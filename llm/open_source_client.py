from __future__ import annotations
import os
from typing import Any, Dict, Optional, Type, TypeVar, List, Tuple

from openai import OpenAI

from core.models import RedactionResult
from llm.base import BaseLLM
from llm.json_fix import plan_with_json_retries

T = TypeVar("T")


class FriendliLLM(BaseLLM):
    """
    Friendli Serverless wrapper (OpenAI-compatible).
    - generate_text(): Chat Completions API
    - plan(): JSON-in-text planning via plan_with_json_retries()
    """

    def __init__(
        self,
        *,
        token: str,
        model: str = "mistralai/Magistral-Small-2506",
        base_url: str = "https://api.friendli.ai/serverless/v1",
        extra_body: Optional[Dict[str, Any]] = None,
        debug_plan: Optional[bool] = None,
    ):
        if not token:
            raise ValueError("Missing Friendli token (set FRIENDLI_TOKEN)")

        self.token = token
        self.model = model
        self.base_url = base_url
        self.extra_body = extra_body or {}
        self.client = OpenAI(api_key=self.token, base_url=self.base_url)

        if debug_plan is None:
            debug_plan = os.getenv("FRIENDLI_DEBUG_PLAN", "0").strip().lower() in (
                "1",
                "true",
                "yes",
            )
        self.debug_plan = debug_plan

    def _generate_text_impl(
        self,
        *,
        instructions: str,
        input_text: str,
        max_tokens: int,
        temperature: float,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            extra_body=(self.extra_body | (extra_body or {})),
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )
        return (completion.choices[0].message.content or "").strip()

    def generate_text(self, instructions: str, input_text: str) -> str:
        return self._generate_text_impl(
            instructions=instructions,
            input_text=input_text,
            max_tokens=512,
            temperature=0.2,
        )

    def plan(self, instruction: str, schema: Type[T], retries: int = 2) -> T:
        def _gen(prompt: str) -> str:
            return self._generate_text_impl(
                instructions="You are a careful planner for a tool-using research agent.",
                input_text=prompt,
                max_tokens=900,
                temperature=0.0,
            )

        return plan_with_json_retries(
            instruction=instruction,
            schema=schema,
            generate_text=_gen,
            retries=retries,
            debug=self.debug_plan,
            debug_prefix="PLAN/Friendli",
        )

    def translate(self, text: str, target_language: str) -> str:
        instr = (
            "You are a professional translator. "
            "Translate the user's text into the target language. "
            "Preserve bullet points and structure. Return only the translation."
        )
        return self._generate_text_impl(
            instructions=instr,
            input_text=f"Target language: {target_language}\n\nText:\n{text}",
            max_tokens=1024,
            temperature=0.2,
        )

    def summarize(self, text: str, target_language: str, max_words: int = 180) -> str:
        instr = (
            "You are a precise analyst. Summarize the text for a company briefing. "
            f"Write the summary in {target_language}. "
            f"Keep it under {max_words} words. Return only the summary."
        )
        return self._generate_text_impl(
            instructions=instr,
            input_text=f"Text:\n{text}",
            max_tokens=512,
            temperature=0.2,
        )

    def redact(
        self,
        text: str,
        sensitive_terms: List[str],
        *,
        target_language: Optional[str] = None,
        replacement: str = "[REDACTED]",
    ) -> Tuple[str, List[str]]:
        lang = target_language or "auto"

        instructions = (
            "You are a security redaction engine.\n"
            "Replace sensitive info with the replacement token.\n"
            "Preserve text exactly except replacements. No rewriting.\n"
            "Detect translations/obfuscations/paraphrases referring to the same named items.\n"
            "Only redact when highly confident.\n"
            'Return ONLY valid JSON: {"redacted_text": "...", "matched_terms": ["..."]}.\n'
        )

        payload = {
            "target_language": lang,
            "replacement": replacement,
            "sensitive_terms": sensitive_terms,
            "text": text,
        }

        def _gen(prompt: str) -> str:
            return self._generate_text_impl(
                instructions=instructions,
                input_text=prompt,
                max_tokens=1200,
                temperature=0.0,
            )

        result = plan_with_json_retries(
            instruction=str(payload),
            schema=RedactionResult,
            generate_text=_gen,
            retries=2,
            debug=self.debug_plan,
            debug_prefix="REDACT/Friendli",
        )

        return (result.redacted_text or ""), list(
            dict.fromkeys(result.matched_terms or [])
        )
