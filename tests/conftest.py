"""Shared fixtures. Run from the project root:  python -m pytest"""

import importlib.util
import os
import sys
import tempfile

import pytest

# The tests must never touch a real installation. Before anything of Taki is imported:
# ignore a .env file beside run.py (it may name an online database with real accounts),
# drop any database address or shared AI key found in the environment, and keep the
# local data file in a scratch folder instead of ./data.
os.environ["TAKI_IGNORE_ENV_FILE"] = "1"
for _name in ("DATABASE_URL", "TAKI_DATABASE_URL", "TAKI_ANTHROPIC_API_KEY", "TAKI_GEMINI_API_KEY",
              "TAKI_OPENAI_API_KEY"):
    os.environ.pop(_name, None)
os.environ["TAKI_DATA_DIR"] = tempfile.mkdtemp(prefix="taki-tests-")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
REF = os.path.join(ROOT, "tests", "reference")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REF, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def ref():
    """The physics and earth modules exactly as shipped in the original Taki (taki_updated)."""
    physics = _load("physics", "physics_original.py")
    earth = _load("earth", "earth_original.py")
    return physics, earth


# The HTTP tests run on SQLite, and again on PostgreSQL when a test database is named:
#   TAKI_TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/taki_test python -m pytest
# (every table in that database is dropped before each test - use a scratch database).
PG_URL = os.environ.get("TAKI_TEST_DATABASE_URL", "")


@pytest.fixture(params=["sqlite"] + (["postgresql"] if PG_URL else []))
def client(tmp_path, request):
    from fastapi.testclient import TestClient
    from server import auth, config, db
    config.set_data_dir(str(tmp_path))
    config.set_database_url(PG_URL if request.param == "postgresql" else "")
    db.reset_for_tests()
    if request.param == "postgresql":
        import psycopg
        with psycopg.connect(config.DATABASE_URL, autocommit=True) as raw:
            raw.execute("DROP TABLE IF EXISTS " + ", ".join(reversed(db.TABLES)) + " CASCADE")
    auth._attempts.clear()
    from server.main import app
    with TestClient(app, headers={"X-Requested-With": "taki"}) as c:
        assert c.get("/api/health").json()["database"] == request.param
        yield c
    db.reset_for_tests()
    config.set_database_url("")


@pytest.fixture()
def guest(client):
    r = client.post("/api/auth/guest", json={})
    assert r.status_code == 200
    return client
