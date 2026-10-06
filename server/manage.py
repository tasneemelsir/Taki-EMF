"""
manage.py
=========
The housekeeping commands behind `python run.py <command>`:

    setup-db          connect an online database (asks for the connection string,
                      tests it, creates the tables, offers to copy what is on this
                      computer, and saves the setting in .env)
    check-db          test the database Taki is set to use
    copy-db [FILE]    copy a local SQLite file into the online database
    use-local-db      go back to the file on this computer
    users             list the accounts
    reset-password E  set a new password for the account with email E

Each function returns a process exit code (0 = fine).
"""

from __future__ import annotations

import getpass
import os
import re
import time
from typing import Optional
from urllib.parse import quote

from . import config, db

PLACEHOLDER = re.compile(r"\[YOUR[-_ ]PASSWORD\]|<password>|YOUR_PASSWORD", re.I)

GUIDE = """
  Taki keeps accounts and projects in a file on this computer until you give it
  an online PostgreSQL database. You do not write any SQL: Taki creates its own
  tables. Any provider works; these two have free plans.

    Supabase   supabase.com  ->  New project (choose a database password)
               ->  "Connect" at the top  ->  Session pooler  ->  copy the URI

    Neon       neon.com  ->  New project  ->  "Connect"  ->  copy the connection string

  The string starts with  postgresql://  and contains your database password.
"""


# --------------------------------------------------------------- .env editing
ENV_NOTE = "# Online database (written by: python run.py setup-db)"


def _n(count: int, word: str) -> str:
    """ "1 account", "3 accounts" """
    return f"{count} {word}{'' if count == 1 else 's'}"


def _write_env(key: str, value: Optional[str]) -> None:
    """Set KEY=value in .env (value None removes it), leaving every other line as it is."""
    lines = []
    if os.path.isfile(config.ENV_FILE):
        with open(config.ENV_FILE, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    out, done = [], False
    for line in lines:
        if line.strip() == ENV_NOTE:
            continue
        name = line.split("=", 1)[0].strip().lstrip("#").strip()
        if name in (key, "TAKI_" + key) and "=" in line:
            if value is not None and not done and not line.lstrip().startswith("#"):
                out += [ENV_NOTE, f"{key}={value}"]
                done = True
            elif line.lstrip().startswith("#"):
                out.append(line)                     # an explanatory comment: keep it
            continue
        out.append(line)
    if value is not None and not done:
        if out and out[-1].strip():
            out.append("")
        out += [ENV_NOTE, f"{key}={value}"]
    with open(config.ENV_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip("\n") + "\n")
    try:
        os.chmod(config.ENV_FILE, 0o600)             # it holds a password
    except OSError:
        pass


# ------------------------------------------------------- connection strings
def tidy_url(raw: str, password: Optional[str] = None) -> str:
    """
    Clean up a pasted connection string: quotes and spaces, the short postgres://
    form, a [YOUR-PASSWORD] placeholder, and sslmode=require for anything that is
    not on this computer. Returns "" if it is not a PostgreSQL address.
    """
    url = (raw or "").strip().strip('"').strip("'").strip()
    # what the providers' "Connect" boxes actually hand out: psql '...', export NAME="...", NAME=...
    for lead in ("psql ", "export ", "set "):
        if url.lower().startswith(lead):
            url = url[len(lead):].strip()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", url) and not url.lower().startswith("postgres"):
        url = url.split("=", 1)[1].strip()
    url = url.strip().strip('"').strip("'").strip()
    found = re.search(r"postgres(?:ql)?://\S+", url)
    if found:                                     # anything else on the line (flags, a trailing quote) is dropped
        url = found.group(0).rstrip("'\";")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        return ""
    if password is not None:
        url = PLACEHOLDER.sub(lambda _m: quote(password, safe=""), url)
    host = url.rsplit("@", 1)[-1].split("/", 1)[0].lower()
    local = host.startswith(("localhost", "127.0.0.1", "[::1]"))
    if not local and "sslmode=" not in url:
        url += ("&" if "?" in url.rsplit("/", 1)[-1] else "?") + "sslmode=require"
    return url


def _explain(url: str, exc: Exception) -> str:
    """A connection failure in plain words, with the fix where there is a usual one."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    low = str(exc).lower()
    host = url.rsplit("@", 1)[-1].split("/", 1)[0].lower()
    if re.match(r"db\.[a-z0-9]+\.supabase\.co", host) and any(
            k in low for k in ("network is unreachable", "could not translate", "no route", "timeout",
                               "name or service not known", "nodename nor servname", "getaddrinfo")):
        return (f"{text}\n  This is Supabase's DIRECT address, which only works on IPv6 networks.\n"
                "  In Supabase click \"Connect\" and copy the \"Session pooler\" string instead.")
    if "password authentication failed" in low or "wrong password" in low:
        return (f"{text}\n  The database password in the string is not right. It is the password you chose when\n"
                "  you created the database project (not your website sign-in). Supabase: Project Settings ->\n"
                "  Database -> Reset database password.")
    if "tenant or user not found" in low:
        return (f"{text}\n  The pooler does not know this project: copy the string again from \"Connect\"\n"
                "  (the user name must look like  postgres.abcdefghijklmnop ).")
    if any(k in low for k in ("could not translate host", "name or service not known", "getaddrinfo",
                              "nodename nor servname")):
        return f"{text}\n  The host name was not found. Check the string was copied whole, and your internet connection."
    if "timeout" in low or "timed out" in low:
        return (f"{text}\n  No answer from the database. If it is a free Supabase project that has not been used\n"
                "  for a week it is paused: open the Supabase dashboard and press \"Restore project\".")
    return text


def _drain_keys() -> None:
    """
    Throw away keystrokes typed (or pasted) ahead of a question. A pasted
    connection string often ends in more than one line break; the extra one would
    answer the next question, or close the window, before it could be read.
    """
    try:
        import msvcrt                                     # Windows
        while msvcrt.kbhit():
            msvcrt.getwch()
    except ImportError:
        try:
            import sys
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:
            pass
    except Exception:
        pass


def test_url(url: str) -> dict:
    """Connect, create Taki's tables if they are missing, and count what is there."""
    previous = config.DATABASE_URL
    config.set_database_url(url)
    db.reset_for_tests()
    try:
        t0 = time.time()
        db.conn()
        got = db.counts()
        version = db.scalar("SELECT version() AS n")
        return {"ok": True, "counts": got, "ms": (time.time() - t0) * 1000.0,
                "version": str(version).split(" on ")[0]}
    except Exception as exc:
        config.set_database_url(previous)
        db.reset_for_tests()
        return {"ok": False, "error": _explain(url, exc)}


# ------------------------------------------------------------------ commands
def setup_db(url: Optional[str] = None, assume_yes: bool = False) -> int:
    interactive = url is None
    print("\n  Taki - connect an online database\n  ---------------------------------")
    if interactive:
        print(GUIDE)
        if db.is_postgres():
            print(f"  Taki is already set to use an online database ({db.provider()}).\n"
                  "  Paste a new string to replace it, or press Enter to keep it.\n")
        try:
            url = input("  Paste the connection string here and press Enter:\n  > ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not url.strip():
            print("  Nothing changed.")
            return 0
    password = None
    if PLACEHOLDER.search(url or ""):
        if not interactive:
            print("  The string still contains the [YOUR-PASSWORD] placeholder. Put the database password there.")
            return 2
        print("\n  The string still has the [YOUR-PASSWORD] placeholder.")
        password = getpass.getpass("  Type the database password (it is not shown): ")
    clean = tidy_url(url or "", password)
    if not clean:
        print("  That does not look like a PostgreSQL connection string (it should start with postgresql://).")
        return 2

    print(f"\n  Connecting to {db.provider(clean)} ...")
    result = test_url(clean)
    if not result["ok"]:
        print(f"  Could not connect: {result['error']}\n  Nothing was changed.")
        return 1
    got = result["counts"]
    print(f"  Connected in {result['ms']:.0f} ms ({result['version']}). Tables are ready: "
          f"{_n(got['users'], 'account')}, {_n(got['projects'], 'project')} there now.")

    local = _local_counts()
    if local and (local["users"] or local["projects"]):
        ask = (f"\n  This computer has {_n(local['users'], 'account')} and {_n(local['projects'], 'project')} "
               "in its local file.\n"
               "  Copy them to the online database? [Y/n] ")
        if interactive and not assume_yes:
            _drain_keys()
        answer = "y" if assume_yes else (input(ask).strip().lower() if interactive else "n")
        if answer in ("", "y", "yes"):
            copied = db.copy_from_sqlite(config.DB_PATH)
            print("  Copied: " + ", ".join(f"{n} {t.replace('_', ' ')}" for t, n in copied.items() if n) + "."
                  if any(copied.values()) else "  Everything was already there.")

    _write_env("DATABASE_URL", clean)
    print(f"\n  CONNECTED. Taki now keeps accounts and projects in {db.provider(clean)}.\n"
          f"  The setting is saved in {config.ENV_FILE}\n\n"
          "  How to see that it is in use, at any time:\n"
          "    - when Taki starts, its window says  \"Accounts and projects: online database\"\n"
          "    - in the app: Settings > About & limits > Database\n"
          "    - or run  check-database  (check-database.bat on Windows)\n\n"
          "  To go back to the file on this computer:  python run.py use-local-db\n")
    if interactive:
        _drain_keys()
    return 0


def _local_counts() -> Optional[dict]:
    if not os.path.isfile(config.DB_PATH):
        return None
    import sqlite3
    try:
        con = sqlite3.connect(config.DB_PATH)
        try:
            return {"users": con.execute("SELECT COUNT(*) FROM users WHERE is_guest = 0").fetchone()[0],
                    "projects": con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]}
        finally:
            con.close()
    except sqlite3.Error:
        return None


def use_local_db() -> int:
    _write_env("DATABASE_URL", None)
    print(f"  Taki will use the file on this computer again ({config.DB_PATH}).\n"
          "  The online database was not changed or deleted.")
    return 0


def check_db() -> int:
    try:
        db.conn()
        got = db.counts()
    except Exception as exc:
        print(f"Could not use the database: {_explain(config.DATABASE_URL, exc)}")
        return 1
    where = f"online, {db.provider()}" if db.is_postgres() else config.DB_PATH
    print(f"Database OK ({db.backend_name()}, {where}): {_n(got['users'], 'account')}, "
          f"{_n(got['projects'], 'project')}, {_n(got['scenarios'], 'saved scenario')}.")
    return 0


def copy_db(path: Optional[str] = None) -> int:
    if not db.is_postgres():
        print("Connect the online database first:  python run.py setup-db")
        return 2
    src = path or config.DB_PATH
    try:
        copied = db.copy_from_sqlite(src)
    except FileNotFoundError:
        print(f"No SQLite file at {src}.")
        return 1
    except Exception as exc:
        print(f"Copy failed: {_explain(config.DATABASE_URL, exc)}")
        return 1
    print(f"Copied into {db.provider()}: " + ", ".join(f"{n} {t.replace('_', ' ')}" for t, n in copied.items()) + ".")
    return 0


def users() -> int:
    from . import auth
    rows = auth.list_users()
    if not rows:
        print("No accounts yet.")
        return 0
    print(f"{'email':38s} {'name':22s} {'projects':>8s}  {'created':10s}  last seen")
    for r in rows:
        day = lambda t: time.strftime("%Y-%m-%d", time.localtime(t))        # noqa: E731
        print(f"{(r['email'] or '')[:38]:38s} {r['name'][:22]:22s} {r['projects']:8d}  "
              f"{day(r['created_at'])}  {day(r['last_seen'])}")
    print(_n(len(rows), "account") + ".")
    return 0


def reset_password(email: Optional[str]) -> int:
    from . import auth
    if not email:
        print("Usage: python run.py reset-password EMAIL")
        return 2
    pw = getpass.getpass("New password: ")
    if pw != getpass.getpass("Repeat: "):
        print("The two entries do not match.")
        return 1
    try:
        ok = auth.admin_set_password(email, pw)
    except auth.AuthError as exc:
        print(exc)
        return 1
    print("Password updated; that account's sign-ins were ended." if ok else "No account with that email.")
    return 0 if ok else 1
