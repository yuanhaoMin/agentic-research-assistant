from __future__ import annotations
import os
from typing import Optional, Type, TypeVar, List, Tuple

from openai import OpenAI

from core.models import RedactionResult
from llm.base import BaseLLM
from llm.json_fix import (
    plan_with_json_retries,
    read_output_text_from_response,
)

T = TypeVar("T")


class OpenAILLM(BaseLLM):
    """
    OpenAI wrapper using the Responses API.
    - plan(): JSON-in-text planning via plan_with_json_retries()
      (Avoids responses.parse schema restrictions with Dict[str, Any])
    - generate_text(): responses.create()
    """

    def __init__(
        self,
        model: Optional[str] = None,
        debug_plan: Optional[bool] = None,
    ):
        self.client = OpenAI()
        self.model = model or "gpt-5"

        if debug_plan is None:
            debug_plan = os.getenv("OPENAI_DEBUG_PLAN", "0").strip().lower() in (
                "1",
                "true",
                "yes",
            )
        self.debug_plan = debug_plan

    def plan(self, instruction: str, schema: Type[T], retries: int = 2) -> T:
        def _gen(prompt: str) -> str:
            resp = self.client.responses.create(
                model=self.model,
                instructions="You are a careful planner for a tool-using research agent.",
                input=prompt,
            )
            return read_output_text_from_response(resp)

        return plan_with_json_retries(
            instruction=instruction,
            schema=schema,
            generate_text=_gen,
            retries=retries,
            debug=self.debug_plan,
            debug_prefix="PLAN/OpenAI",
        )

    def generate_text(self, instructions: str, input_text: str) -> str:
        resp = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=input_text,
        )
        return read_output_text_from_response(resp)

    def translate(self, text: str, target_language: str) -> str:
        instr = (
            "You are a professional translator. "
            "Translate the user's text into the target language. "
            "Preserve bullet points and structure. Return only the translation."
        )
        return self.generate_text(
            instructions=instr,
            input_text=f"Target language: {target_language}\n\nText:\n{text}",
        )

    def summarize(self, text: str, target_language: str, max_words: int = 180) -> str:
        instr = (
            "You are a precise analyst. Summarize the text for a company briefing. "
            f"Write the summary in {target_language}. "
            f"Keep it under {max_words} words. Return only the summary."
        )
        return self.generate_text(
            instructions=instr,
            input_text=f"Text:\n{text}",
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
            "Task: Replace any occurrence of sensitive information in the given text with the replacement token.\n"
            "You MUST:\n"
            "1) Preserve the original text exactly except for replacements (no rewriting).\n"
            "2) Detect occurrences even if:\n"
            "   - translated into the target language\n"
            "   - lightly paraphrased while clearly referring to the same named project/initiative\n"
            "   - obfuscated with spaces/punctuation/hyphens/dots/underscores or mixed case\n"
            "3) Only redact when you are highly confident it refers to one of the provided sensitive terms.\n"
            "Output MUST be valid JSON with keys: redacted_text (string), matched_terms (string[] of ORIGINAL terms).\n"
        )

        payload = {
            "target_language": lang,
            "replacement": replacement,
            "sensitive_terms": sensitive_terms,
            "text": text,
        }

        def _gen(prompt: str) -> str:
            resp = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=prompt,
            )
            return read_output_text_from_response(resp)

        result = plan_with_json_retries(
            instruction=str(payload),
            schema=RedactionResult,
            generate_text=_gen,
            retries=2,
            debug=self.debug_plan,
            debug_prefix="REDACT/OpenAI",
        )

        return (result.redacted_text or ""), list(
            dict.fromkeys(result.matched_terms or [])
        )
