import os
import json
import streamlit as st
from dotenv import load_dotenv

from core.agent import ResearchBriefingAgent
from llm.open_source_client import FriendliLLM
from llm.openai_client import OpenAILLM


# -----------------------
# Shared helpers
# -----------------------
def build_llm(provider: str):
    provider = (provider or "").lower().strip()

    if provider == "openai":
        return OpenAILLM(model=os.getenv("OPENAI_MODEL", "gpt-4.1"))

    if provider in ("friendli", "oss", "open_source", "opensource"):
        token = os.getenv("FRIENDLI_TOKEN", "")
        model = os.getenv("FRIENDLI_MODEL", "mistralai/Magistral-Small-2506")
        base_url = os.getenv(
            "FRIENDLI_BASE_URL", "https://api.friendli.ai/serverless/v1"
        )
        return FriendliLLM(token=token, model=model, base_url=base_url)

    raise ValueError(f"Unknown provider: {provider}. Use openai|friendli")


def load_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_default_index(options, predicate, fallback: int = 0) -> int:
    for i, x in enumerate(options):
        if predicate(x):
            return i
    return fallback


def main():
    load_dotenv()

    st.set_page_config(
        page_title="Research Briefing Agent", page_icon="🧪", layout="wide"
    )
    st.title("🧪 Research Assistant (Agentic) — Company Briefing Generator")

    # Load assets
    companies = load_json("data/synth_companies.json")
    internal_docs_all = load_json("data/internal_docs.json")

    company_names = [c.get("name", "UnknownCo") for c in companies] or [
        "Tesla",
        "OpenAI",
    ]

    # ---- Layout: two main columns (no sidebar) ----
    left, right = st.columns([1.6, 1.0], gap="large")

    # -----------------------
    # Left: Instruction + Internal doc
    # -----------------------
    with left:
        st.subheader("1) Instruction")
        default_instruction = "Generate a company briefing on Tesla in German"
        instruction = st.text_area(
            "Enter instruction (natural language)",
            value=default_instruction,
            height=90,
        )

        st.subheader("2) Internal document (shown as PDF, backend uses text)")

        # ✅ Default company -> Tesla
        default_company_idx = find_default_index(
            company_names,
            lambda name: (name or "").strip().lower() == "tesla",
            fallback=0,
        )
        selected_company = st.selectbox(
            "Company (optional helper)",
            options=company_names,
            index=default_company_idx,
        )

        # Filter docs by company
        def same_company(doc):
            return (doc.get("company") or "").strip().lower() == (
                selected_company or ""
            ).strip().lower()

        filtered_docs = [d for d in internal_docs_all if same_company(d)]
        # if none matched, fall back to all docs
        if not filtered_docs:
            filtered_docs = internal_docs_all

        # We'll keep internal key as doc["id"] but display only title (no id in UI)
        # Use objects in selectbox with format_func
        def fmt_doc(d):
            return d.get("title", "Internal.pdf")

        # ✅ Default doc -> Tesla_Internal_Q3_Notes.pdf (by id preferred; fallback by title)
        default_doc_idx = find_default_index(
            filtered_docs,
            lambda d: (d.get("id") == "tesla_q3_internal")
            or (
                (d.get("title") or "").strip().lower() == "tesla_internal_q3_notes.pdf"
            ),
            fallback=0,
        )

        if filtered_docs:
            chosen_doc = st.selectbox(
                "Choose an internal PDF",
                options=filtered_docs,
                index=default_doc_idx,
                format_func=fmt_doc,
            )
        else:
            chosen_doc = None
            st.info("No internal document available.")

        internal_text = (chosen_doc or {}).get("text", "") if chosen_doc else ""

        # Show PDF icon card (no id)
        if chosen_doc:
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:12px;padding:12px;border:1px solid #2a2a2a;border-radius:10px;">
                    <div style="font-size:34px;">📄</div>
                    <div>
                        <div style="font-weight:700;">{chosen_doc.get("title","Internal.pdf")}</div>
                        <div style="font-size:12px;color:#9aa0a6;">
                            company={chosen_doc.get("company","")}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander(
                "Preview internal text (what backend will send to translate_document)",
                expanded=False,
            ):
                st.code(internal_text, language="text")

    # -----------------------
    # Right: Settings + Run (not empty anymore)
    # -----------------------
    with right:
        st.subheader("Settings & Run")

        with st.container(border=True):
            # ✅ Default opensource
            provider_label_to_value = {
                "opensource (Magistral-Small-2506)": "friendli",
                "openai (GPT-4.1)": "openai",
            }

            llm_provider_label = st.selectbox(
                "LLM Provider",
                options=list(provider_label_to_value.keys()),
                index=0,
            )

            enable_live_web = st.checkbox(
                "Enable live web (mock tool toggle)",
                value=False,
                help="Toggles mock_web_search(enable_live=...)",
            )

            trace_path = st.text_input("Trace path", value="runs/streamlit_run.jsonl")

            st.caption("Env vars used:")
            st.code(
                "\n".join(
                    [
                        "OPENAI_MODEL",
                        "FRIENDLI_TOKEN",
                        "FRIENDLI_MODEL",
                        "FRIENDLI_BASE_URL",
                    ]
                ),
                language="text",
            )

        st.write("")  # spacing

        run_btn = st.button("🚀 Run Agent", type="primary", use_container_width=True)

        # A small helper panel so the right side isn't just run button
        with st.expander("Quick sanity checks", expanded=False):
            st.write(f"**Selected company:** {selected_company}")
            st.write(f"**Selected model:** {llm_provider_label}")
            st.write(f"**Internal doc:** {(chosen_doc or {}).get('title','(none)')}")
            st.write(f"**Internal doc length:** {len(internal_text or '')} chars")

    # -----------------------
    # Execute + Results (full width, below)
    # -----------------------
    if run_btn:
        sensitive_terms = [
            "Project Phoenix",
            "Internal-Only Alpha",
            "Redwood Initiative",
        ]

        llm = build_llm(provider_label_to_value[llm_provider_label])

        agent = ResearchBriefingAgent(
            llm=llm,
            template_path="templates/briefing_template.md",
            company_db_path="data/synth_companies.json",
            sensitive_terms=sensitive_terms,
            enable_live_web=enable_live_web,
        )

        with st.spinner("Running agent..."):
            res = agent.run(
                instruction=instruction,
                internal_document_text=internal_text,
                trace_path=trace_path,
            )

        st.success("Done!")

        tab1, tab2, tab3 = st.tabs(
            ["📄 Final Document", "🧾 Security Filtering", "🧠 Trace (preview)"]
        )

        with tab1:
            st.markdown(res.final_document)

        with tab2:
            if res.redactions:
                st.warning("Redacted terms: " + ", ".join(res.redactions))
            else:
                st.info("No redactions.")

        with tab3:
            last_n = 25
            trace_preview = [
                ev.model_dump() for ev in (res.trace[-last_n:] if res.trace else [])
            ]
            st.json(trace_preview)


if __name__ == "__main__":
    main()
