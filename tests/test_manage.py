"""The command-line helpers that connect an online database."""

import os

import pytest

from server import config, db, manage


def test_pasted_connection_strings_are_tidied():
    t = manage.tidy_url
    assert t("  'postgres://u:p@db.example.com:5432/app'  ") == "postgresql://u:p@db.example.com:5432/app?sslmode=require"
    assert t("DATABASE_URL=postgresql://u:p@h.neon.tech/app?options=x") == "postgresql://u:p@h.neon.tech/app?options=x&sslmode=require"
    assert t("postgresql://u:p@h/app?sslmode=verify-full") == "postgresql://u:p@h/app?sslmode=verify-full"
    assert t("postgresql://taki@127.0.0.1:5432/taki") == "postgresql://taki@127.0.0.1:5432/taki"      # local: no TLS forced
    assert t("mysql://u:p@h/app") == "" and t("") == "" and t("hello") == ""


def test_what_the_connect_boxes_hand_out_is_understood():
    """Neon's box shows  psql 'postgresql://...'  by default; others show an export line or a .env line."""
    t = manage.tidy_url
    want = "postgresql://owner:pw@ep-cool-name-a1b2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    assert t(f"psql '{want}'") == want
    assert t(f'psql "{want}"') == want
    assert t(f"  PSQL   '{want}'  ") == want
    assert t(f"export DATABASE_URL='{want}'") == want
    assert t(f'DATABASE_URL="{want}"') == want
    assert t(f"set DATABASE_URL={want}") == want
    assert t(f"psql -h pg.neon.tech '{want}' --set=x") == want
    assert t("psql 'postgres://u:p@db.example.com/app';") == "postgresql://u:p@db.example.com/app?sslmode=require"
    assert t("psql -h db.example.com -U me app") == "" and t("psql ''") == ""


def test_password_placeholder_is_filled_and_encoded():
    raw = "postgresql://postgres.abcd:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    got = manage.tidy_url(raw, "p@ss/w#rd?")
    assert "p%40ss%2Fw%23rd%3F@aws-0" in got and "[YOUR-PASSWORD]" not in got and got.endswith("?sslmode=require")
    assert manage.PLACEHOLDER.search(raw) and not manage.PLACEHOLDER.search(got)


def test_provider_names():
    assert db.provider("") == "this computer"
    assert db.provider("postgresql://postgres.x:p@aws-0-eu.pooler.supabase.com:5432/postgres") == "Supabase"
    assert db.provider("postgresql://u:p@ep-cool-name.ap-southeast-1.aws.neon.tech/neondb") == "Neon"
    assert db.provider("postgresql://u:p@localhost/x") == "PostgreSQL on this computer"
    assert db.provider("postgresql://u:p@db.internal.example.org/x") == "PostgreSQL server"


def test_env_file_is_edited_without_touching_other_settings(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# my settings\nTAKI_PORT=9000\n# DATABASE_URL=example-in-a-comment\nDATABASE_URL=postgresql://old\n")
    monkeypatch.setattr(config, "ENV_FILE", str(env))
    manage._write_env("DATABASE_URL", "postgresql://new")
    text = env.read_text()
    assert "TAKI_PORT=9000" in text and "# my settings" in text and "# DATABASE_URL=example-in-a-comment" in text
    assert "DATABASE_URL=postgresql://new" in text and "postgresql://old" not in text
    assert text.count("\nDATABASE_URL=") == 1
    manage._write_env("DATABASE_URL", None)
    text = env.read_text()
    assert "\nDATABASE_URL=" not in text and "TAKI_PORT=9000" in text and manage.ENV_NOTE not in text
    env.unlink()
    manage._write_env("DATABASE_URL", "postgresql://fresh")
    assert env.read_text().splitlines() == [manage.ENV_NOTE, "DATABASE_URL=postgresql://fresh"]


def test_failures_are_explained_in_plain_words():
    direct = "postgresql://postgres:x@db.abcdefghijklmnop.supabase.co:5432/postgres"
    assert "Session pooler" in manage._explain(direct, Exception("failed to resolve host: Name or service not known"))
    assert "password you chose" in manage._explain("postgresql://h", Exception('FATAL: password authentication failed for user "postgres"'))
    assert "Restore project" in manage._explain("postgresql://h", Exception("connection timeout expired"))
    assert manage._explain("postgresql://h", Exception("something else\nsecond line")) == "something else"


def test_setup_refuses_a_bad_string_and_changes_nothing(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_FILE", str(env))
    assert manage.setup_db("mysql://nope") == 2
    assert manage.setup_db("postgresql://u:[YOUR-PASSWORD]@h/db") == 2
    assert manage.setup_db("postgresql://taki:x@127.0.0.1:1/none") == 1          # nothing listens there
    assert not env.exists() and "Nothing was changed" in capsys.readouterr().out
    assert not db.is_postgres()


@pytest.mark.skipif(not os.environ.get("TAKI_TEST_DATABASE_URL"), reason="needs a scratch PostgreSQL database")
def test_setup_connects_copies_and_saves(tmp_path, monkeypatch, capsys):
    import sqlite3
    env = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_FILE", str(env))
    config.set_data_dir(str(tmp_path))
    local = sqlite3.connect(config.DB_PATH)
    local.executescript(db.SCHEMA)
    local.execute("INSERT INTO users (id, email, name, password_hash, is_guest, created_at, last_seen) "
                  "VALUES ('wiz1', 'wizard@example.com', 'Wizard', 'scrypt$x', 0, 1.0, 2.0)")
    local.commit(); local.close()
    url = os.environ["TAKI_TEST_DATABASE_URL"]
    try:
        import psycopg
        with psycopg.connect(url, autocommit=True) as raw:
            raw.execute("DROP TABLE IF EXISTS " + ", ".join(reversed(db.TABLES)) + " CASCADE")
        assert manage.setup_db(url, assume_yes=True) == 0
        assert f"DATABASE_URL={url}" in env.read_text()
        assert db.is_postgres() and db.scalar("SELECT COUNT(*) AS n FROM users WHERE id = 'wiz1'") == 1
        # row-level security is on, so a hosted REST API cannot read the tables
        rows = db.conn().execute("SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
                                 "('users', 'sessions', 'projects', 'scenarios', 'password_resets', 'shares')").fetchall()
        assert len(rows) == 6 and all(r["relrowsecurity"] for r in rows)
        assert "Copied" in capsys.readouterr().out
    finally:
        config.set_database_url("")
        db.reset_for_tests()
