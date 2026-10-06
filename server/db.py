"""
db.py
=====
Storage for accounts, sessions, projects and saved scenarios.

Two back ends, one interface:

  * SQLite (default) - one file in the data directory (TAKI_DATA_DIR, ./data).
    Nothing to install or run. Right for one computer.
  * PostgreSQL - when DATABASE_URL (or TAKI_DATABASE_URL) holds a connection
    string, Taki keeps everything in that database instead. This is how a
    published copy uses an online database: Supabase, Neon, Render, Railway,
    AWS RDS ... anything that speaks PostgreSQL. `python run.py setup-db`
    asks for the connection string and does the rest.

Nobody has to write SQL: the tables are created on first use in either case.
This module is the only place that issues SQL; everything else calls the
functions below or `conn().execute(sql, params)` with `?` placeholders, which
are translated for PostgreSQL. Rows can be read by column name on both.

PostgreSQL connections come from a small pool shared by the server's threads
(TAKI_DB_POOL, 5 by default), because hosted databases allow only a handful of
connections on their free plans. Prepared statements are switched off so the
"transaction pooler" addresses those hosts hand out work too. Row-level
security is switched on for Taki's tables, which closes them to the public
REST API that Supabase puts in front of every database; Taki itself connects
as the owner and is not affected.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from . import config

_local = threading.local()
_init_lock = threading.Lock()
_schema_target = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE,
    name          TEXT NOT NULL DEFAULT '',
    organisation  TEXT NOT NULL DEFAULT '',
    password_hash TEXT,
    is_guest      INTEGER NOT NULL DEFAULT 0,
    prefs         TEXT NOT NULL DEFAULT '{}',
    created_at    REAL NOT NULL,
    last_seen     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    config      TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, updated_at);
CREATE TABLE IF NOT EXISTS scenarios (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    config     TEXT NOT NULL,
    summary    TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenarios_project ON scenarios(project_id, created_at);
CREATE TABLE IF NOT EXISTS password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shares (
    token      TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    opened     INTEGER NOT NULL DEFAULT 0
);
"""
TABLES = ("users", "sessions", "projects", "scenarios", "password_resets", "shares")   # parents first
_KEYS = {"users": "id", "sessions": "token_hash", "projects": "id", "scenarios": "id",
         "password_resets": "token_hash", "shares": "token"}
POOL_SIZE = max(1, int(os.environ.get("TAKI_DB_POOL", "5") or 5))
IDLE_S = 240.0            # hosted poolers drop connections idle for ~5 minutes; retire ours first


class IntegrityError(Exception):
    """A unique or foreign-key rule was broken (same meaning on both back ends)."""


def is_postgres() -> bool:
    return bool(config.DATABASE_URL)


def backend_name() -> str:
    return "postgresql" if is_postgres() else "sqlite"


def provider(url: Optional[str] = None) -> str:
    """Who hosts the database, for display: "Supabase", "Neon", ... or "this computer"."""
    url = config.DATABASE_URL if url is None else url
    if not url:
        return "this computer"
    host = url.rsplit("@", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()
    for key, name in (("supabase", "Supabase"), ("neon.tech", "Neon"), ("render.com", "Render"),
                      ("railway", "Railway"), ("rds.amazonaws", "Amazon RDS"), ("azure", "Azure"),
                      ("aivencloud", "Aiven"), ("cockroachlabs", "CockroachDB")):
        if key in host:
            return name
    if host.startswith(("localhost", "127.0.0.1", "[::1]")):
        return "PostgreSQL on this computer"
    return "PostgreSQL server"


def _target() -> str:
    return config.DATABASE_URL or config.DB_PATH


# ---------------------------------------------------------------- connections
class _SqliteConn:
    def __init__(self):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.raw = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None)
        self.raw.row_factory = sqlite3.Row
        self.raw.execute("PRAGMA journal_mode=WAL")
        self.raw.execute("PRAGMA foreign_keys=ON")
        self.raw.execute("PRAGMA synchronous=NORMAL")

    def execute(self, sql: str, params=()):
        try:
            return self.raw.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc)) from exc

    def script(self, sql: str) -> None:
        self.raw.executescript(sql)

    def begin(self) -> None:
        self.raw.execute("BEGIN IMMEDIATE")

    def end(self) -> None:
        pass

    def close(self) -> None:
        self.raw.close()


class _Rows:
    """A finished query. The rows are already here, so the connection is back in the pool."""
    __slots__ = ("_rows", "_i", "rowcount")

    def __init__(self, rows: list, rowcount: int):
        self._rows, self._i, self.rowcount = rows, 0, rowcount

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        self._i += 1
        return self._rows[self._i - 1]

    def fetchall(self) -> list:
        rest, self._i = self._rows[self._i:], len(self._rows)
        return rest


def _quiet_close(raw) -> None:
    try:
        raw.close()
    except Exception:
        pass


class _PgPool:
    """A few PostgreSQL connections shared by all threads of this process."""

    def __init__(self, url: str, size: int):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:          # pragma: no cover - depends on the installation
            raise RuntimeError("An online database is configured, but its driver is not installed. "
                               "Run:  pip install -r requirements.txt") from exc
        self.psycopg, self._dict_row = psycopg, dict_row
        self.url, self.size = url, size
        self._idle: list = []
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(size)

    def _open(self):
        # autocommit: every statement stands alone unless tx() opens a transaction.
        # prepare_threshold=None: no server-side prepared statements (transaction poolers reject them).
        # client_encoding: a database created without an encoding (SQL_ASCII) would otherwise hand
        # text back as bytes; hosted databases are UTF-8 already, where this changes nothing.
        return self.psycopg.connect(self.url, autocommit=True, row_factory=self._dict_row,
                                    connect_timeout=15, prepare_threshold=None,
                                    application_name="taki", client_encoding="utf8")

    def acquire(self):
        if not self._slots.acquire(timeout=30):
            raise RuntimeError("The database is busy. Try again in a moment.")
        try:
            with self._lock:
                while self._idle:
                    raw, used = self._idle.pop()
                    if not raw.closed and time.time() - used < IDLE_S:
                        return raw
                    _quiet_close(raw)
            return self._open()
        except BaseException:
            self._slots.release()
            raise

    def release(self, raw, broken: bool = False) -> None:
        try:
            if broken or raw.closed:
                _quiet_close(raw)
            else:
                with self._lock:
                    self._idle.append((raw, time.time()))
        finally:
            self._slots.release()

    def close(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, []
        for raw, _ in idle:
            _quiet_close(raw)


class _PgConn:
    """
    What `conn()` hands a thread when the database is PostgreSQL. Each statement
    borrows a pooled connection, reads its rows and gives the connection back;
    inside tx() one connection is held until the transaction ends. A statement
    that fails because the server dropped the link is retried once on a fresh
    connection (every statement outside a transaction is safe to repeat).
    """

    def __init__(self, pool: _PgPool):
        self.pool = pool
        self._held = None

    def _run(self, raw, sql: str, params) -> _Rows:
        try:
            cur = raw.execute(sql, tuple(params))
        except self.pool.psycopg.errors.IntegrityError as exc:
            raise IntegrityError(str(exc)) from exc
        return _Rows(cur.fetchall() if cur.description is not None else [], cur.rowcount)

    def execute(self, sql: str, params=()) -> _Rows:
        sql = sql.replace("?", "%s")
        if self._held is not None:
            return self._run(self._held, sql, params)
        pg = self.pool.psycopg
        for attempt in (0, 1):
            raw = self.pool.acquire()
            try:
                out = self._run(raw, sql, params)
            except (pg.OperationalError, pg.InterfaceError):
                self.pool.release(raw, broken=True)
                if attempt:
                    raise
                continue
            except BaseException:
                self.pool.release(raw)
                raise
            self.pool.release(raw)
            return out
        raise RuntimeError("unreachable")       # pragma: no cover

    def script(self, sql: str) -> None:
        for stmt in sql.replace(" REAL ", " DOUBLE PRECISION ").split(";"):
            if stmt.strip():
                self.execute(stmt)
        for table in TABLES:                    # see the module docstring: closes the public REST API
            try:
                self.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            except IntegrityError:
                raise
            except Exception:                   # not the owner of an existing table: leave it as it is
                pass

    def begin(self) -> None:
        raw = self.pool.acquire()
        try:
            raw.execute("BEGIN")
        except BaseException:
            self.pool.release(raw, broken=True)
            raise
        self._held = raw

    def end(self) -> None:
        raw, self._held = self._held, None
        if raw is not None:
            idle = raw.info.transaction_status == self.pool.psycopg.pq.TransactionStatus.IDLE
            self.pool.release(raw, broken=not idle)

    def close(self) -> None:
        self.end()


_pools: Dict[str, _PgPool] = {}


def _pool() -> _PgPool:
    url = config.DATABASE_URL
    with _init_lock:
        if url not in _pools:
            _pools[url] = _PgPool(url, POOL_SIZE)
        return _pools[url]


def conn():
    """This thread's handle on the database; the tables are created once per database."""
    global _schema_target
    target = _target()
    c = getattr(_local, "con", None)
    if c is None or getattr(_local, "target", None) != target:
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
        c = _PgConn(_pool()) if is_postgres() else _SqliteConn()
        _local.con, _local.target = c, target
    if _schema_target != target:
        with _init_lock:
            if _schema_target != target:
                c.script(SCHEMA)
                _schema_target = target
    return c


def reset_for_tests() -> None:
    """Forget cached connections (the tests point the app at a temporary database)."""
    global _schema_target
    _schema_target = None
    if getattr(_local, "con", None) is not None:
        try:
            _local.con.close()
        except Exception:
            pass
        _local.con = None
    with _init_lock:
        pools = list(_pools.values())
        _pools.clear()
    for p in pools:
        p.close()


@contextmanager
def tx() -> Iterator[Any]:
    """A transaction: everything inside is saved together, or not at all."""
    c = conn()
    c.begin()
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        c.end()


def scalar(sql: str, params=()) -> Any:
    """First column of the first row (name the column `n` in the query)."""
    r = conn().execute(sql, params).fetchone()
    return None if r is None else r["n"]


def copy_from_sqlite(path: str) -> Dict[str, int]:
    """
    Copy every account, session, project and scenario from a Taki SQLite file
    into the database Taki is configured to use (normally an online PostgreSQL).
    Rows that are already there (same id) are left alone, so it is safe to run twice.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    src = sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    dst = conn()
    counts: Dict[str, int] = {}
    try:
        have = {r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in TABLES:
            if table not in have:                    # a file written by an older version
                continue
            key, n = _KEYS[table], 0
            for r in src.execute(f"SELECT * FROM {table}").fetchall():
                cols = list(r.keys())
                if dst.execute(f"SELECT 1 AS n FROM {table} WHERE {key} = ?", (r[key],)).fetchone():
                    continue
                try:
                    dst.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                                [r[c] for c in cols])
                    n += 1
                except IntegrityError:
                    continue            # e.g. an email that already exists in the target
            counts[table] = n
    finally:
        src.close()
    return counts


def counts() -> Dict[str, int]:
    """Rows per table, for the command-line checks."""
    return {t: int(scalar(f"SELECT COUNT(*) AS n FROM {t}") or 0) for t in TABLES}


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> float:
    return time.time()


def row(r) -> Optional[Dict[str, Any]]:
    return dict(r) if r is not None else None


# ------------------------------------------------------------------ projects
def _project_out(r, with_config: bool = True) -> dict:
    d = {"id": r["id"], "name": r["name"], "description": r["description"],
         "created_at": r["created_at"], "updated_at": r["updated_at"],
         "summary": json.loads(r["summary"] or "{}")}
    if with_config:
        d["config"] = json.loads(r["config"])
    return d


def list_projects(user_id: str) -> List[dict]:
    rows = conn().execute(
        "SELECT p.*, (SELECT COUNT(*) FROM scenarios s WHERE s.project_id = p.id) AS n_scen, "
        "(SELECT COUNT(*) FROM shares h WHERE h.project_id = p.id) AS n_share "
        "FROM projects p WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
    out = []
    for r in rows:
        d = _project_out(r, with_config=False)
        d["scenario_count"] = r["n_scen"]
        d["shared"] = bool(r["n_share"])
        out.append(d)
    return out


def get_project(user_id: str, project_id: str) -> Optional[dict]:
    r = conn().execute("SELECT p.*, (SELECT token FROM shares s WHERE s.project_id = p.id) AS share_token "
                       "FROM projects p WHERE p.id = ? AND p.user_id = ?", (project_id, user_id)).fetchone()
    if r is None:
        return None
    d = _project_out(r)
    d["share"] = r["share_token"]
    d["scenarios"] = list_scenarios(project_id)
    return d


def create_project(user_id: str, name: str, cfg: dict, description: str = "",
                   summary: Optional[dict] = None) -> dict:
    pid, t = new_id(), now()
    conn().execute(
        "INSERT INTO projects (id, user_id, name, description, config, summary, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (pid, user_id, name[:120], description[:500], json.dumps(cfg), json.dumps(summary or {}), t, t))
    return get_project(user_id, pid)  # type: ignore[return-value]


def update_project(user_id: str, project_id: str, name: Optional[str] = None,
                   description: Optional[str] = None, cfg: Optional[dict] = None,
                   summary: Optional[dict] = None) -> Optional[dict]:
    sets, vals = ["updated_at = ?"], [now()]
    if name is not None:
        sets.append("name = ?"); vals.append(name[:120])
    if description is not None:
        sets.append("description = ?"); vals.append(description[:500])
    if cfg is not None:
        sets.append("config = ?"); vals.append(json.dumps(cfg))
    if summary is not None:
        sets.append("summary = ?"); vals.append(json.dumps(summary))
    vals += [project_id, user_id]
    cur = conn().execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ? AND user_id = ?", vals)
    if cur.rowcount == 0:
        return None
    return get_project(user_id, project_id)


def delete_project(user_id: str, project_id: str) -> bool:
    cur = conn().execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    return cur.rowcount > 0


def count_projects(user_id: str) -> int:
    return int(scalar("SELECT COUNT(*) AS n FROM projects WHERE user_id = ?", (user_id,)))


# ----------------------------------------------------------------- scenarios
def list_scenarios(project_id: str) -> List[dict]:
    rows = conn().execute("SELECT * FROM scenarios WHERE project_id = ? ORDER BY created_at",
                          (project_id,)).fetchall()
    return [{"id": r["id"], "name": r["name"], "note": r["note"], "created_at": r["created_at"],
             "config": json.loads(r["config"]), "summary": json.loads(r["summary"] or "{}")}
            for r in rows]


def add_scenario(project_id: str, name: str, cfg: dict, note: str = "",
                 summary: Optional[dict] = None) -> dict:
    sid, t = new_id(), now()
    conn().execute(
        "INSERT INTO scenarios (id, project_id, name, note, config, summary, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (sid, project_id, name[:120], note[:500], json.dumps(cfg), json.dumps(summary or {}), t))
    conn().execute("UPDATE projects SET updated_at = ? WHERE id = ?", (t, project_id))
    return {"id": sid, "name": name[:120], "note": note[:500], "created_at": t, "config": cfg,
            "summary": summary or {}}


def rename_scenario(project_id: str, scenario_id: str, name: str, note: Optional[str] = None) -> bool:
    if note is None:
        cur = conn().execute("UPDATE scenarios SET name = ? WHERE id = ? AND project_id = ?",
                             (name[:120], scenario_id, project_id))
    else:
        cur = conn().execute("UPDATE scenarios SET name = ?, note = ? WHERE id = ? AND project_id = ?",
                             (name[:120], note[:500], scenario_id, project_id))
    return cur.rowcount > 0


def delete_scenario(project_id: str, scenario_id: str) -> bool:
    cur = conn().execute("DELETE FROM scenarios WHERE id = ? AND project_id = ?",
                         (scenario_id, project_id))
    return cur.rowcount > 0


def count_scenarios(project_id: str) -> int:
    return int(scalar("SELECT COUNT(*) AS n FROM scenarios WHERE project_id = ?", (project_id,)))


# -------------------------------------------------------------------- shares
# A share link hands out a COPY of a project: whoever opens it gets their own
# project to work on, and the owner's is never touched.
def share_project(user_id: str, project_id: str) -> Optional[str]:
    """The project's share token, made on first call. None if the project is not the user's."""
    c = conn()
    if not c.execute("SELECT 1 AS n FROM projects WHERE id = ? AND user_id = ?",
                     (project_id, user_id)).fetchone():
        return None
    r = c.execute("SELECT token FROM shares WHERE project_id = ?", (project_id,)).fetchone()
    if r:
        return r["token"]
    token = uuid.uuid4().hex + uuid.uuid4().hex[:8]
    try:
        c.execute("INSERT INTO shares (token, project_id, created_at) VALUES (?,?,?)",
                  (token, project_id, now()))
    except IntegrityError:                           # shared from two tabs at once
        return c.execute("SELECT token FROM shares WHERE project_id = ?", (project_id,)).fetchone()["token"]
    return token


def unshare_project(user_id: str, project_id: str) -> bool:
    cur = conn().execute("DELETE FROM shares WHERE project_id = ? AND project_id IN "
                         "(SELECT id FROM projects WHERE user_id = ?)", (project_id, user_id))
    return cur.rowcount > 0


def shared_project(token: str) -> Optional[dict]:
    """The project behind a share link, with its scenarios and the owner's name."""
    r = conn().execute("SELECT p.*, u.name AS owner_name, u.organisation AS owner_org FROM shares s "
                       "JOIN projects p ON p.id = s.project_id JOIN users u ON u.id = p.user_id "
                       "WHERE s.token = ?", (str(token or "")[:80],)).fetchone()
    if r is None:
        return None
    d = _project_out(r)
    d["owner"] = {"name": r["owner_name"], "organisation": r["owner_org"]}
    d["owner_id"] = r["user_id"]
    d["scenarios"] = list_scenarios(r["id"])
    return d


def count_share_open(token: str) -> None:
    conn().execute("UPDATE shares SET opened = opened + 1 WHERE token = ?", (token,))
