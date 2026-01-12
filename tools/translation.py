from typing import Any


def translate_document(document: str, target_language: str, llm: Any) -> str:
    """
    Internal PDF translation is mocked as translating plain text input.
    """
    if not document.strip():
        return ""
    return llm.translate(document, target_language)
