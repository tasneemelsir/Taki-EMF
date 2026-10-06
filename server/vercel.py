"""
vercel.py
=========
What is different when Taki runs on Vercel (README, "Publishing on Vercel").

Vercel keeps no server running. It puts the application in a function, starts that
when someone opens the site and freezes it between requests, on a disk that cannot
be written to. Its entrance is app.py beside requirements.txt, which calls the two
functions below around loading the application:

    prepare()    before the settings are read: the settings that follow from Vercel
    adapt(app)   afterwards: believe Vercel's front door about the visitor, and refuse
                 to work without an online database

Nothing here runs anywhere else. On a computer and in the Docker image Taki starts
with run.py, which never loads app.py.
"""

from __future__ import annotations

import os
from typing import Dict, Mapping, MutableMapping, Optional

NO_DATABASE = """Taki is on Vercel, but it has no database yet.

Vercel keeps nothing on the server's own disk, so accounts and projects need an
online database. Neon and Supabase both have a free one.

  1. In Vercel, open this project, then Settings, then Environment Variables.
  2. Add DATABASE_URL, with the connection string of the database as its value.
  3. Open Deployments and choose Redeploy on the newest one.

The steps in full: README, "Publishing on Vercel".
"""


def settings(env: Mapping[str, str]) -> Dict[str, str]:
    """The settings that follow from running on Vercel. A value somebody set is never replaced."""
    out = {
        # A function has one processor: more maths threads would only wait on each other
        # (the Dockerfile has the measurement).
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        # Every address Vercel gives a site is HTTPS.
        "TAKI_SECURE_COOKIES": "1",
        # The program's own folder is read-only. /tmp is the one place that is not, and it is
        # emptied whenever the function is started afresh: fit for a font cache, not for projects.
        "TAKI_DATA_DIR": "/tmp/taki",
        "MPLCONFIGDIR": "/tmp/matplotlib",
    }
    # Vercel's own database integrations call the connection string POSTGRES_URL.
    if not (env.get("TAKI_DATABASE_URL") or env.get("DATABASE_URL")) and env.get("POSTGRES_URL"):
        out["TAKI_DATABASE_URL"] = env["POSTGRES_URL"]
    # Share links and e-mailed links carry the lasting address of the site. Every deployment
    # also has an address of its own, which goes on running that deployment's old code.
    site = (env.get("VERCEL_PROJECT_PRODUCTION_URL") or "").strip().strip("/")
    if site and env.get("VERCEL_ENV", "production") == "production":
        out["TAKI_PUBLIC_URL"] = site if "://" in site else "https://" + site
    return {name: value for name, value in out.items() if not env.get(name)}


def prepare(env: Optional[MutableMapping[str, str]] = None) -> Dict[str, str]:
    """Put those settings in place. Call it before server.config is loaded; returns what it set."""
    env = os.environ if env is None else env
    added = settings(env)
    env.update(added)
    return added


class NeedsDatabase:
    """Answers every request by saying what is missing, instead of keeping accounts where they vanish."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = NO_DATABASE.encode("utf-8")
        await send({"type": "http.response.start", "status": 503,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                (b"content-length", str(len(body)).encode("ascii")),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": b"" if scope.get("method") == "HEAD" else body})


def adapt(app) -> None:
    """Fit the loaded application to Vercel. Call it once, before the first request."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    from . import config

    # A function is only ever reached through Vercel's front door, which writes the visitor's
    # address and "https" into the X-Forwarded headers itself, over anything a visitor sent.
    # Without this every visitor would look like one address, and share one sign-in limit.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    if not config.DATABASE_URL:
        app.add_middleware(NeedsDatabase)          # added last, so it answers first
