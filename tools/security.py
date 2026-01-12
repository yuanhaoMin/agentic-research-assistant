import re
from typing import List, Tuple, Optional

from llm.base import BaseLLM


def _variant_pattern(term: str) -> re.Pattern:
    """
    Build a regex that matches common obfuscations like:
    "Project Phoenix", "Project.Phoenix", "P r o j e c t  P h o e n i x"
    """
    escaped = [re.escape(ch) for ch in term]
    pat = r"[\s\.\-_]*".join(escaped)
    return re.compile(pat, flags=re.IGNORECASE)


def security_filter(document: str, sensitive_terms: List[str]) -> Tuple[str, List[str]]:
    """
    Regex-based redaction. Returns (filtered_doc, redacted_terms).
    """
    redacted: List[str] = []
    out = document

    for term in sensitive_terms:
        if not term.strip():
            continue
        pattern = _variant_pattern(term.strip())
        if pattern.search(out):
            out = pattern.sub("[REDACTED]", out)
            redacted.append(term)

    return out, redacted


def hybrid_security_filter(
    document: str,
    sensitive_terms: List[str],
    *,
    llm: BaseLLM,
    target_language: Optional[str] = None,
    replacement: str = "[REDACTED]",
    enable_llm: bool = True,
) -> Tuple[str, List[str]]:
    """
    Two-pass redaction:
    1) Regex for exact terms + simple obfuscations (fast, deterministic)
    2) LLM for translations/paraphrases/semantic references (slow, robust)

    Returns (final_doc, redacted_terms_original_list)
    """
    # Pass 1: regex
    regex_out, regex_hits = security_filter(
        document=document, sensitive_terms=sensitive_terms
    )

    if not enable_llm:
        return regex_out, sorted(set(regex_hits))

    # Pass 2: LLM
    # - Use the regex output as input to reduce surface area + token usage
    # - Ask model to only redact when highly confident and preserve text except replacements
    llm_out, llm_hits = llm.redact(
        text=regex_out,
        sensitive_terms=sensitive_terms,
        target_language=target_language,
        replacement=replacement,
    )

    merged_hits = list(dict.fromkeys((regex_hits or []) + (llm_hits or [])))

    # Safety: if LLM returns empty for some reason, fall back to regex output
    final_doc = llm_out or regex_out
    return final_doc, merged_hits
