"""Try the agents from the terminal, without the web app.

    python -m whatelse.try "What are you trying to figure out?" --context "optional notes"

Runs a real Generate through `claude -p` and prints the ideas. Nothing is stored
except the private agent-call log.
"""

from __future__ import annotations

import argparse
import sys
import time

from whatelse.config import load_settings
from whatelse.context import AgentContext
from whatelse.llm import ClaudeCLI, LLMError
from whatelse.orchestrator import PATTERNS, generate, load_techniques, technique_label


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="python -m whatelse.try", description=__doc__.splitlines()[0])
    parser.add_argument("statement", help="the challenge, in a few sentences")
    parser.add_argument("--context", default=None, help="optional background")
    parser.add_argument("--pattern", choices=PATTERNS, default=None, help="defaults to config.toml")
    parser.add_argument("--effort", default=None, help="override config.toml (low, medium, high, ...)")
    args = parser.parse_args()

    settings = load_settings()
    effort = args.effort or settings.effort
    llm = ClaudeCLI(model=settings.model, timeout=settings.timeout_seconds,
                    log_path=settings.log_path, effort=effort)
    techniques = load_techniques(settings.techniques)

    print(f"The agents are working… (pattern: {args.pattern or settings.pattern}, effort: {effort or 'CLI default'})\n")
    started = time.monotonic()
    try:
        result = generate(AgentContext(args.statement, args.context), llm, settings, args.pattern)
    except LLMError as exc:
        print(f"{exc.user_message}\n  detail: {exc.detail}\n  log: {settings.log_path}")
        return 1
    elapsed = time.monotonic() - started

    for i, idea in enumerate(result.ideas, start=1):
        print(f"{i}. [{technique_label(idea.techniques, techniques)}]")
        print(f"   {idea.title}")
        print(f"   {idea.text}")
        if idea.how:
            print(f"   built on: {', '.join(idea.built_on)} ({idea.how})")
        print()

    data = result.data
    seeds = len(data.get("seeds", []))
    print(f"{len(result.ideas)} ideas in {elapsed:.0f}s" + (f" from {seeds} seeds" if seeds else ""))
    if data.get("drafts"):
        fused = sum(d["fused_two_techniques"] for d in data["drafts"])
        print(f"Drafts fusing two or more other techniques: {fused}/{len(data['drafts'])}; "
              f"pushed in round 3: {len(data.get('pushes', []))}")
    if data.get("banned"):
        print(f"Banned obvious moves: {'; '.join(data['banned'])}")
    for name in ("round1_failures", "round3_failures"):
        if data.get(name):
            print(f"{name.replace('_', ' ')}: {', '.join(f['technique'] for f in data[name])}")
    print(f"Agent-call log: {settings.log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
