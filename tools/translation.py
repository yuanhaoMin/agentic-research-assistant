from typing import Any


def translate_document(
    document: str,
    target_language: str,
    llm: Any,
    source: str = "internal",
    mode: str = "plain",
) -> str:
    """
    Translation tool.
    - plain mode: normal translation (internal docs, etc.)
    - briefing mode: localize a Markdown briefing while preserving structure
      (used to translate the FINAL rendered briefing into target_language)
    """
    if not (document or "").strip():
        return ""

    mode_l = (mode or "plain").lower().strip()

    # Briefing localization: preserve Markdown structure, don't translate proper nouns/URLs/tokens.
    if mode_l == "briefing":
        instructions = (
            "You are a localization engine for Markdown company briefings.\n"
            "Translate the briefing into the target language while preserving Markdown structure EXACTLY.\n"
            "Rules:\n"
            "1) Preserve headings levels, numbering, bullet structure, indentation, and blank lines.\n"
            "2) Translate only human-readable labels and prose.\n"
            "3) Do NOT translate: company names, product names, proper nouns, URLs, code, and tokens like [REDACTED].\n"
            "4) Do not add/remove/reorder any sections or bullets.\n"
            "Return ONLY the localized Markdown.\n"
        )
        return llm.generate_text(
            instructions=instructions,
            input_text=f"Target language: {target_language}\n\nMarkdown:\n{document}",
        )

    # Plain translation
    return llm.translate(document, target_language)
