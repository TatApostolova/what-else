"""Learning boundary: the only place that decides what history the agents see."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContext:
    statement: str
    context: str | None = None
    history: str = ""
