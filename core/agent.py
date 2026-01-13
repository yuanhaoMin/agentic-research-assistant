import json
import os
from datetime import datetime
from typing import Any, Dict, Callable, List, Optional

from core.models import AgentPlan, ToolStep, TraceEvent, AgentRunResult
from llm.base import BaseLLM
from tools.company_db import get_company_info
from tools.web_search import mock_web_search
from tools.translation import translate_document
from tools.doc_gen import generate_document
from tools.security import hybrid_security_filter


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class ResearchBriefingAgent:
    def __init__(
        self,
        llm: BaseLLM,
        template_path: str,
        company_db_path: str,
        sensitive_terms: List[str],
        enable_live_web: bool = False,
    ):
        self.llm = llm
        self.template_path = template_path
        self.company_db_path = company_db_path
        self.sensitive_terms = sensitive_terms
        self.enable_live_web = enable_live_web

        self.tool_registry: Dict[str, Callable[..., Any]] = {
            "get_company_info": lambda **kw: get_company_info(
                db_path=self.company_db_path, **kw
            ),
            "mock_web_search": lambda **kw: mock_web_search(
                enable_live=self.enable_live_web, **kw
            ),
            "translate_document": lambda **kw: translate_document(llm=self.llm, **kw),
            "generate_document": lambda **kw: generate_document(
                template_path=self.template_path, **kw
            ),
            "security_filter": lambda **kw: hybrid_security_filter(
                llm=self.llm,
                sensitive_terms=self.sensitive_terms,
                **kw,
            ),
        }

    def _trace(
        self, trace: List[TraceEvent], event_type: str, payload: Dict[str, Any]
    ) -> None:
        trace.append(
            TraceEvent(event_type=event_type, payload={"ts": _now_iso(), **payload})
        )

    def _fallback_plan(self, instruction: str) -> AgentPlan:
        target_language = "en"
        tokens = [t.strip(",.?!") for t in instruction.split() if t.strip(",.?!")]
        company_name = tokens[-1] if tokens else "UnknownCo"

        steps = [
            ToolStep(tool="get_company_info", args={"company_name": company_name}),
            ToolStep(tool="mock_web_search", args={"company_name": company_name}),
            ToolStep(
                tool="translate_document",
                args={
                    "document": "",
                    "target_language": target_language,
                    "source": "internal",
                    "mode": "plain",
                },
            ),
            ToolStep(tool="generate_document", args={"content_dict": {}}),
            ToolStep(
                tool="translate_document",
                args={
                    "document": "",
                    "target_language": target_language,
                    "source": "final",
                    "mode": "briefing",
                },
            ),
            ToolStep(tool="security_filter", args={"document": ""}),
        ]
        return AgentPlan(
            company_name=company_name, target_language=target_language, steps=steps
        )

    def plan(self, instruction: str) -> AgentPlan:
        planner_instruction = (
            "Plan tool calls for a research assistant that produces a company briefing.\n"
            "Available tools:\n"
            "- get_company_info(company_name)\n"
            "- mock_web_search(company_name)\n"
            "- translate_document(document, target_language, source, mode)\n"
            "- generate_document(content_dict)\n"
            "- security_filter(document)\n\n"
            "Rules:\n"
            "1) Always include security_filter as the final step.\n"
            "2) translate_document may be used for:\n"
            '   - internal document translation (source="internal", mode="plain")\n'
            '   - final briefing localization after generate_document (source="final", mode="briefing")\n'
            "3) generate_document should happen right before either:\n"
            '   - translate_document(source="final") if target_language is not English, otherwise\n'
            "   - security_filter\n"
            "Return a JSON structure matching the schema."
        )

        full_prompt = f"{planner_instruction}\n\nUser request: {instruction}"

        try:
            parsed = self.llm.plan(
                full_prompt,
                schema=AgentPlan,
            )

            plan = AgentPlan(
                company_name=parsed.company_name,
                target_language=parsed.target_language,
                steps=parsed.steps,
            )

        except Exception as e:
            print("\n[PLAN][ERROR] llm.plan() failed, falling back")
            print("Exception type:", type(e).__name__)
            print("Exception message:", str(e))
            print("Traceback:")
            plan = self._fallback_plan(instruction)

        return plan

    def normalize_plan(self, plan: AgentPlan, internal_document_text: str) -> AgentPlan:
        steps = list(plan.steps or [])

        # (A) Make sure security_filter at last
        steps = [s for s in steps if s.tool != "security_filter"]
        steps.append(ToolStep(tool="security_filter", args={"document": ""}))

        # (B) if internal_doc exist: make sure translate_document(source=internal) before generate_document
        if (internal_document_text or "").strip():
            gen_idx = next(
                (i for i, s in enumerate(steps) if s.tool == "generate_document"),
                None,
            )
            trans_idx = next(
                (
                    i
                    for i, s in enumerate(steps)
                    if s.tool == "translate_document"
                    and (s.args or {}).get("source", "internal") != "final"
                ),
                None,
            )

            if gen_idx is not None:
                if trans_idx is None:
                    steps.insert(
                        gen_idx,
                        ToolStep(
                            tool="translate_document",
                            args={
                                "document": "",
                                "target_language": plan.target_language,
                                "source": "internal",
                                "mode": "plain",
                            },
                        ),
                    )
                elif trans_idx > gen_idx:
                    trans_step = steps.pop(trans_idx)
                    steps.insert(gen_idx, trans_step)

        # (C) If target_language != en: ensure translate_document(source=final, mode=briefing)
        tl = (plan.target_language or "en").lower().strip()
        if tl not in ("en", "english"):
            has_final_translate = any(
                s.tool == "translate_document"
                and (s.args or {}).get("source") == "final"
                for s in steps
            )
            if not has_final_translate:
                gen_idx = next(
                    (i for i, s in enumerate(steps) if s.tool == "generate_document"),
                    None,
                )
                sec_idx = next(
                    (i for i, s in enumerate(steps) if s.tool == "security_filter"),
                    None,
                )

                insert_at = sec_idx if sec_idx is not None else len(steps)
                if gen_idx is not None:
                    insert_at = min(insert_at, gen_idx + 1)

                steps.insert(
                    insert_at,
                    ToolStep(
                        tool="translate_document",
                        args={
                            "document": "",
                            "target_language": plan.target_language,
                            "source": "final",
                            "mode": "briefing",
                        },
                    ),
                )

        plan.steps = steps
        return plan

    def run(
        self,
        instruction: str,
        internal_document_text: str = "",
        trace_path: Optional[str] = None,
    ) -> AgentRunResult:
        trace: List[TraceEvent] = []
        self._trace(trace, "start", {"instruction": instruction})

        plan = self.plan(instruction)
        self._trace(trace, "raw_plan", {"plan": plan.model_dump()})

        plan = self.normalize_plan(plan, internal_document_text)
        self._trace(trace, "plan", {"plan": plan.model_dump()})

        ctx: Dict[str, Any] = {
            "company_name": plan.company_name,
            "target_language": plan.target_language,
            "internal_document_text": internal_document_text,
            "translated_internal_doc": "",
        }

        draft_document = ""
        redactions: List[str] = []

        for idx, step in enumerate(plan.steps):
            tool_name = step.tool
            tool = self.tool_registry.get(tool_name)

            if tool is None:
                self._trace(
                    trace,
                    "tool_error",
                    {"step": idx, "tool": tool_name, "error": "Tool not found"},
                )
                continue

            args = dict(step.args or {})

            # Inject dynamic args
            if tool_name == "get_company_info":
                args.setdefault("company_name", ctx["company_name"])

            elif tool_name == "mock_web_search":
                args.setdefault("company_name", ctx["company_name"])

            elif tool_name == "translate_document":
                source = (args.get("source") or "internal").lower().strip()
                if source == "final":
                    args["document"] = draft_document or ""
                    args.setdefault("mode", "briefing")
                else:
                    args["document"] = ctx.get("internal_document_text", "") or ""
                    args.setdefault("mode", "plain")
                args["target_language"] = ctx.get("target_language", "en")
                args["source"] = source

            elif tool_name == "generate_document":
                built_cd = self._build_content_dict(ctx)
                planned_cd = args.get("content_dict", {}) or {}
                merged_cd = built_cd | planned_cd
                merged_cd.setdefault(
                    "target_language", ctx.get("target_language", "en")
                )
                merged_cd.setdefault("language", ctx.get("target_language", "en"))
                args = {"content_dict": merged_cd}

            elif tool_name == "security_filter":
                args["document"] = draft_document or ""

            self._trace(
                trace, "tool_call", {"step": idx, "tool": tool_name, "args": args}
            )

            try:
                out = tool(**args)
                self._trace(
                    trace,
                    "tool_result",
                    {"step": idx, "tool": tool_name, "output_preview": _preview(out)},
                )

                if tool_name == "get_company_info":
                    ctx["company_info"] = out

                elif tool_name == "mock_web_search":
                    ctx["web_findings"] = out

                elif tool_name == "translate_document":
                    source = (args.get("source") or "internal").lower().strip()
                    if source == "final":
                        draft_document = out or ""
                        ctx["draft_document"] = draft_document
                    else:
                        ctx["translated_internal_doc"] = out or ""

                elif tool_name == "generate_document":
                    draft_document = out or ""
                    ctx["draft_document"] = draft_document

                elif tool_name == "security_filter":
                    draft_document, redactions = out
                    ctx["final_document"] = draft_document
                    ctx["redactions"] = redactions

            except Exception as e:
                self._trace(
                    trace,
                    "tool_error",
                    {"step": idx, "tool": tool_name, "error": str(e)},
                )

        final_doc = ctx.get("final_document", draft_document)
        self._trace(
            trace, "end", {"redactions": redactions, "final_len": len(final_doc)}
        )

        if trace_path:
            os.makedirs(os.path.dirname(trace_path), exist_ok=True)
            with open(trace_path, "w", encoding="utf-8") as f:
                for ev in trace:
                    f.write(json.dumps(ev.model_dump(), ensure_ascii=False) + "\n")

        return AgentRunResult(
            instruction=instruction,
            plan=plan,
            trace=trace,
            final_document=final_doc,
            redactions=redactions,
        )

    def _build_content_dict(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        info = ctx.get("company_info", {}) or {}
        web = ctx.get("web_findings", {}) or {}

        internal_doc = ctx.get("translated_internal_doc", "") or ""
        if internal_doc:
            internal_summary = self.llm.summarize(
                internal_doc, ctx["target_language"], max_words=160
            )
        else:
            internal_summary = "(No internal document provided.)"

        web_text = web.get("combined_text", "") or ""
        if web_text:
            web_summary = self.llm.summarize(
                web_text, ctx["target_language"], max_words=160
            )
        else:
            web_summary = "(No web findings.)"

        return {
            "company_name": ctx.get("company_name", "UnknownCo"),
            "industry": info.get("industry", "Unknown"),
            "headquarters": info.get("headquarters", "Unknown"),
            "website": info.get("website", "Unknown"),
            "products": info.get("products", []),
            "partnerships": web.get("partnerships", []) or info.get("partnerships", []),
            "web_summary": web_summary,
            "internal_doc_summary": internal_summary,
            "risk_category": info.get("risk_category", "unknown"),
        }


def _preview(x: Any, n: int = 400) -> str:
    s = str(x)
    return s if len(s) <= n else s[:n] + "..."
