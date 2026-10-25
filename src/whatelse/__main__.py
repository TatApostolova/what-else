"""`python -m whatelse`: start the local server and open the browser."""

from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser

import uvicorn

from whatelse.config import load_settings
from whatelse.web import create_app

HOST, PORT = "127.0.0.1", 8000


def already_running(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def open_browser_when_ready(url: str, port: int, timeout: float = 20.0) -> None:
    """Open the browser only once the server answers, so the first load never fails."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m whatelse", description="What Else? — local creative studio")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    parser.add_argument("--port", type=int, default=PORT, help=f"port to listen on (default {PORT})")
    args = parser.parse_args()

    url = f"http://{HOST}:{args.port}"
    if already_running(args.port):
        print(f"What Else? is already running at {url}; opening it.")
        if not args.no_browser:
            webbrowser.open(url)
        return

    settings = load_settings()
    app = create_app(settings)
    print(f"What Else? is running at {url} (data: {settings.db_path}). Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url, args.port), daemon=True).start()
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
