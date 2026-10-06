"""
config.py
=========
Runtime settings, read from environment variables (or a .env file next to
run.py). Every setting has a default that works for running on one computer.

    TAKI_DATA_DIR         where the SQLite database lives     (./data)
    DATABASE_URL          connection string of an online PostgreSQL database (Supabase,
                          Neon, ...); when set, accounts and projects are kept there
                          instead of in the SQLite file
                          (TAKI_DATABASE_URL does the same and wins if both are set)
    TAKI_HOST             interface to listen on              (127.0.0.1)
    TAKI_PORT             port                                (8000)
    TAKI_ALLOW_SIGNUP     allow new accounts: 1 / 0           (1)
    TAKI_ALLOW_GUESTS     allow "continue as guest": 1 / 0    (1)
    TAKI_SECURE_COOKIES   send cookies over HTTPS only: 1 / 0 (0; set 1 when published)
    TAKI_SESSION_DAYS     how long a sign-in lasts            (30)
    TAKI_MAX_PROJECTS     projects per account                (200)
    TAKI_WORKERS          server processes                    (1)
    TAKI_TRUSTED_PROXIES  proxies whose X-Forwarded-* headers are believed (127.0.0.1)
    TAKI_DB_POOL          connections kept to an online database (5)
    TAKI_PUBLIC_URL       the address people open Taki at, e.g. https://taki.example.org
    TAKI_SMTP_HOST ...    optional email for password-reset links (see server/mailer.py)
    TAKI_ANTHROPIC_API_KEY, TAKI_GEMINI_API_KEY, TAKI_OPENAI_API_KEY
                          optional: a key of YOURS that signed-in users of this copy may
                          use for the AI narrative, at your cost. Leave them unset and
                          each person enters their own key, which stays in their browser.
    TAKI_AI_PER_HOUR      narratives per account per hour on a shared key   (10)
    TAKI_DESKTOP_DOWNLOAD let visitors download the desktop version from this copy: 1 / 0 (1)

`python run.py setup-db` writes DATABASE_URL into .env for you.

The desktop version (python run.py desktop, or the installed app) sets TAKI_DESKTOP=1
itself: one person, no sign-in, everything kept in a folder on that computer. It
ignores the .env file and DATABASE_URL. See server/desktop.py.
"""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path) or os.environ.get("TAKI_IGNORE_ENV_FILE") or os.environ.get("TAKI_DESKTOP"):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_dotenv()


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Set by the desktop launcher before this module is imported (server/desktop.py).
DESKTOP = _flag("TAKI_DESKTOP", False)
DATA_DIR = os.path.abspath(os.environ.get("TAKI_DATA_DIR", os.path.join(ROOT, "data")))
DB_PATH = os.path.join(DATA_DIR, "taki.db")


def _pg_url(v: str) -> str:
    v = (v or "").strip()
    if v.startswith("postgres://"):               # the short form some hosts hand out
        v = "postgresql://" + v[len("postgres://"):]
    return v if v.startswith("postgresql://") else ""


DATABASE_URL = _pg_url(os.environ.get("TAKI_DATABASE_URL") or os.environ.get("DATABASE_URL", ""))
STATIC_DIR = os.path.join(ROOT, "server", "static")
HOST = os.environ.get("TAKI_HOST", "127.0.0.1")
PORT = _int("TAKI_PORT", _int("PORT", 8000))
ALLOW_SIGNUP = _flag("TAKI_ALLOW_SIGNUP", True)
ALLOW_GUESTS = _flag("TAKI_ALLOW_GUESTS", True)
SECURE_COOKIES = _flag("TAKI_SECURE_COOKIES", False)
SESSION_DAYS = _int("TAKI_SESSION_DAYS", 30)
ALLOW_DESKTOP_DOWNLOAD = _flag("TAKI_DESKTOP_DOWNLOAD", True)
MAX_PROJECTS = _int("TAKI_MAX_PROJECTS", 200)
MAX_SCENARIOS = _int("TAKI_MAX_SCENARIOS", 60)
WORKERS = _int("TAKI_WORKERS", 1)
TRUSTED_PROXIES = os.environ.get("TAKI_TRUSTED_PROXIES", "127.0.0.1")
# Keys the operator chooses to share with the people using this copy. Only the TAKI_ names
# are read: a key that happens to be in the environment for some other program is not used.
OPERATOR_AI_KEYS = {
    "anthropic": os.environ.get("TAKI_ANTHROPIC_API_KEY", "").strip(),
    "google": os.environ.get("TAKI_GEMINI_API_KEY", "").strip(),
    "openai": os.environ.get("TAKI_OPENAI_API_KEY", "").strip(),
}
OPERATOR_AI_KEY = OPERATOR_AI_KEYS["anthropic"]
AI_PER_HOUR = _int("TAKI_AI_PER_HOUR", 10)
PUBLIC_URL = os.environ.get("TAKI_PUBLIC_URL", "").strip().rstrip("/")
SMTP_HOST = os.environ.get("TAKI_SMTP_HOST", "").strip()
SMTP_PORT = _int("TAKI_SMTP_PORT", 587)
SMTP_USER = os.environ.get("TAKI_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("TAKI_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("TAKI_SMTP_FROM", "").strip()
SMTP_SECURITY = (os.environ.get("TAKI_SMTP_SECURITY", "starttls").strip().lower() or "starttls")
ENV_FILE = os.path.join(ROOT, ".env")
VERSION = "4.3.4"
COOKIE_NAME = "taki_session"
_WEB = {}


def set_desktop(on: bool) -> None:
    """
    Switch the desktop behaviour on or off: one local person and no sign-in, so no
    accounts and no guests, a session that does not run out while a window stays open
    for weeks, and the file on this computer whatever DATABASE_URL says. Cookies
    belong to a host, not to a port; a name of its own keeps the desktop version and
    a web copy on the same computer from signing each other out.
    """
    global DESKTOP, DATABASE_URL, ALLOW_SIGNUP, ALLOW_GUESTS, SECURE_COOKIES, SESSION_DAYS, COOKIE_NAME
    if not _WEB:                                  # what the settings are without it, to go back to
        _WEB.update(DATABASE_URL=DATABASE_URL, ALLOW_SIGNUP=ALLOW_SIGNUP, ALLOW_GUESTS=ALLOW_GUESTS,
                    SECURE_COOKIES=SECURE_COOKIES, SESSION_DAYS=SESSION_DAYS)
    DESKTOP = bool(on)
    if on:
        DATABASE_URL, ALLOW_SIGNUP, ALLOW_GUESTS, SECURE_COOKIES = "", False, False, False
        SESSION_DAYS, COOKIE_NAME = 3650, "taki_desktop"
    else:
        DATABASE_URL, ALLOW_SIGNUP, ALLOW_GUESTS = _WEB["DATABASE_URL"], _WEB["ALLOW_SIGNUP"], _WEB["ALLOW_GUESTS"]
        SECURE_COOKIES, SESSION_DAYS, COOKIE_NAME = _WEB["SECURE_COOKIES"], _WEB["SESSION_DAYS"], "taki_session"


if DESKTOP:
    set_desktop(True)


def set_data_dir(path: str) -> None:
    """Point the app at another data directory (used by the tests)."""
    global DATA_DIR, DB_PATH
    DATA_DIR = os.path.abspath(path)
    DB_PATH = os.path.join(DATA_DIR, "taki.db")


def set_database_url(url: str) -> None:
    """Use a PostgreSQL database ("" = back to the SQLite file). Used by the tests."""
    global DATABASE_URL
    DATABASE_URL = _pg_url(url)

