"""
Publishing on Vercel: the entrance file Vercel looks for, the settings that follow
from running there, and what a visitor gets when the database is missing.

Vercel itself cannot run here. What is tested is everything Taki contributes: that
app.py is a file Vercel's own detection accepts, and that the application behaves
behind a front door that reports the visitor in X-Forwarded headers.
"""

import ast
import json
import os
import subprocess
import sys

import pytest

from server import vercel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- what Vercel looks for
def test_the_entrance_is_a_file_vercel_recognises():
    """Vercel reads app.py without running it and wants a top-level `app`: a plain import counts."""
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = [alias.asname or alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                for alias in node.names]
    assert "app" in imported
    where = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "server.main":
            where["load"] = node.lineno
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            where[ast.unparse(node.value.func)] = node.lineno
    # the settings before the application reads them, the fitting after it exists
    assert where["vercel.prepare"] < where["load"] < where["vercel.adapt"]


def test_nothing_beside_it_changes_what_vercel_builds():
    """Vercel decides what a project is from the files at its top. These would change its mind."""
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as fh:
        assert "fastapi" in fh.read(), "this is how Vercel recognises a FastAPI project"
    for name in ("pyproject.toml", "Pipfile", "package.json", "index.py", "main.py", "server.py", "wsgi.py", "asgi.py",
                 "manage.py", "Dockerfile.vercel"):
        assert not os.path.exists(os.path.join(ROOT, name)), name
    for folder in ("api", "public", "app"):          # separate functions; files served as they are; hides app.py
        assert not os.path.isdir(os.path.join(ROOT, folder)), folder


# --------------------------------------------------------------------------------- the settings
def test_settings_that_follow_from_vercel():
    got = vercel.settings({"VERCEL": "1", "VERCEL_ENV": "production", "VERCEL_PROJECT_PRODUCTION_URL": "taki.vercel.app",
                           "DATABASE_URL": "postgresql://u@h/d"})
    assert got == {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "TAKI_SECURE_COOKIES": "1",
                   "TAKI_DATA_DIR": "/tmp/taki", "MPLCONFIGDIR": "/tmp/matplotlib",
                   "TAKI_PUBLIC_URL": "https://taki.vercel.app"}


def test_a_value_somebody_set_is_kept():
    env = {"TAKI_SECURE_COOKIES": "0", "TAKI_PUBLIC_URL": "https://emf.example.org", "MPLCONFIGDIR": "/tmp",
           "OMP_NUM_THREADS": "2", "VERCEL_PROJECT_PRODUCTION_URL": "taki.vercel.app"}
    got = vercel.prepare(env)
    assert set(got) == {"OPENBLAS_NUM_THREADS", "TAKI_DATA_DIR"}
    assert env["TAKI_SECURE_COOKIES"] == "0" and env["TAKI_PUBLIC_URL"] == "https://emf.example.org"
    assert env["MPLCONFIGDIR"] == "/tmp" and env["OMP_NUM_THREADS"] == "2" and env["TAKI_DATA_DIR"] == "/tmp/taki"


@pytest.mark.parametrize("env, expected", [
    ({"VERCEL_ENV": "preview", "VERCEL_PROJECT_PRODUCTION_URL": "taki.vercel.app"}, None),   # a trial deployment
    ({"VERCEL_ENV": "production"}, None),                                                    # Vercel did not say
    ({"VERCEL_PROJECT_PRODUCTION_URL": "emf.example.org/"}, "https://emf.example.org"),
    ({"VERCEL_PROJECT_PRODUCTION_URL": "https://emf.example.org"}, "https://emf.example.org"),
])
def test_the_lasting_address_is_used_for_links_only_on_the_real_site(env, expected):
    assert vercel.settings(env).get("TAKI_PUBLIC_URL") == expected


@pytest.mark.parametrize("env, expected", [
    ({"POSTGRES_URL": "postgres://u@h/d"}, "postgres://u@h/d"),            # what Vercel's database add-ons set
    ({"POSTGRES_URL": "postgres://u@h/d", "DATABASE_URL": "postgresql://x@y/z"}, None),
    ({"POSTGRES_URL": "postgres://u@h/d", "TAKI_DATABASE_URL": "postgresql://x@y/z"}, None),
    ({}, None),
])
def test_the_database_address_under_vercels_own_name(env, expected):
    assert vercel.settings(env).get("TAKI_DATABASE_URL") == expected


# ------------------------------------------------------------------------ the application, adapted
def _adapted(monkeypatch, database_url):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from server import config
    monkeypatch.setattr(config, "DATABASE_URL", database_url)
    started = []
    app = FastAPI(on_startup=[lambda: started.append(True)])

    @app.get("/who")
    def who(request: Request):
        return {"client": request.client.host, "scheme": request.url.scheme, "base": str(request.base_url)}

    vercel.adapt(app)
    return TestClient(app, base_url="http://taki.vercel.app"), started


def test_the_visitor_is_who_vercels_front_door_says(monkeypatch):
    client, _ = _adapted(monkeypatch, "postgresql://u@h/d")
    with client:
        one = client.get("/who", headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"}).json()
        two = client.get("/who", headers={"X-Forwarded-For": "203.0.113.8", "X-Forwarded-Proto": "https"}).json()
    assert one == {"client": "203.0.113.7", "scheme": "https", "base": "https://taki.vercel.app/"}
    assert two["client"] == "203.0.113.8"          # two visitors are two addresses: sign-in limits count per person


def test_without_a_database_every_page_says_what_is_missing(monkeypatch):
    client, started = _adapted(monkeypatch, "")
    with client:
        assert started == [True]                   # the application itself still starts
        for method, path in (("GET", "/"), ("GET", "/who"), ("POST", "/api/auth/guest"), ("GET", "/assets/x.js")):
            r = client.request(method, path)
            assert r.status_code == 503 and r.headers["content-type"].startswith("text/plain")
            assert "DATABASE_URL" in r.text and "Environment Variables" in r.text
            assert r.headers["cache-control"] == "no-store"
        assert client.head("/").status_code == 503 and client.head("/").text == ""


def test_with_a_database_nothing_is_in_the_way(monkeypatch):
    client, _ = _adapted(monkeypatch, "postgresql://u@h/d")
    with client:
        assert client.get("/who").status_code == 200


# --------------------------------------------------------------- the entrance, loaded as Vercel does
PROBE = """
import json, os, sys
sys.path.insert(0, {root!r})
import app as entrance
from fastapi.testclient import TestClient
from server import config
with TestClient(entrance.app, base_url="http://taki.vercel.app") as client:
    r = client.get("/api/health", headers={{"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"}})
    g = client.post("/api/auth/guest", json={{}}, headers={{"X-Requested-With": "taki", "X-Forwarded-Proto": "https"}})
print(json.dumps({{"status": r.status_code, "text": r.text, "secure": config.SECURE_COOKIES, "data": config.DATA_DIR,
                  "public": config.PUBLIC_URL, "threads": os.environ.get("OPENBLAS_NUM_THREADS"),
                  "cookie": g.headers.get("set-cookie", "")}}))
"""


def _load_entrance(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TAKI_", "VERCEL")) and k not in
           ("DATABASE_URL", "POSTGRES_URL", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MPLCONFIGDIR")}
    env.update({"VERCEL": "1", "VERCEL_ENV": "production", "VERCEL_PROJECT_PRODUCTION_URL": "taki.vercel.app",
                "TAKI_IGNORE_ENV_FILE": "1", "TAKI_DATA_DIR": str(tmp_path / "data"),
                "MPLCONFIGDIR": str(tmp_path / "mpl")})
    env.update(extra)
    done = subprocess.run([sys.executable, "-c", PROBE.format(root=ROOT)], env=env, cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_entrance_without_a_database(tmp_path):
    got = _load_entrance(tmp_path)
    assert got["status"] == 503 and got["text"].startswith("Taki is on Vercel, but it has no database yet.")
    assert got["secure"] is True and got["public"] == "https://taki.vercel.app" and got["threads"] == "1"
    assert got["data"] == str(tmp_path / "data")           # a value somebody set is kept


@pytest.mark.skipif(not os.environ.get("TAKI_TEST_DATABASE_URL"), reason="needs TAKI_TEST_DATABASE_URL")
def test_the_entrance_with_a_database(tmp_path):
    got = _load_entrance(tmp_path, POSTGRES_URL=os.environ["TAKI_TEST_DATABASE_URL"])
    assert got["status"] == 200 and json.loads(got["text"])["database"] == "postgresql"
    assert "Secure" in got["cookie"] and "HttpOnly" in got["cookie"]
