"""LLM adapter: the only module that knows how agents are called.

`ClaudeCLI` runs Claude Code in headless mode (`claude -p`) on the user's existing
subscription. `FakeLLM` is a simulation used only in tests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol


class LLMError(Exception):
    """An agent call failed. `kind` tells the UI which friendly message to show."""

    MESSAGES = {
        "api_key": "ANTHROPIC_API_KEY is set, so calls would be billed to the API. Unset it to use your subscription.",
        "cli_missing": "The Claude Code CLI (`claude`) wasn't found. Install it and log in, then try again.",
        "not_logged_in": "Claude Code isn't logged in. Run `claude` in a terminal and log in, then try again.",
        "failed": "The agents couldn't finish. Try again in a moment.",
    }

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind if kind in self.MESSAGES else "failed"
        self.detail = detail
        super().__init__(f"{self.kind}: {detail}" if detail else self.kind)

    @property
    def user_message(self) -> str:
        return self.MESSAGES[self.kind]


class LLM(Protocol):
    def complete(self, system: str, prompt: str, schema: dict) -> dict: ...


_log_lock = Lock()


def _write_log(log_path: Path | None, entry: dict) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with _log_lock, open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


_LOGIN_HINTS = ("/login", "not logged in", "please log in", "invalid api key", "authentication")


class ClaudeCLI:
    """One `claude -p` subprocess per call. The prompt goes in on stdin (no length limit)."""

    def __init__(
        self,
        model: str | None = None,
        timeout: int = 120,
        log_path: Path | None = None,
        effort: str | None = None,
    ):
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.log_path = log_path

    def _args(self, exe: str, system: str, schema: dict) -> list[str]:
        args = [
            exe, "-p",
            "--output-format", "json",
            "--system-prompt", system,
            "--json-schema", json.dumps(schema),
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--no-session-persistence",
        ]
        if self.model:
            args += ["--model", self.model]
        if self.effort:
            args += ["--effort", self.effort]
        return args

    def complete(self, system: str, prompt: str, schema: dict) -> dict:
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise LLMError("api_key")
        exe = shutil.which("claude")
        if exe is None:
            raise LLMError("cli_missing")

        started = time.monotonic()
        entry: dict = {
            "at": datetime.now(timezone.utc).isoformat(),
            "model": self.model,
            "effort": self.effort,
            "system": system,
            "prompt": prompt,
        }
        try:
            proc = subprocess.run(
                self._args(exe, system, schema),
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            entry.update(error=f"timeout after {self.timeout}s", duration_s=round(time.monotonic() - started, 1))
            _write_log(self.log_path, entry)
            raise LLMError("failed", f"timeout after {self.timeout}s")

        entry["duration_s"] = round(time.monotonic() - started, 1)
        entry["returncode"] = proc.returncode
        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError:
            entry.update(error="non-JSON output", stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:])
            _write_log(self.log_path, entry)
            raise LLMError(self._classify(proc.stdout + proc.stderr), "non-JSON output from claude")

        entry.update(
            is_error=response.get("is_error"),
            result=response.get("result"),
            structured_output=response.get("structured_output"),
            usage=response.get("usage"),
            duration_ms=response.get("duration_ms"),
        )
        if proc.stderr:
            entry["stderr"] = proc.stderr[-2000:]

        if response.get("is_error") or proc.returncode != 0:
            entry["error"] = "is_error"
            _write_log(self.log_path, entry)
            message = str(response.get("result") or proc.stderr)
            raise LLMError(self._classify(message), message[:300])

        output = response.get("structured_output")
        if not isinstance(output, dict):
            entry["error"] = "missing structured_output"
            _write_log(self.log_path, entry)
            raise LLMError("failed", "no structured_output in response")

        _write_log(self.log_path, entry)
        return output

    @staticmethod
    def _classify(message: str) -> str:
        lowered = message.lower()
        return "not_logged_in" if any(h in lowered for h in _LOGIN_HINTS) else "failed"


class FakeLLM:
    """SIMULATION FOR TESTS ONLY. Returns canned output shaped by the requested schema.

    Pass `handler(system, prompt, schema) -> dict` to control responses. Every call is
    recorded in `calls` so tests can inspect prompts.
    """

    def __init__(self, handler: Callable[[str, str, dict], dict] | None = None):
        self.handler = handler or self.default_handler
        self.calls: list[dict] = []
        self._lock = Lock()

    def complete(self, system: str, prompt: str, schema: dict) -> dict:
        with self._lock:
            self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        return self.handler(system, prompt, schema)

    @staticmethod
    def default_handler(system: str, prompt: str, schema: dict) -> dict:
        props = schema.get("properties", {})

        def count(name: str, default: int) -> int:
            return props[name].get("minItems", default)

        if "seeds" in props:
            return {
                "obvious": [f"Obvious move {i + 1}" for i in range(count("obvious", 3))],
                "seeds": [{"title": f"Fake seed {i + 1}", "text": "Simulated seed."} for i in range(count("seeds", 3))],
            }
        if "pushed" in props:
            ids = re.findall(r"^- \[([^\]]+)\]", prompt, flags=re.M)
            return {"pushed": [
                {"id": ids[i] if i < len(ids) else "", "title": f"Pushed idea {i + 1}", "text": "Simulated push.",
                 "how": "made it bolder"}
                for i in range(count("pushed", 2))
            ]}
        if "ideas" in props:
            item_props = props["ideas"]["items"]["properties"]
            n = count("ideas", 2)
            if "technique" in item_props:  # single prompt
                keys = item_props["technique"].get("enum", ["scamper"])
                return {"ideas": [
                    {"title": f"Fake idea {i + 1}", "text": "Simulated idea.", "technique": keys[i % len(keys)]}
                    for i in range(n)
                ]}
            seed_ids = re.findall(r"^- \[([^\]]+)\]", prompt, flags=re.M)
            return {"ideas": [
                {"title": f"Fake draft {i + 1}", "text": "Simulated draft.", "built_on": seed_ids[i:i + 2],
                 "how": "fuses two seeds"}
                for i in range(n)
            ]}
        return {"idea": {"title": "Fake idea", "text": "Simulated idea.", "built_on": [], "how": ""}}
