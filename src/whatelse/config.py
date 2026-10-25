"""Settings: config.toml inside the package, overridden by environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def default_data_dir() -> Path:
    """Per-user app-data folder, outside the repository."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "WhatElse"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "whatelse"


@dataclass(frozen=True)
class Settings:
    mode: str  # "real" or "demo"
    data_dir: Path
    pattern: str
    model: str | None
    effort: str | None
    seeds_per_agent: int
    ideas_per_agent: int
    timeout_seconds: int
    techniques: list[str]
    hints: dict[str, str] = field(default_factory=dict)
    save_tags: list[dict[str, str]] = field(default_factory=list)
    discard_tags: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def tag_labels(self) -> dict[str, str]:
        return {t["key"]: t["label"] for t in self.save_tags + self.discard_tags}

    @property
    def db_path(self) -> Path:
        return self.data_dir / ("demo.db" if self.is_demo else "whatelse.db")

    @property
    def log_path(self) -> Path:
        name = "demo-agent-calls.jsonl" if self.is_demo else "agent-calls.jsonl"
        return self.data_dir / "logs" / name


def load_settings(mode: str | None = None) -> Settings:
    with open(PACKAGE_DIR / "config.toml", "rb") as f:
        raw = tomllib.load(f)

    mode = mode or os.environ.get("WHATELSE_MODE") or "real"
    if mode not in ("real", "demo"):
        raise ValueError(f"Unknown mode {mode!r}: use 'real' or 'demo'.")

    data_dir = os.environ.get("WHATELSE_DATA_DIR")
    model = os.environ.get("WHATELSE_MODEL", raw.get("model", "")) or None
    effort = os.environ.get("WHATELSE_EFFORT", raw.get("effort", "")) or None

    return Settings(
        mode=mode,
        data_dir=Path(data_dir) if data_dir else default_data_dir(),
        pattern=os.environ.get("WHATELSE_PATTERN", raw["pattern"]),
        model=model,
        effort=effort,
        seeds_per_agent=int(raw["seeds_per_agent"]),
        ideas_per_agent=int(raw["ideas_per_agent"]),
        timeout_seconds=int(raw["timeout_seconds"]),
        techniques=list(raw["techniques"]),
        hints=dict(raw.get("hints", {})),
        save_tags=list(raw["tags"]["save"]),
        discard_tags=list(raw["tags"]["discard"]),
    )
