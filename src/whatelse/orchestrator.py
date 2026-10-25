"""Loads techniques and runs a collaboration pattern."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from whatelse.config import PACKAGE_DIR, Settings
from whatelse.context import AgentContext
from whatelse.llm import LLM, LLMError
from whatelse.patterns import PatternResult

TECHNIQUES_DIR = PACKAGE_DIR / "techniques"
PATTERNS = ("collaborative", "single_prompt")


@dataclass(frozen=True)
class Technique:
    key: str
    label: str
    body: str


def _parse_technique(text: str) -> Technique:
    """Minimal frontmatter: `---`, `key: value` lines, `---`, then the body."""
    _, front, body = text.split("---", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    return Technique(key=meta["key"], label=meta["label"], body=body.strip())


def load_techniques(keys: list[str]) -> list[Technique]:
    return [_parse_technique((TECHNIQUES_DIR / f"{k}.md").read_text(encoding="utf-8")) for k in keys]


def technique_label(keys: list[str], techniques: list[Technique]) -> str:
    """Card label: own technique first, then what it built on, e.g. 'SCAMPER ← ANALOGIES + REVERSE THINKING'."""
    labels = {t.key: t.label.upper() for t in techniques}
    names = [labels.get(k, k.replace("_", " ").upper()) for k in keys]
    if len(names) == 1:
        return names[0]
    return f"{names[0]} ← {' + '.join(names[1:])}"


def generate(ctx: AgentContext, llm: LLM, settings: Settings, pattern: str | None = None) -> PatternResult:
    """Run a pattern. Raises LLMError on any failure; never returns partial results."""
    name = pattern or settings.pattern
    if name not in PATTERNS:
        raise ValueError(f"Unknown pattern {name!r}")
    module = importlib.import_module(f"whatelse.patterns.{name}")
    result = module.run(ctx, llm, load_techniques(settings.techniques), settings)
    if not result.ideas:
        raise LLMError("failed", "pattern returned no ideas")
    return result
