#!/usr/bin/env python3
"""
Local verification launcher — boots the CorpBrain backend so a human can click through it.

This is a DEVELOPER TOOL, not the shipped shell. The shipped entry point is pywebview +
WebView2 packaged by PyInstaller (DEC-01); this script exists only so the API and the built
SPA can be inspected in a normal browser during development. It is deliberately excluded
from the PyInstaller bundle.

It replaces `run_app.py`, which is registered as CORE #4 and #5 in
docs/loop/DECISION_LOG.md: that file shells out to `npx vite preview` (putting a Node
runtime in the run path, DEC-01) and hardcodes port 8000 plus the literal session token
"corpbrain_dev_session_token_12345" (DEC-02). Both are avoided here:

- **Port**: `port=0`, so the OS assigns it. The real port is read back from the bound socket
  after startup and printed. Nothing is hardcoded, and two instances cannot collide.
- **Token**: `secrets.token_urlsafe(32)`, generated fresh on every boot by `create_app`.
  It is printed to this console only — never written to a file, an env var, or a log
  (DEC-02). Closing the terminal is enough to invalidate it.
- **No Node**: the prebuilt `dist/` bundle is served by FastAPI's own StaticFiles, so
  `npx`/`vite` are not involved. If `dist/` is missing, the API still comes up.

Usage:
    python scripts/dev_serve.py
    python scripts/dev_serve.py --open      # also open the Swagger UI in a browser
"""

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uvicorn  # noqa: E402  - must follow the sys.path bootstrap above
from fastapi.staticfiles import StaticFiles  # noqa: E402

from src.backend.api.app import create_app  # noqa: E402
from src.backend.db import DatabaseManager  # noqa: E402

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BANNER_WIDTH = 78


def _mount_spa(app) -> bool:
    """
    Serve the prebuilt SPA at / if it exists.

    Mounted last so it cannot shadow /api/v1/* or /docs. The Bearer middleware only guards
    /api/v1/*, so the static assets load without a token — same as the packaged shell, where
    the bundle is read off disk rather than fetched.
    """
    dist_dir = REPO_ROOT / "dist"
    if not (dist_dir / "index.html").is_file():
        return False
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="spa")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Boot the CorpBrain backend for local inspection.")
    parser.add_argument("--open", action="store_true", help="open the Swagger UI in the default browser")
    parser.add_argument("--log-level", default="warning", help="uvicorn log level (default: warning)")
    args = parser.parse_args()

    db_mgr = DatabaseManager()
    app = create_app(db_mgr)          # session_token=None -> secrets.token_urlsafe(32)
    token = app.state.session_token
    spa_mounted = _mount_spa(app)

    # port=0: the OS picks a free port (DEC-02 forbids a hardcoded one).
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level=args.log_level)
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the socket to be bound before reading the assigned port back off it.
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        if not thread.is_alive():
            print("[dev_serve] Server thread exited during startup.", file=sys.stderr)
            return 1
        time.sleep(0.05)

    if not server.started:
        print("[dev_serve] Server did not start within 15s.", file=sys.stderr)
        return 1

    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    print("=" * BANNER_WIDTH)
    print(" CorpBrain — local verification server")
    print("=" * BANNER_WIDTH)
    print(f"  Swagger UI (API 직접 호출)  {base}/docs")
    print(f"  Health (토큰 불필요)         {base}/api/v1/health")
    if spa_mounted:
        print(f"  SPA (정적 목업)              {base}/")
    else:
        print("  SPA                          dist/ 없음 — `npm run build` 후 재실행")
    print()
    print("  Bearer token (이 콘솔에만 출력됩니다):")
    print(f"    {token}")
    print()
    print("  Swagger UI 우측 상단 [Authorize] 에 위 토큰을 붙여넣으면")
    print("  /api/v1/* 엔드포인트를 호출할 수 있습니다.")
    print()
    print(f"  SQLite   {db_mgr.db_path}")
    print(f"  Vectors  {db_mgr.vectors_dir}")
    print("=" * BANNER_WIDTH)
    print("  Ctrl+C 로 종료")
    print()

    if args.open:
        webbrowser.open(f"{base}/docs")

    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\n[dev_serve] Shutting down...")
        server.should_exit = True
        thread.join(timeout=10)

    return 0


if __name__ == "__main__":
    sys.exit(main())
