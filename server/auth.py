"""
auth.py
=======
Accounts and sign-in sessions.

  * Passwords are stored as scrypt hashes with a per-user random salt.
  * A session is a random token kept in an HttpOnly, SameSite=Lax cookie; the
    database stores only its SHA-256, so a leaked database cannot be replayed.
  * "Guest" accounts let someone try the app without registering. A guest's
    projects are kept on the server and move with them if they later create an
    account from the same browser.
  * Sign-in attempts are rate-limited per address and per email.

  * "Forgot password" makes a one-hour, single-use link. It is emailed when a
    mail server is configured (server/mailer.py); otherwise it is printed in the
    server window. An administrator can also set a password directly with
    python run.py reset-password <email>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

from . import config, db

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
MIN_PASSWORD = 8


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                        dklen=32)
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N, SCRYPT_R, SCRYPT_P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, dk = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n),
                              r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def check_password_strength(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Use a password of at least {MIN_PASSWORD} characters.")
    if len(password) > 200:
        raise AuthError("That password is too long.")
    if password.lower() in ("password", "12345678", "123456789", "qwertyuiop", "password1"):
        raise AuthError("That password is too easy to guess.")


# -------------------------------------------------------------- rate limiting
_attempts: Dict[str, list] = {}
_attempts_lock = threading.Lock()
WINDOW_S, MAX_ATTEMPTS = 600, 8


def _throttle(key: str, limit: int = MAX_ATTEMPTS) -> None:
    t = time.time()
    with _attempts_lock:
        hits = [h for h in _attempts.get(key, []) if t - h < WINDOW_S]
        if len(hits) >= limit:
            _attempts[key] = hits
            raise AuthError("Too many attempts. Wait a few minutes and try again.", 429)
        hits.append(t)
        _attempts[key] = hits
        if len(_attempts) > 5000:
            for k in list(_attempts)[:1000]:
                _attempts.pop(k, None)


def _clear_throttle(key: str) -> None:
    with _attempts_lock:
        _attempts.pop(key, None)


# -------------------------------------------------------------------- users
def _user_out(r) -> dict:
    try:
        prefs = json.loads(r["prefs"] or "{}")
    except ValueError:
        prefs = {}
    return {"id": r["id"], "email": r["email"], "name": r["name"],
            "organisation": r["organisation"], "is_guest": bool(r["is_guest"]),
            "prefs": prefs, "created_at": r["created_at"]}


def get_user(user_id: str) -> Optional[dict]:
    r = db.conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_out(r) if r else None


def create_guest() -> dict:
    if not config.ALLOW_GUESTS:
        raise AuthError("Guest access is switched off on this server.", 403)
    uid, t = db.new_id(), db.now()
    db.conn().execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES (?,?,1,?,?)",
                      (uid, "Guest", t, t))
    return get_user(uid)  # type: ignore[return-value]


# The desktop version has one account: the person at that computer. Nobody signs in to it,
# so it has no email and no password (server/desktop.py).
DESKTOP_USER_ID = "desktop"


def desktop_user(name: str = "") -> dict:
    """The account of the desktop version, made the first time it is asked for."""
    c = db.conn()
    r = c.execute("SELECT * FROM users WHERE id = ?", (DESKTOP_USER_ID,)).fetchone()
    if r is None:
        t = db.now()
        try:
            c.execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES (?,?,0,?,?)",
                      (DESKTOP_USER_ID, (name or "").strip()[:80] or "User", t, t))
        except db.IntegrityError:                    # two windows opened in the same instant
            pass
        r = c.execute("SELECT * FROM users WHERE id = ?", (DESKTOP_USER_ID,)).fetchone()
    return _user_out(r)


def register(email: str, password: str, name: str = "", organisation: str = "",
             upgrade_user_id: Optional[str] = None, client: str = "") -> dict:
    if not config.ALLOW_SIGNUP:
        raise AuthError("New accounts are switched off on this server.", 403)
    _throttle(f"reg:{client}")
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    check_password_strength(password)
    name = (name or "").strip()[:80] or email.split("@")[0]
    organisation = (organisation or "").strip()[:120]
    c = db.conn()
    if c.execute("SELECT 1 AS n FROM users WHERE email = ?", (email,)).fetchone():
        raise AuthError("An account with that email already exists. Sign in instead.", 409)
    t = db.now()
    pw = hash_password(password)
    if upgrade_user_id:
        r = c.execute("SELECT is_guest FROM users WHERE id = ?", (upgrade_user_id,)).fetchone()
        if r and r["is_guest"]:
            try:
                c.execute("UPDATE users SET email = ?, name = ?, organisation = ?, password_hash = ?, "
                          "is_guest = 0, last_seen = ? WHERE id = ?",
                          (email, name, organisation, pw, t, upgrade_user_id))
            except db.IntegrityError:
                raise AuthError("An account with that email already exists. Sign in instead.", 409)
            return get_user(upgrade_user_id)  # type: ignore[return-value]
    uid = db.new_id()
    try:
        c.execute("INSERT INTO users (id, email, name, organisation, password_hash, is_guest, created_at, "
                  "last_seen) VALUES (?,?,?,?,?,0,?,?)", (uid, email, name, organisation, pw, t, t))
    except db.IntegrityError:               # two sign-ups with the same email at the same moment
        raise AuthError("An account with that email already exists. Sign in instead.", 409)
    return get_user(uid)  # type: ignore[return-value]


def login(email: str, password: str, client: str = "") -> dict:
    email = (email or "").strip().lower()
    _throttle(f"ip:{client}")
    _throttle(f"em:{email}")
    r = db.conn().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # Verify against a dummy hash when the account does not exist, so the two cases take the same time.
    ok = verify_password(password or "", r["password_hash"] if r else _DUMMY_HASH)
    if not r or not ok:
        raise AuthError("That email and password do not match.", 401)
    _clear_throttle(f"em:{email}")
    db.conn().execute("UPDATE users SET last_seen = ? WHERE id = ?", (db.now(), r["id"]))
    return _user_out(r)


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def update_profile(user_id: str, name: Optional[str] = None, organisation: Optional[str] = None,
                   prefs: Optional[dict] = None) -> dict:
    c = db.conn()
    if name is not None:
        c.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip()[:80] or "User", user_id))
    if organisation is not None:
        c.execute("UPDATE users SET organisation = ? WHERE id = ?", (organisation.strip()[:120], user_id))
    if prefs is not None:
        cur = get_user(user_id) or {"prefs": {}}
        merged = dict(cur["prefs"]); merged.update({k: v for k, v in prefs.items() if len(str(k)) < 40})
        blob = json.dumps(merged)
        if len(blob) < 8000:
            c.execute("UPDATE users SET prefs = ? WHERE id = ?", (blob, user_id))
    return get_user(user_id)  # type: ignore[return-value]


def change_password(user_id: str, current: str, new: str) -> None:
    r = db.conn().execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not r or not verify_password(current or "", r["password_hash"]):
        raise AuthError("The current password is not correct.", 401)
    check_password_strength(new)
    db.conn().execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))


def admin_set_password(email: str, new: str) -> bool:
    check_password_strength(new)
    cur = db.conn().execute("UPDATE users SET password_hash = ? WHERE email = ?",
                            (hash_password(new), email.strip().lower()))
    if cur.rowcount:
        db.conn().execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = ?)",
                          (email.strip().lower(),))
    return cur.rowcount > 0


def delete_account(user_id: str, password: Optional[str]) -> None:
    r = db.conn().execute("SELECT password_hash, is_guest FROM users WHERE id = ?", (user_id,)).fetchone()
    if not r:
        return
    if not r["is_guest"] and not verify_password(password or "", r["password_hash"]):
        raise AuthError("The password is not correct.", 401)
    db.conn().execute("DELETE FROM users WHERE id = ?", (user_id,))


# ----------------------------------------------------------------- sessions
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: str, user_agent: str = "") -> Tuple[str, float]:
    token = secrets.token_urlsafe(32)
    t = db.now()
    exp = t + config.SESSION_DAYS * 86400
    db.conn().execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at, user_agent) "
                      "VALUES (?,?,?,?,?)", (_hash_token(token), user_id, t, exp, user_agent[:200]))
    return token, exp


def user_for_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    c = db.conn()
    th = _hash_token(token)
    r = c.execute("SELECT s.expires_at AS session_expires, u.* FROM sessions s "
                  "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (th,)).fetchone()
    if not r:
        return None
    t = db.now()
    if r["session_expires"] < t:
        c.execute("DELETE FROM sessions WHERE token_hash = ?", (th,))
        return None
    # sliding expiry, written at most once an hour
    if r["session_expires"] - t < config.SESSION_DAYS * 86400 - 3600:
        c.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                  (t + config.SESSION_DAYS * 86400, th))
        c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (t, r["id"]))
    return _user_out(r)


def end_session(token: Optional[str]) -> None:
    if token:
        db.conn().execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))


def end_other_sessions(user_id: str, keep_token: Optional[str]) -> None:
    keep = _hash_token(keep_token) if keep_token else ""
    db.conn().execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, keep))


# ----------------------------------------------------------- password reset
RESET_MINUTES = 60


def start_password_reset(email: str, client: str = "") -> Optional[Tuple[dict, str]]:
    """
    Make a reset link for the account with this email. Returns (user, token), or
    None when there is no such account - the caller answers the visitor the same
    way in both cases, so the form cannot be used to find out who has an account.
    """
    email = (email or "").strip().lower()
    _throttle(f"fp:{client}")
    _throttle(f"fpe:{email}", limit=3)             # nobody's inbox gets flooded
    c = db.conn()
    r = c.execute("SELECT * FROM users WHERE email = ? AND is_guest = 0", (email,)).fetchone()
    if not r:
        return None
    token, t = secrets.token_urlsafe(32), db.now()
    c.execute("DELETE FROM password_resets WHERE user_id = ?", (r["id"],))
    c.execute("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
              (_hash_token(token), r["id"], t, t + RESET_MINUTES * 60))
    return _user_out(r), token


def finish_password_reset(token: str, new: str, client: str = "") -> dict:
    """Set the new password, end every sign-in of that account and use the link up."""
    _throttle(f"rp:{client}", limit=20)
    c = db.conn()
    r = c.execute("SELECT user_id, expires_at FROM password_resets WHERE token_hash = ?",
                  (_hash_token(token or ""),)).fetchone()
    if not r or r["expires_at"] < db.now():
        raise AuthError("That reset link has expired or was already used. Ask for a new one.", 400)
    check_password_strength(new)
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), r["user_id"]))
    c.execute("DELETE FROM password_resets WHERE user_id = ?", (r["user_id"],))
    c.execute("DELETE FROM sessions WHERE user_id = ?", (r["user_id"],))
    return get_user(r["user_id"])  # type: ignore[return-value]


# -------------------------------------------------------------- housekeeping
def purge_expired() -> None:
    """Remove expired sessions and reset links, and guests idle for 30 days with no sign-in left."""
    c = db.conn()
    t = db.now()
    c.execute("DELETE FROM sessions WHERE expires_at < ?", (t,))
    c.execute("DELETE FROM password_resets WHERE expires_at < ?", (t,))
    c.execute("DELETE FROM users WHERE is_guest = 1 AND last_seen < ? AND id NOT IN "
              "(SELECT user_id FROM sessions)", (t - 30 * 86400,))


def list_users() -> list:
    """Accounts with their project counts, newest first (for `python run.py users`)."""
    rows = db.conn().execute(
        "SELECT u.email, u.name, u.organisation, u.created_at, u.last_seen, "
        "(SELECT COUNT(*) FROM projects p WHERE p.user_id = u.id) AS projects "
        "FROM users u WHERE u.is_guest = 0 ORDER BY u.created_at DESC").fetchall()
    return [dict(r) for r in rows]
