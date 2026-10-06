"""HTTP layer: accounts, sessions, ownership and the main endpoints."""

from server import service

PW = "correct horse battery"


def register(client, email="eng@example.com", name="Eng One"):
    r = client.post("/api/auth/register", json={"email": email, "password": PW, "name": name})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def test_health_and_meta_are_public(client):
    assert client.get("/api/health").json()["ok"] is True
    m = client.get("/api/meta").json()
    assert m["user"] is None and m["allow_guests"] is True


def test_everything_else_needs_a_session(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/solve", json={"config": service.default_config()}).status_code == 401
    assert client.get("/api/library").status_code == 401


def test_mutating_calls_need_the_csrf_header(client):
    r = client.post("/api/auth/guest", json={}, headers={"X-Requested-With": ""})
    assert r.status_code == 400


def test_register_login_logout(client):
    user = register(client)
    assert user["email"] == "eng@example.com" and user["is_guest"] is False
    assert client.get("/api/auth/me").json()["user"]["id"] == user["id"]
    assert client.post("/api/auth/logout", json={}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "eng@example.com", "password": "nope nope nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ENG@example.com", "password": PW}).status_code == 200
    assert client.get("/api/auth/me").json()["user"]["id"] == user["id"]


def test_registration_rules(client):
    assert client.post("/api/auth/register", json={"email": "not-an-email", "password": PW}).status_code == 400
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 400
    register(client, "dup@example.com")
    client.post("/api/auth/logout", json={})
    assert client.post("/api/auth/register", json={"email": "dup@example.com", "password": PW}).status_code == 409


def test_passwords_are_not_stored_in_clear(client):
    register(client, "hash@example.com")
    from server import db
    row = db.conn().execute("SELECT password_hash FROM users WHERE email = ?", ("hash@example.com",)).fetchone()
    assert PW not in row["password_hash"] and row["password_hash"].startswith("scrypt$")
    tokens = [r["token_hash"] for r in db.conn().execute("SELECT token_hash FROM sessions").fetchall()]
    assert tokens and all(len(t) == 64 for t in tokens)


def test_guest_projects_survive_becoming_an_account(guest):
    p = guest.post("/api/projects", json={"name": "Guest work"}).json()["project"]
    user = register(guest, "up@example.com")
    assert user["is_guest"] is False
    names = [x["name"] for x in guest.get("/api/projects").json()["projects"]]
    assert names == ["Guest work"] and guest.get(f"/api/projects/{p['id']}").status_code == 200


def test_projects_are_private_to_their_owner(client):
    register(client, "a@example.com")
    pid = client.post("/api/projects", json={"name": "Mine"}).json()["project"]["id"]
    client.post("/api/auth/logout", json={})
    register(client, "b@example.com")
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.put(f"/api/projects/{pid}", json={"name": "Stolen"}).status_code == 404
    assert client.delete(f"/api/projects/{pid}").status_code == 404
    assert client.post(f"/api/projects/{pid}/scenarios", json={"name": "x"}).status_code == 404
    assert client.get("/api/projects").json()["projects"] == []


def test_project_and_scenario_lifecycle(guest):
    cfg = service.default_config()
    cfg["lines"][0]["load_pct"] = 70
    p = guest.post("/api/projects", json={"name": "Corridor", "description": "d", "config": cfg}).json()["project"]
    assert p["summary"]["peak_b"] > 0
    cfg["lines"][0]["load_pct"] = 100
    up = guest.put(f"/api/projects/{p['id']}", json={"name": "Corridor 2", "config": cfg}).json()["project"]
    assert up["name"] == "Corridor 2" and up["summary"]["peak_b"] > p["summary"]["peak_b"]
    s = guest.post(f"/api/projects/{p['id']}/scenarios", json={"name": "Base", "config": cfg}).json()["scenario"]
    assert guest.patch(f"/api/projects/{p['id']}/scenarios/{s['id']}", json={"name": "Base case"}).status_code == 200
    full = guest.get(f"/api/projects/{p['id']}").json()["project"]
    assert [x["name"] for x in full["scenarios"]] == ["Base case"]
    dup = guest.post(f"/api/projects/{p['id']}/duplicate", json={}).json()["project"]
    assert dup["name"].endswith("(copy)") and len(dup["scenarios"]) == 1
    assert guest.delete(f"/api/projects/{p['id']}/scenarios/{s['id']}").status_code == 200
    assert guest.delete(f"/api/projects/{p['id']}").status_code == 200
    assert [x["id"] for x in guest.get("/api/projects").json()["projects"]] == [dup["id"]]


def test_simulation_endpoints(guest):
    cfg = next(t for t in guest.get("/api/templates").json()["templates"] if t["id"] == "school")["config"]
    body = {"config": cfg}
    assert guest.post("/api/solve", json=body).json()["shield"]["on"] is True
    for path, extra in (("/api/grid", {"z": 0}), ("/api/points", {"points": [{"x": 5, "y": 1, "z": 0}]}),
                        ("/api/earth", {}), ("/api/fieldlines", {"phase_deg": 45}), ("/api/efieldlines", {}),
                        ("/api/shield/models", {}), ("/api/shield/sweep", {"kind": "thickness"}),
                        ("/api/shield/assistant", {}), ("/api/twin", {}), ("/api/twin/section", {"z": 10}),
                        ("/api/twin/volume", {}), ("/api/changes", {}), ("/api/report/preview", {}),
                        ("/api/scenarios/compare", {"items": [{"name": "a", "config": cfg}]})):
        r = guest.post(path, json={**body, **extra})
        assert r.status_code == 200, f"{path}: {r.text[:200]}"
    assert guest.post("/api/shield/sweep", json={**body, "kind": "bogus"}).status_code == 422
    assert guest.get("/api/library").json()["shield_materials"]
    assert len(guest.get("/api/validation/checks").json()["checks"]) >= 7


def test_report_download(guest):
    r = guest.post("/api/report/pdf", json={"config": service.default_config(), "options": {"figures": []}})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert "attachment" in r.headers["content-disposition"]
    assert guest.post("/api/report/exe", json={"config": {}}).status_code == 404


def test_legacy_file_import_is_flagged(guest):
    legacy = {"schema_version": 1, "num_lines": 1, "max_sag_m": 1.5, "row_boundary_m": 12,
              "lines": [{"preset_name": "275kV Monopole", "x_offset": 0, "load": 60, "arrangement": "ABC-CBA",
                         "current_override": 0, "voltage_override": 0}]}
    r = guest.post("/api/normalise", json={"config": legacy}).json()
    assert r["migrated"] is True and r["notes"] and r["config"]["lines"][0]["load_pct"] == 60


def test_change_password_and_delete_account(client):
    register(client, "pw@example.com")
    assert client.post("/api/auth/password", json={"current": "wrong", "new": "another long phrase"}).status_code in (400, 401, 403)
    assert client.post("/api/auth/password", json={"current": PW, "new": "another long phrase"}).status_code == 200
    client.post("/api/auth/logout", json={})
    assert client.post("/api/auth/login", json={"email": "pw@example.com", "password": PW}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "pw@example.com", "password": "another long phrase"}).status_code == 200
    client.post("/api/projects", json={"name": "to be removed"})
    assert client.post("/api/auth/delete", json={"password": "another long phrase"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    from server import db
    assert db.scalar("SELECT COUNT(*) AS n FROM projects") == 0
    assert db.scalar("SELECT COUNT(*) AS n FROM sessions") == 0


def test_login_is_rate_limited(client):
    register(client, "rl@example.com")
    client.post("/api/auth/logout", json={})
    codes = [client.post("/api/auth/login", json={"email": "rl@example.com", "password": "bad bad bad bad"}).status_code for _ in range(12)]
    assert 429 in codes


def test_spa_fallback_serves_the_app_or_a_clear_message(client):
    r = client.get("/p/anything/dashboard")
    assert r.status_code in (200, 503)
    assert client.get("/api/does-not-exist").status_code == 404


def test_copy_sqlite_into_the_configured_database(client, tmp_path):
    """A local SQLite database can be moved into whichever database is configured."""
    import sqlite3
    from server import db
    src = tmp_path / "old.db"
    con = sqlite3.connect(src)
    con.executescript(db.SCHEMA)
    con.execute("INSERT INTO users (id, email, name, password_hash, is_guest, created_at, last_seen) "
                "VALUES ('u1', 'moved@example.com', 'Moved', 'scrypt$x', 0, 1.0, 2.0)")
    con.execute("INSERT INTO projects (id, user_id, name, config, created_at, updated_at) "
                "VALUES ('p1', 'u1', 'Old project', '{}', 1.0, 1700000000.123456)")
    con.execute("INSERT INTO scenarios (id, project_id, name, config, created_at) VALUES ('s1', 'p1', 'Base', '{}', 3.0)")
    con.commit(); con.close()
    first, again = db.copy_from_sqlite(str(src)), db.copy_from_sqlite(str(src))
    assert {k: first[k] for k in ("users", "sessions", "projects", "scenarios")} == \
        {"users": 1, "sessions": 0, "projects": 1, "scenarios": 1}
    assert not any(again.values())                                  # safe to run twice
    row = db.conn().execute("SELECT name, updated_at FROM projects WHERE id = ?", ("p1",)).fetchone()
    assert row["name"] == "Old project" and abs(row["updated_at"] - 1700000000.123456) < 1e-3   # full precision kept


# ----------------------------------------------------------- password reset
def _register(client, email="reset@example.com", password="a long first password"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Reset Me"})
    assert r.status_code == 200
    return r.json()["user"]


def _reset_link(capsys) -> str:
    import re
    m = re.search(r"/reset\?token=([\w-]+)", capsys.readouterr().out)
    assert m, "the reset link should be printed when no mail server is configured"
    return m.group(1)


def test_forgot_password_gives_a_single_use_link(client, capsys):
    _register(client)
    client.post("/api/auth/logout")
    # same answer whether or not the account exists
    a = client.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    b = client.post("/api/auth/forgot", json={"email": "reset@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json() == {"ok": True, "email": False}
    token = _reset_link(capsys)

    assert client.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    r = client.post("/api/auth/reset", json={"token": token, "password": "a brand new password"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "reset@example.com"
    assert client.get("/api/auth/me").status_code == 200                       # signed in by the reset
    assert client.post("/api/auth/reset", json={"token": token, "password": "another password 2"}).status_code == 400

    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "a long first password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "a brand new password"}).status_code == 200


def test_reset_ends_other_sign_ins_and_rejects_bad_tokens(client, capsys):
    from fastapi.testclient import TestClient
    from server.main import app
    _register(client)
    assert client.post("/api/auth/reset", json={"token": "not-a-token", "password": "whatever password"}).status_code == 400
    other = TestClient(app, headers={"X-Requested-With": "taki"})
    client.post("/api/auth/forgot", json={"email": "reset@example.com"})
    token = _reset_link(capsys)
    assert other.post("/api/auth/reset", json={"token": token, "password": "set from another browser"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401                       # the old session is gone


def test_forgot_is_rate_limited_per_address(client):
    codes = [client.post("/api/auth/forgot", json={"email": "flood@example.com"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes


def test_expired_reset_links_are_purged(client, capsys):
    from server import auth, db
    _register(client)
    client.post("/api/auth/forgot", json={"email": "reset@example.com"})
    token = _reset_link(capsys)
    db.conn().execute("UPDATE password_resets SET expires_at = ?", (db.now() - 5,))
    assert client.post("/api/auth/reset", json={"token": token, "password": "too late password"}).status_code == 400
    auth.purge_expired()
    assert db.scalar("SELECT COUNT(*) AS n FROM password_resets") == 0


# ------------------------------------------------------------------ sharing
def test_share_link_hands_out_an_independent_copy(client):
    from fastapi.testclient import TestClient
    from server.main import app
    _register(client, "owner@example.com")
    pid = client.post("/api/projects", json={"name": "Shared study", "description": "for review"}).json()["project"]["id"]
    client.post(f"/api/projects/{pid}/scenarios", json={"name": "Base"})
    assert client.get(f"/api/projects/{pid}").json()["project"]["share"] is None

    r = client.post(f"/api/projects/{pid}/share")
    token = r.json()["token"]
    assert r.status_code == 200 and r.json()["url"].endswith(f"/s/{token}") and len(token) >= 32
    assert client.post(f"/api/projects/{pid}/share").json()["token"] == token          # one link per project
    assert client.get(f"/api/projects/{pid}").json()["project"]["share"] == token
    assert client.get("/api/projects").json()["projects"][0]["shared"] is True

    visitor = TestClient(app, headers={"X-Requested-With": "taki"})
    info = visitor.get(f"/api/shared/{token}")                                          # no sign-in needed to look
    assert info.status_code == 200 and info.json()["name"] == "Shared study" and info.json()["scenarios"] == 1
    assert "config" not in info.json() and info.json()["owner"]["name"] == "Reset Me"
    assert visitor.post(f"/api/shared/{token}/open").status_code == 401                 # ... but needed to copy
    visitor.post("/api/auth/guest", json={})
    got = visitor.post(f"/api/shared/{token}/open").json()
    assert got["own"] is False and got["project"]["id"] != pid and len(got["project"]["scenarios"]) == 1
    # the visitor's changes stay in the visitor's copy
    visitor.put(f"/api/projects/{got['project']['id']}", json={"name": "Changed by the visitor"})
    assert client.get(f"/api/projects/{pid}").json()["project"]["name"] == "Shared study"
    assert visitor.get(f"/api/projects/{pid}").status_code == 404                       # the original stays private
    assert client.post(f"/api/shared/{token}/open").json() == {"project": client.get(f"/api/projects/{pid}").json()["project"], "own": True}

    assert client.delete(f"/api/projects/{pid}/share").status_code == 200
    assert visitor.get(f"/api/shared/{token}").status_code == 404
    assert visitor.post(f"/api/shared/{token}/open").status_code == 404


def test_only_the_owner_can_share_and_deleting_the_project_kills_the_link(client):
    from fastapi.testclient import TestClient
    from server.main import app
    _register(client, "owner2@example.com")
    pid = client.post("/api/projects", json={"name": "Mine"}).json()["project"]["id"]
    token = client.post(f"/api/projects/{pid}/share").json()["token"]
    stranger = TestClient(app, headers={"X-Requested-With": "taki"})
    stranger.post("/api/auth/guest", json={})
    assert stranger.post(f"/api/projects/{pid}/share").status_code == 404
    stranger.delete(f"/api/projects/{pid}/share")
    assert client.get(f"/api/shared/{token}").status_code == 200                        # still shared
    client.delete(f"/api/projects/{pid}")
    assert client.get(f"/api/shared/{token}").status_code == 404


# ------------------------------------------------------- database plumbing
def test_many_threads_share_the_database(client):
    """More threads than pooled connections, all reading and writing at once."""
    import threading
    from server import db
    errors, ids = [], []

    def work(i):
        try:
            uid = db.new_id()
            db.conn().execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES (?,?,1,?,?)",
                              (uid, f"t{i}", db.now(), db.now()))
            assert db.conn().execute("SELECT name FROM users WHERE id = ?", (uid,)).fetchone()["name"] == f"t{i}"
            ids.append(uid)
        except Exception as exc:                                    # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(24)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(ids) == 24
    assert db.scalar("SELECT COUNT(*) AS n FROM users WHERE is_guest = 1") >= 24


def test_transactions_roll_back_together(client):
    from server import db
    try:
        with db.tx() as c:
            c.execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES ('tx1', 'x', 1, 1, 1)")
            c.execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES ('tx1', 'dup', 1, 1, 1)")
    except db.IntegrityError:
        pass
    assert db.scalar("SELECT COUNT(*) AS n FROM users WHERE id = 'tx1'") == 0
    with db.tx() as c:
        c.execute("INSERT INTO users (id, name, is_guest, created_at, last_seen) VALUES ('tx2', 'kept', 1, 1, 1)")
    assert db.scalar("SELECT COUNT(*) AS n FROM users WHERE id = 'tx2'") == 1


def test_a_database_that_is_ready_is_asked_once_not_set_up_again(client, monkeypatch):
    """Every start used to run the whole set-up script: fifteen round trips to a database that had it all."""
    from server import db
    con = db.conn()
    if not db.is_postgres():
        assert con.ready() is False             # a local file: the script costs nothing, so it always runs
        return
    assert con.ready() is True
    ran = []
    with monkeypatch.context() as patch:
        patch.setattr(type(con), "script", lambda self, sql: ran.append(sql))
        db.reset_for_tests()
        db.conn()
    assert ran == []                            # the next start asks its one question and changes nothing
    for damage in ("DROP INDEX idx_scenarios_project", "ALTER TABLE shares DISABLE ROW LEVEL SECURITY",
                   "DROP TABLE password_resets"):
        db.conn().execute(damage)
        assert db.conn().ready() is False, damage
        db.reset_for_tests()
        assert db.conn().ready() is True, damage            # and the start after that puts it right


def test_meta_reports_where_the_data_lives(client):
    m = client.get("/api/meta").json()
    assert m["database"] in ("sqlite", "postgresql") and m["email"] is False
    assert m["database_host"] == ("this computer" if m["database"] == "sqlite" else "PostgreSQL on this computer")
