from __future__ import annotations
import json
from typing import Any, Callable, Type, TypeVar

from pydantic import ValidationError

T = TypeVar("T")


def strip_markdown_fences(text: str) -> str:
    """
    If text is wrapped in ```...``` fences (optionally ```json),
    remove the fences and return the inner content.
    """
    t = (text or "").strip()
    if not t.startswith("```"):
        return t

    lines = t.splitlines()
    if not lines:
        return t

    inner = "\n".join(lines[1:]).strip()
    if inner.endswith("```"):
        inner = inner.rsplit("```", 1)[0].strip()
    return inner


def extract_first_json_object(text: str) -> str:
    """
    Extract the first top-level JSON object {...} from text.
    Robust to leading commentary. Handles strings and escapes.
    """
    if not text:
        raise ValueError("Empty model output")

    t = text.strip()
    start = t.find("{")
    if start < 0:
        raise ValueError("No JSON object start '{' found in output")

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(t)):
        ch = t[i]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return t[start : i + 1]

    raise ValueError("Unclosed JSON object in output")


def coerce_to_json_text(raw: str) -> str:
    """
    Best-effort: strip code fences and extract a JSON object.
    Returns a string that should be valid JSON (object) for json.loads.
    """
    cleaned = strip_markdown_fences(raw)
    s = cleaned.lstrip()
    if s.startswith("{") and cleaned.rstrip().endswith("}"):
        return cleaned.strip()
    return extract_first_json_object(cleaned)


def read_output_text_from_response(resp: Any) -> str:
    """
    OpenAI SDK version differences:
    - Some versions expose resp.output_text
    - Others require stitching from resp.output[].content[].text
    """
    out = getattr(resp, "output_text", None)
    if out:
        return (out or "").strip()

    try:
        parts: list[str] = []
        for item in getattr(resp, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", None) == "output_text":
                        parts.append(getattr(c, "text", "") or "")
        return "".join(parts).strip()
    except Exception:
        return ""


def plan_with_json_retries(
    *,
    instruction: str,
    schema: Type[T],
    generate_text: Callable[[str], str],
    retries: int = 2,
    debug: bool = False,
    debug_prefix: str = "PLAN",
) -> T:
    """
    Generic "ask model for JSON plan" implementation:
    - builds schema prompt
    - calls generate_text(prompt_or_input) which returns raw text
    - coerces to JSON + pydantic validate
    - retries on JSONDecodeError/ValidationError/ValueError
    """
    schema_json = schema.model_json_schema()
    planner_instructions = (
        "You are a careful planner for a tool-using research agent.\n"
        "Return ONLY valid JSON. No markdown, no code fences, no extra text.\n"
        "The JSON must match this JSON Schema:\n"
        f"{json.dumps(schema_json, ensure_ascii=False)}"
    )

    last_err: Exception | None = None
    cur = instruction

    for attempt in range(retries + 1):
        raw = generate_text(f"{planner_instructions}\n\nUser request:\n{cur}")

        if debug:
            print(f"\n[{debug_prefix}][ATTEMPT {attempt}] RAW MODEL OUTPUT:")
            print("--------------------------------------------------")
            print(repr(raw[:1200]))
            print("--------------------------------------------------")

        try:
            json_text = coerce_to_json_text(raw)
            obj = json.loads(json_text)
            return schema.model_validate(obj)
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_err = e
            cur = (
                "Your previous output was invalid.\n"
                f"Error: {str(e)}\n"
                "Return ONLY corrected JSON that matches the schema. No markdown.\n\n"
                f"Original instruction:\n{instruction}"
            )

    raise RuntimeError(f"Failed to produce valid plan JSON. Last error: {last_err}")
