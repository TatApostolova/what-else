"""Collaboration patterns and the helpers they share.

A pattern is a module with `run(ctx, llm, techniques, settings) -> PatternResult`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from string import Template
from typing import Any, Callable, Iterable, TypeVar

from pydantic import BaseModel, Field, ValidationError

from whatelse.config import PACKAGE_DIR
from whatelse.context import AgentContext
from whatelse.llm import LLMError

PROMPTS_DIR = PACKAGE_DIR / "prompts"


class IdeaDraft(BaseModel):
    """A validated idea ready to be stored."""

    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    techniques: list[str] = Field(min_length=1)  # own technique first
    built_on: list[str] = Field(default_factory=list)
    how: str | None = None


@dataclass
class PatternResult:
    pattern: str
    ideas: list[IdeaDraft]
    data: dict[str, Any] = field(default_factory=dict)


def render(name: str, **values: Any) -> str:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return Template(text).substitute(values).strip()


def challenge_block(ctx: AgentContext) -> str:
    block = render(
        "challenge",
        statement=ctx.statement.strip(),
        context=(ctx.context or "").strip() or "(none given)",
    )
    if ctx.history.strip():
        block += "\n\n## History of this challenge\n" + ctx.history.strip()
    return block


def system_prompt(technique: Any) -> str:
    return render("agent_system", label=technique.label, technique=technique.body)


T = TypeVar("T")
R = TypeVar("R")


def run_parallel(fn: Callable[[T], R], items: Iterable[T], workers: int = 5) -> list[tuple[T, R | Exception]]:
    """Run `fn` over items in parallel. Exceptions are returned in place of results."""
    items = list(items)

    def safe(item: T) -> R | Exception:
        try:
            return fn(item)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            return exc

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(zip(items, pool.map(safe, items)))


def as_llm_error(exc: Exception) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, ValidationError):
        return LLMError("failed", f"agent output didn't match the expected shape: {exc.errors()[:2]}")
    return LLMError("failed", repr(exc))
