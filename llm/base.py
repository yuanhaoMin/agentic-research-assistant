from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional, Tuple

T = TypeVar("T")


class BaseLLM(ABC):
    """
    Abstract base class for LLM clients.
    Subclasses MUST implement these methods, otherwise instantiation fails.
    """

    @abstractmethod
    def plan(self, instruction: str, schema: Type[T]) -> T:
        raise NotImplementedError

    @abstractmethod
    def generate_text(self, instructions: str, input_text: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def translate(self, text: str, target_language: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, text: str, target_language: str, max_words: int = 180) -> str:
        raise NotImplementedError

    @abstractmethod
    def redact(
        self,
        text: str,
        sensitive_terms: List[str],
        *,
        target_language: Optional[str] = None,
        replacement: str = "[REDACTED]",
    ) -> Tuple[str, List[str]]:
        raise NotImplementedError
