import argparse
import os
from dotenv import load_dotenv

from core.agent import ResearchBriefingAgent
from llm.open_source_client import FriendliLLM
from llm.openai_client import OpenAILLM


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

    raise ValueError(f"Unknown --llm_provider: {provider}. Use openai|friendli")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--instruction", type=str, required=True)
    parser.add_argument("--internal_doc", type=str, default="")
    parser.add_argument("--enable_live_web", action="store_true")
    parser.add_argument("--trace_path", type=str, default="runs/run_001.jsonl")
    parser.add_argument(
        "--llm_provider",
        type=str,
        default=os.getenv("LLM_PROVIDER", "openai"),
        help="openai|friendli",
    )
    args = parser.parse_args()

    llm = build_llm(args.llm_provider)

    sensitive_terms = [
        "Project Phoenix",
        "Internal-Only Alpha",
        "Redwood Initiative",
    ]

    agent = ResearchBriefingAgent(
        llm=llm,
        template_path="templates/briefing_template.md",
        company_db_path="data/synth_companies.json",
        sensitive_terms=sensitive_terms,
        enable_live_web=args.enable_live_web,
    )

    res = agent.run(
        instruction=args.instruction,
        internal_document_text=args.internal_doc,
        trace_path=args.trace_path,
    )

    print("\n===== FINAL DOCUMENT =====\n")
    print(res.final_document)
    if res.redactions:
        print("\n[Security] Redacted terms:", ", ".join(res.redactions))


if __name__ == "__main__":
    main()
