"""
run.py - start Taki.

    python run.py                      start the server and open the browser
    python run.py --no-browser         start without opening a browser
    python run.py --host 0.0.0.0       listen on the network (for a server)
    python run.py --workers 2          several processes, for a shared server

    python run.py desktop              the desktop version: its own window, no sign-in,
                                       everything kept on this computer (server/desktop.py)

    python run.py setup-db             connect an online database (Supabase, Neon, ...)
    python run.py check-db             test the database Taki is set to use
    python run.py copy-db [FILE]       copy a local SQLite file into the online database
    python run.py use-local-db         go back to the file on this computer
    python run.py users                list the accounts
    python run.py reset-password EMAIL set a new password for an account
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

COMMANDS = ["serve", "setup-db", "check-db", "copy-db", "use-local-db", "users", "reset-password"]


def main() -> int:
    if sys.argv[1:2] == ["desktop"]:             # before the settings are read: it sets its own
        from server import desktop
        return desktop.main(sys.argv[2:])
    from server import config

    parser = argparse.ArgumentParser(description="Taki - EMF simulation, shielding and digital twin")
    parser.add_argument("command", nargs="?", default="serve", choices=COMMANDS)
    parser.add_argument("argument", nargs="?", help="EMAIL for reset-password, FILE for copy-db")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reload", action="store_true", help="restart when Python files change")
    parser.add_argument("--workers", type=int, default=config.WORKERS,
                        help="number of server processes (use 2-4 on a shared server)")
    parser.add_argument("--url", help="setup-db: the connection string, instead of being asked for it")
    parser.add_argument("--yes", action="store_true", help="setup-db: copy local data without asking")
    args = parser.parse_args()

    if args.command != "serve":
        from server import manage
        if args.command == "setup-db":
            return manage.setup_db(args.url, args.yes)
        if args.command == "check-db":
            return manage.check_db()
        if args.command == "copy-db":
            return manage.copy_db(args.argument)
        if args.command == "use-local-db":
            return manage.use_local_db()
        if args.command == "users":
            return manage.users()
        return manage.reset_password(args.argument)

    try:
        import uvicorn
    except ImportError:
        print("Missing packages. Run:  pip install -r requirements.txt")
        return 1

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    from server import db
    store = (f"online database ({db.provider()})" if db.is_postgres()
             else f"file on this computer ({config.DB_PATH})")
    shared = [p for p, k in config.OPERATOR_AI_KEYS.items() if k]
    print(f"\n  Taki {config.VERSION} is starting at {url}\n  Accounts and projects: {store}\n"
          + (f"  AI narrative: this copy shares ITS OWN key for {', '.join(shared)} with signed-in users.\n"
             if shared else "  AI narrative: each person uses their own key (none is shared by this copy).\n")
          + "  Press Ctrl+C to stop.\n")
    if not args.no_browser and args.host in ("127.0.0.1", "localhost"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    workers = max(1, int(args.workers or 1))
    uvicorn.run("server.main:app", host=args.host, port=args.port, reload=args.reload,
                workers=None if args.reload or workers == 1 else workers,
                proxy_headers=True, forwarded_allow_ips=config.TRUSTED_PROXIES, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
