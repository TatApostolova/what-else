"""`python -m whatelse`: start the local server and open the browser."""

from __future__ import annotations

import argparse
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import uvicorn

from whatelse.config import code_fingerprint, load_settings
from whatelse.web import create_app

HOST, PORT = "127.0.0.1", 8000


def already_running(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def replace_stale_copy(url: str, port: int) -> bool:
    """If an older version is running, ask it to stop. True means the port is now free."""
    try:
        running = urllib.request.urlopen(f"{url}/_version", timeout=2).read().decode()
    except (urllib.error.URLError, OSError):
        running = ""  # a copy from before versioning existed, or something else on the port
    if running == code_fingerprint():
        return False
    try:
        body = urllib.parse.urlencode({"token": running}).encode()
        urllib.request.urlopen(f"{url}/_shutdown", data=body, timeout=5)
    except (urllib.error.URLError, OSError) as exc:
        print(f"An older copy of What Else? is running and couldn't be replaced ({exc}). "
              "Close its window and start again.")
        return False
    deadline = time.monotonic() + 10
    while already_running(port) and time.monotonic() < deadline:
        time.sleep(0.25)
    return not already_running(port)


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
    parser.add_argument("--host", default=HOST, help=f"address to listen on (default {HOST}; 0.0.0.0 when hosted)")
    args = parser.parse_args()

    url = f"http://{HOST}:{args.port}"
    if already_running(args.port):
        if replace_stale_copy(url, args.port):
            print("Replaced an older running copy with the updated app.")
        else:
            print(f"What Else? is already running at {url}; opening it.")
            if not args.no_browser:
                webbrowser.open(url)
            return

    settings = load_settings()
    app = create_app(settings)
    print(f"What Else? is running at {url} (data: {settings.db_path}). Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url, args.port), daemon=True).start()
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="warning"))
    app.state.server = server
    server.run()


if __name__ == "__main__":
    main()
