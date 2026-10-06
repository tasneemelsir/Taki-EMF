"""
The desktop version: no sign-in, stops with its window, and everything that
installs it. The Windows-only steps of the installer (shortcuts, the registry)
cannot run here; what is tested is everything around them, and the batch file
is checked for the mistakes that most often break one.
"""

import http.client
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "the-key-of-this-test"


@pytest.fixture()
def desk(tmp_path):
    """The application as the desktop version, on a scratch folder, addressed as this computer."""
    from fastapi.testclient import TestClient
    from server import auth, config, db, desktop
    config.set_data_dir(str(tmp_path))
    config.set_database_url("")
    config.set_desktop(True)
    db.reset_for_tests()
    auth._attempts.clear()
    desktop.STATE.__init__()
    desktop.STATE.key = KEY
    from server.main import app
    try:
        with TestClient(app, base_url="http://127.0.0.1:8254", headers={"X-Requested-With": "taki"},
                        follow_redirects=False) as c:
            yield c
    finally:
        db.reset_for_tests()
        config.set_desktop(False)
        desktop.STATE.__init__()


@pytest.fixture(scope="module")
def setup_script():
    """tools/desktop_setup.py, which is a script and not part of a package."""
    spec = importlib.util.spec_from_file_location("desktop_setup", os.path.join(ROOT, "tools", "desktop_setup.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def test_the_desktop_switch_changes_the_settings_and_gives_them_back():
    from server import config
    before = (config.ALLOW_SIGNUP, config.ALLOW_GUESTS, config.SESSION_DAYS, config.COOKIE_NAME, config.DATABASE_URL)
    config.set_desktop(True)
    try:
        assert config.DESKTOP and not config.ALLOW_SIGNUP and not config.ALLOW_GUESTS
        assert config.DATABASE_URL == "" and config.COOKIE_NAME == "taki_desktop" and config.SESSION_DAYS > 3000
    finally:
        config.set_desktop(False)
    assert (config.ALLOW_SIGNUP, config.ALLOW_GUESTS, config.SESSION_DAYS, config.COOKIE_NAME,
            config.DATABASE_URL) == before and not config.DESKTOP


def test_the_web_copy_is_not_a_desktop_and_offers_the_download(client):
    m = client.get("/api/meta").json()
    assert m["desktop"] is False and m["desktop_download"] is True and "data_dir" not in m
    assert client.get("/desktop/start?k=x").status_code == 404
    assert client.get("/api/desktop/presence").status_code == 404
    client.post("/api/auth/guest", json={})
    assert client.post("/api/desktop/open-data-folder", json={}).status_code == 404


# ---------------------------------------------------------------------------
# No sign-in
# ---------------------------------------------------------------------------
def test_the_launcher_key_signs_the_window_in(desk):
    assert desk.get("/api/projects").status_code == 401
    r = desk.get(f"/desktop/start?k={KEY}")
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "taki_desktop=" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]
    m = desk.get("/api/meta").json()
    assert m["desktop"] is True and m["user"]["id"] == "desktop" and m["user"]["is_guest"] is False
    assert m["user"]["email"] is None and m["user"]["name"] and os.path.isdir(m["data_dir"])
    assert desk.get("/api/projects").json() == {"projects": []}
    p = desk.post("/api/projects", json={"name": "On this computer"}).json()["project"]
    assert desk.get(f"/api/projects/{p['id']}").status_code == 200


def test_a_wrong_key_gets_nothing(desk):
    r = desk.get("/desktop/start?k=not-the-key")
    assert r.status_code == 403 and "set-cookie" not in r.headers and "out of date" in r.text
    assert desk.get("/desktop/start").status_code == 403
    assert desk.get("/api/projects").status_code == 401


def test_an_old_address_still_works_in_a_window_that_is_signed_in(desk):
    """A pinned window carries the key of an earlier run in its address; its cookie is what counts."""
    from server import db
    desk.get(f"/desktop/start?k={KEY}")
    r = desk.get("/desktop/start?k=key-of-last-week")
    assert r.status_code == 303 and "taki_desktop=" in r.headers["set-cookie"]
    assert db.scalar("SELECT COUNT(*) AS n FROM sessions") == 1 and db.scalar("SELECT COUNT(*) AS n FROM users") == 1


def test_no_accounts_and_no_guests_on_the_desktop(desk):
    assert desk.post("/api/auth/guest", json={}).status_code == 403
    assert desk.post("/api/auth/register", json={"email": "a@b.co", "password": "correct horse"}).status_code == 403
    m = desk.get("/api/meta").json()
    assert m["allow_signup"] is False and m["allow_guests"] is False and m["user"] is None and "data_dir" not in m


def test_only_this_computer_is_answered(desk):
    """A page elsewhere that points a name of its own at 127.0.0.1 is turned away by its Host header."""
    assert desk.get("/api/health", headers={"Host": "evil.example:8254"}).status_code == 404
    assert desk.get(f"/desktop/start?k={KEY}", headers={"Host": "taki.attacker.test"}).status_code == 404
    for host in ("127.0.0.1:8254", "localhost:8254", "127.0.0.1", "[::1]:8254"):
        assert desk.get("/api/health", headers={"Host": host}).status_code == 200, host


def test_host_names_that_mean_this_computer():
    from server.desktop import host_allowed
    assert all(host_allowed(h) for h in ("127.0.0.1", "127.0.0.1:8254", "LOCALHOST:1", "[::1]", "[::1]:8254"))
    assert not any(host_allowed(h) for h in ("", None, "example.org", "127.0.0.1.example.org", "localhost.evil.test:80",
                                             "192.168.1.5:8254", "[::2]:8254"))


def test_the_desktop_account_is_made_once(desk):
    from server import auth, db
    a = auth.desktop_user("Aisha Rahman")
    b = auth.desktop_user("Someone Else")
    assert a["id"] == b["id"] == "desktop" and b["name"] == "Aisha Rahman" and a["email"] is None
    assert db.scalar("SELECT COUNT(*) AS n FROM users") == 1
    from server.desktop import default_user_name
    assert default_user_name().strip() and len(default_user_name()) <= 80


def test_the_presence_stream_needs_the_session(desk):
    assert desk.get("/api/desktop/presence").status_code == 401


# ---------------------------------------------------------------------------
# When it stops
# ---------------------------------------------------------------------------
def _snap(**kw):
    base = {"started": 1000.0, "windows": 0, "ever": False, "last_gone": 0.0, "owner_alive": False,
            "owner_exit": 0.0, "quit": False, "requests": 0}
    base.update(kw)
    return base


def test_it_stops_when_nobody_is_left_and_not_before():
    from server import desktop as d
    stop = d.should_stop
    # a page is open: never
    assert not stop(10**9, _snap(windows=1, ever=True))
    # asked to stop: at once, whatever is open
    assert stop(1001, _snap(windows=2, ever=True, quit=True))
    # still starting: the first window gets its time to load
    assert not stop(1000 + d.STARTUP_S - 1, _snap())
    assert stop(1000 + d.STARTUP_S + 1, _snap())
    # the app window was closed on purpose: its process ended as its page went
    closed = _snap(ever=True, last_gone=2000.0, owner_exit=2000.6)
    assert not stop(2000 + d.GRACE_S - 1, closed)
    assert stop(2000 + d.GRACE_S + 1, closed)
    # a reload: the page is gone for a moment but the browser lives
    assert not stop(2000 + 3600, _snap(ever=True, last_gone=2000.0, owner_alive=True))
    # ... which does not keep a forgotten browser process alive for ever
    assert stop(2000 + d.ZOMBIE_S + 1, _snap(ever=True, last_gone=2000.0, owner_alive=True))
    # the page was a tab of the usual browser (no process to watch), or the window belonged to a
    # browser that was already running (ours handed over and ended long ago): the long wait
    for tab in (_snap(ever=True, last_gone=2000.0), _snap(ever=True, last_gone=2000.0, owner_exit=1002.0)):
        assert not stop(2000 + d.GRACE_S + 5, tab)
        assert not stop(2000 + d.ORPHAN_S - 1, tab)
        assert stop(2000 + d.ORPHAN_S + 1, tab)
    # the window was closed before the page had loaded
    early = _snap(owner_exit=1004.0)
    assert not stop(1005, early)
    assert stop(1004 + 2 * d.GRACE_S + 1, early)


def test_the_state_counts_windows():
    from server.desktop import State
    s = State()
    s.key = "abc"
    assert s.check_key("abc") and not s.check_key("abd") and not s.check_key("") and not s.check_key(None)
    assert not State().check_key("")                 # no key set: nothing matches, not even nothing
    s.window_opened(); s.window_opened()
    assert s.snapshot()["windows"] == 2 and s.snapshot()["ever"]
    s.window_closed(); s.window_closed(); s.window_closed()
    snap = s.snapshot()
    assert snap["windows"] == 0 and snap["last_gone"] > 0 and not snap["owner_alive"]


def test_one_copy_at_a_time(tmp_path):
    from server.desktop import InstanceLock
    first, second = InstanceLock(str(tmp_path / "x.lock")), InstanceLock(str(tmp_path / "x.lock"))
    assert first.acquire() and not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


def test_the_running_copy_writes_down_where_it_listens(tmp_path):
    from server import desktop as d
    assert d.read_info(str(tmp_path)) is None
    d.write_info(str(tmp_path), {"pid": 1, "port": 8254, "key": "k"})
    assert d.read_info(str(tmp_path))["port"] == 8254
    if os.name != "nt":
        assert oct(os.stat(tmp_path / "desktop.json").st_mode)[-3:] == "600"
    assert d.probe({"port": 9, "key": "k"}, timeout=0.3) is None            # nothing answers there
    d.remove_info(str(tmp_path)); d.remove_info(str(tmp_path))
    assert d.read_info(str(tmp_path)) is None


def test_a_taken_port_is_stepped_around():
    from server.desktop import listen
    a = listen(0)
    port = a.getsockname()[1]
    b = listen(port)
    try:
        assert a.getsockname()[0] == "127.0.0.1" and b.getsockname()[1] != port
    finally:
        a.close(); b.close()


def test_the_window_command_and_the_data_folder(tmp_path, monkeypatch):
    from server import desktop as d
    cmd = d.window_command("/x/browser", "http://127.0.0.1:8254/desktop/start?k=K", str(tmp_path / "window"))
    assert cmd[0] == "/x/browser" and cmd[1] == "--app=http://127.0.0.1:8254/desktop/start?k=K"
    assert f"--user-data-dir={tmp_path / 'window'}" in cmd and "--no-first-run" in cmd
    assert d.open_window("http://x", str(tmp_path), "none") is None
    assert os.path.basename(d.default_data_dir()).lower() == "taki"
    monkeypatch.setenv("TAKI_BROWSER", str(tmp_path / "no-such-browser"))
    assert d.find_browser() is None


def test_edge_is_found_where_windows_keeps_it(tmp_path, monkeypatch):
    from server import desktop as d
    monkeypatch.delenv("TAKI_BROWSER", raising=False)
    monkeypatch.setattr(d.sys, "platform", "win32")
    monkeypatch.setattr(d.os.path, "join", lambda *parts: "/".join(p.replace("\\", "/") for p in parts))   # Windows paths, here
    monkeypatch.setattr(d, "_registry_app_path", lambda exe: None)
    for var in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        monkeypatch.setenv(var, str(tmp_path / var))
    assert d.find_browser() is None                                    # no browser at all: a tab of the usual one
    chrome = tmp_path / "PROGRAMFILES" / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"")
    assert d.find_browser() == str(chrome)
    edge = tmp_path / "PROGRAMFILES(X86)" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    assert d.find_browser() == str(edge)                               # Edge first: every Windows has it
    monkeypatch.setenv("TAKI_BROWSER", str(chrome))
    assert d.find_browser() == str(chrome)                             # unless told otherwise
    registered = tmp_path / "elsewhere" / "msedge.exe"
    registered.parent.mkdir()
    registered.write_bytes(b"")
    monkeypatch.delenv("TAKI_BROWSER")
    edge.unlink()
    monkeypatch.setattr(d, "_registry_app_path", lambda exe: str(registered) if exe == "msedge.exe" else None)
    assert d.find_browser() == str(registered)                         # an Edge the registry knows of


# ---------------------------------------------------------------------------
# The stand-in shown while the application loads
# ---------------------------------------------------------------------------
def test_the_stand_in_answers_until_the_application_is_there():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from server import desktop as d
    d.STATE.__init__()
    d.STATE.key = KEY
    try:
        boot = d.Boot(load=lambda: None)
        c = TestClient(boot, base_url="http://127.0.0.1:8254")
        r = c.get(f"/desktop/start?k={KEY}")
        assert r.status_code == 200 and "Starting Taki" in r.text and r.headers["cache-control"] == "no-store"
        r = c.get("/api/health")
        assert r.status_code == 503 and r.json()["starting"] is True and r.json()["ok"] is False
        assert d.STATE.requests == 2                                   # a window has asked for something
        alive = c.get(f"/api/desktop/alive?k={KEY}").json()
        assert alive["ok"] and alive["ready"] is False and alive["pid"] == os.getpid()
        assert c.get("/api/desktop/alive?k=wrong").status_code == 403
        assert d.STATE.requests == 2                                   # the launcher's own questions do not count

        boot.error = "ImportError: no numpy"
        r = c.get("/api/health")
        assert r.status_code == 500 and "no numpy" in r.json()["error"] and r.json()["starting"] is False
        boot.error = None

        real = FastAPI()
        real.add_api_route("/api/health", lambda: {"ok": True})
        boot.app = real
        assert c.get("/api/health").json() == {"ok": True}
        assert c.get(f"/api/desktop/alive?k={KEY}").json()["ready"] is True       # still answered by the stand-in

        assert c.post("/api/desktop/quit", headers={"X-Taki-Key": "wrong"}).status_code == 403 and not d.STATE.quit
        assert c.post("/api/desktop/quit", headers={"X-Taki-Key": KEY}).status_code == 200 and d.STATE.quit
    finally:
        d.STATE.__init__()


def test_a_failed_load_is_reported_not_raised():
    from server import desktop as d

    def broken():
        raise ImportError("No module named 'numpy'")

    boot = d.Boot(load=broken)
    boot.start_loading().join(5)
    assert boot.app is None and "numpy" in boot.error


# ---------------------------------------------------------------------------
# The real thing: start it, open a page, close the page, ask it to stop
# ---------------------------------------------------------------------------
def _get(port, path, cookie=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Cookie": cookie} if cookie else {}
    if host:
        headers["Host"] = host
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    body = res.read()
    conn.close()
    return res, body


def test_the_desktop_program_from_start_to_stop(tmp_path):
    data = str(tmp_path / "data")
    env = dict(os.environ, TAKI_DESKTOP_WINDOW="none", TAKI_DESKTOP_LOG="1")
    env.pop("TAKI_DATA_DIR", None)
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "desktop.py"), "--data-dir", data, "--port", "0"],
                            env=env, cwd=str(tmp_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        info = None
        for _ in range(100):
            try:
                info = json.load(open(os.path.join(data, "desktop.json")))
                break
            except (OSError, ValueError):
                time.sleep(0.1)
        assert info and info["pid"] == proc.pid
        port, key = info["port"], urllib.parse.quote(info["key"])

        res, body = _get(port, f"/desktop/start?k={key}")            # at once: the page, or already the redirect
        assert res.status in (200, 303)
        for _ in range(200):                                            # the real application takes over
            res, body = _get(port, "/api/health")
            if res.status == 200:
                break
            time.sleep(0.1)
        assert json.loads(body)["ok"] is True

        res, _ = _get(port, f"/desktop/start?k={key}")
        assert res.status == 303
        cookie = res.getheader("set-cookie").split(";")[0]
        assert cookie.startswith("taki_desktop=")
        res, body = _get(port, "/api/meta", cookie)
        meta = json.loads(body)
        assert meta["desktop"] and meta["user"]["id"] == "desktop" and os.path.samefile(meta["data_dir"], data)
        assert os.path.isfile(os.path.join(data, "taki.db")) and not os.path.exists(os.path.join(ROOT, "data", "desktop.json"))
        assert _get(port, "/api/health", host="rebound.example")[0].status == 404

        def windows():
            return json.loads(_get(port, f"/api/desktop/alive?k={key}")[1])["windows"]

        page = socket.create_connection(("127.0.0.1", port), timeout=10)     # an open page holds this stream
        page.sendall(f"GET /api/desktop/presence HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nCookie: {cookie}\r\n\r\n".encode())
        head = b""
        while b"retry: 1000" not in head:
            more = page.recv(4096)
            assert more, head
            head += more
        assert head.startswith(b"HTTP/1.1 200") and b"text/event-stream" in head
        assert windows() == 1
        page.close()                                                    # the window is closed
        for _ in range(50):
            if windows() == 0:
                break
            time.sleep(0.1)
        assert windows() == 0 and proc.poll() is None                   # noticed, and not stopped at once

        # a second start finds the first and does not start another
        again = subprocess.run([sys.executable, os.path.join(ROOT, "desktop.py"), "--data-dir", data], env=env,
                               cwd=str(tmp_path), timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert again.returncode == 0 and json.load(open(os.path.join(data, "desktop.json")))["pid"] == proc.pid

        quit_ = subprocess.run([sys.executable, os.path.join(ROOT, "desktop.py"), "--data-dir", data, "--quit"],
                               env=env, cwd=str(tmp_path), timeout=60)
        assert quit_.returncode == 0
        assert proc.wait(15) == 0 and not os.path.exists(os.path.join(data, "desktop.json"))
        assert "Taki desktop started" in open(os.path.join(data, "taki.log"), encoding="utf-8").read()
    finally:
        if proc.poll() is None:
            proc.kill()


# ---------------------------------------------------------------------------
# Export all
# ---------------------------------------------------------------------------
def test_every_project_goes_into_one_file(guest):
    from server import service
    cfg = service.default_config()
    a = guest.post("/api/projects", json={"name": "Alpha", "description": "first", "config": cfg}).json()["project"]
    guest.post(f"/api/projects/{a['id']}/scenarios", json={"name": "Half load", "note": "n", "config": cfg})
    guest.post("/api/projects", json={"name": "Beta", "config": cfg})
    r = guest.get("/api/projects/export")
    assert r.status_code == 200 and ".taki.json" in r.headers["content-disposition"]
    body = r.json()
    assert body["taki"] == "projects" and body["version"] == 4 and len(body["projects"]) == 2
    alpha = next(p for p in body["projects"] if p["name"] == "Alpha")
    assert alpha["description"] == "first" and alpha["config"]["lines"] and alpha["scenarios"][0]["name"] == "Half load"
    assert "id" not in alpha and "user_id" not in alpha
    # what comes out goes back in as it is
    again = guest.post("/api/projects", json={"name": alpha["name"], "config": alpha["config"]})
    assert again.status_code == 200


def test_the_export_is_only_for_its_owner(client):
    assert client.get("/api/projects/export").status_code == 401


# ---------------------------------------------------------------------------
# The download
# ---------------------------------------------------------------------------
def test_the_download_holds_the_program_and_nothing_else(client):
    from server import config, desktop_package
    assert desktop_package.available()
    r = client.get("/api/desktop/package")                              # no sign-in needed
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert f'filename="Taki-Desktop-{config.VERSION}.zip"' in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    top = f"Taki-Desktop-{config.VERSION}/"
    assert all(n.startswith(top) for n in names) and len(names) == len(set(names))
    inside = {n[len(top):] for n in names}
    for must in ("Install Taki.bat", "READ ME.txt", "start-desktop.sh", "app/desktop.py", "app/run.py",
                 "app/requirements-desktop.lock", "app/tools/desktop_setup.py", "app/server/main.py",
                 "app/server/desktop.py", "app/engine/physics.py", "app/engine/benchmark_data/fikry2022_f1000research.json",
                 "app/server/static/index.html", "app/server/static/manifest.webmanifest",
                 "app/server/static/icons/taki.ico", "app/install-desktop.bat"):
        assert must in inside, must
    assert any(re.fullmatch(r"app/tools/wheels/pip-[\d.]+-py3-none-any\.whl", n) for n in inside)
    assert any(n.startswith("app/server/static/assets/") and n.endswith(".js") for n in inside)
    # nothing private, nothing that is not needed to run it
    for n in inside:
        assert not re.search(r"(^|/)(\.env|data|tests|web|node_modules|__pycache__|\.venv|\.git)(/|$)", n), n
        assert not n.endswith((".pyc", ".db", ".log", ".sqlite")), n
    # Windows scripts and the note carry Windows line ends; the shell script can be run
    for name in ("Install Taki.bat", "app/install-desktop.bat", "READ ME.txt"):
        text = z.read(top + name)
        assert b"\r\n" in text and b"\n" not in text.replace(b"\r\n", b""), name
    assert (z.getinfo(top + "start-desktop.sh").external_attr >> 16) & 0o111
    assert config.VERSION in z.read(top + "READ ME.txt").decode()
    assert z.read(top + "app/server/config.py") == open(os.path.join(ROOT, "server", "config.py"), "rb").read()
    assert desktop_package.build()[0] is desktop_package.build()[0]     # built once, then kept


def test_files_left_by_an_older_build_stay_out_of_the_download(tmp_path, monkeypatch, setup_script):
    """A folder copied over an older one keeps the older interface files: their names differ, nothing replaces them."""
    from server import config, desktop_package
    loaded = desktop_package.interface_assets()                          # what this copy's page really loads
    assert loaded and any(n.endswith(".css") for n in loaded) and sum(n.endswith(".js") for n in loaded) >= 3
    shutil.copytree(os.path.join(ROOT, "server", "static"), tmp_path / "server" / "static")
    assets = tmp_path / "server" / "static" / "assets"
    (assets / "index-0ldBu1ld.js").write_text("import('./TwinPage-0ldBu1ld.js')")
    (assets / "TwinPage-0ldBu1ld.js").write_text("an older page")
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    assert desktop_package.interface_assets() == loaded
    inside = {name for _, name in desktop_package.files()}
    assert {n for n in inside if "/static/assets/" in n} == {"app/server/static/assets/" + n for n in loaded}
    assert "app/server/static/index.html" in inside and "app/server/static/icons/taki.ico" in inside
    # the installer goes by the same rule, so what it copies is what the download carries
    assert setup_script.interface_assets(str(tmp_path)) == loaded
    assert {"app/" + rel for _, rel in setup_script.program_files(str(tmp_path))} == inside
    # without the page to read, nothing is guessed: every file is taken
    os.remove(tmp_path / "server" / "static" / "index.html")
    assert desktop_package.interface_assets() is None and setup_script.interface_assets(str(tmp_path)) is None
    assert any("0ldBu1ld" in name for _, name in desktop_package.files())


def test_the_download_can_be_switched_off(client, monkeypatch):
    from server import config
    monkeypatch.setattr(config, "ALLOW_DESKTOP_DOWNLOAD", False)
    assert client.get("/api/desktop/package").status_code == 404
    assert client.get("/api/meta").json()["desktop_download"] is False


# ---------------------------------------------------------------------------
# The installer
# ---------------------------------------------------------------------------
def test_the_installer_copies_what_the_download_carries(setup_script):
    from server import desktop_package
    copied = {rel for _, rel in setup_script.program_files(ROOT)}
    carried = {name[len("app/"):] for _, name in desktop_package.files() if name.startswith("app/")}
    assert copied == carried and set(desktop_package.AT_TOP) <= copied


def test_the_program_is_copied_whole_and_replaced_whole(setup_script, tmp_path):
    app = str(tmp_path / "Taki" / "app")
    n = setup_script.copy_program(ROOT, app)
    assert n > 40 and os.path.isfile(os.path.join(app, "server", "static", "index.html"))
    assert os.path.isfile(os.path.join(app, "desktop.py")) and not os.path.exists(os.path.join(app, "tests"))
    assert not os.path.exists(os.path.join(app, ".env")) and not os.path.exists(os.path.join(app, "data"))
    from server import config
    assert setup_script.app_version(app) == config.VERSION
    open(os.path.join(app, "left-over.txt"), "w").close()               # an update leaves nothing of the old copy
    setup_script.copy_program(ROOT, app)
    assert not os.path.exists(os.path.join(app, "left-over.txt")) and not os.path.exists(app + ".old")
    assert setup_script.copy_program(app, app) == n                     # repairing from the installed copy
    # the installed copy can make the same download again
    assert {rel for _, rel in setup_script.program_files(app)} == {rel for _, rel in setup_script.program_files(ROOT)}


def test_a_folder_that_is_not_taki_is_refused(setup_script, tmp_path):
    (tmp_path / "src").mkdir()
    with pytest.raises(setup_script.SetupError, match="Extract All"):
        setup_script.copy_program(str(tmp_path / "src"), str(tmp_path / "app"))
    assert not os.path.exists(tmp_path / "app")


def test_the_private_python_is_told_where_to_look(setup_script, tmp_path):
    pth = tmp_path / "python313._pth"
    pth.write_bytes(b"python313.zip\r\n.\r\n\r\n# Uncomment to run site.main() automatically\r\n#import site\r\n")
    setup_script.patch_pth(str(tmp_path))
    want = ["python313.zip", ".", "Lib\\site-packages", "..\\app", "import site"]
    assert pth.read_bytes().decode().split("\r\n")[:-1] == want
    setup_script.patch_pth(str(tmp_path))                               # a second install changes nothing
    assert pth.read_bytes().decode().split("\r\n")[:-1] == want
    assert os.path.isdir(tmp_path / "Lib" / "site-packages")
    with pytest.raises(setup_script.SetupError):
        setup_script.patch_pth(str(tmp_path / "Lib"))


def test_the_pip_that_comes_along_is_checked(setup_script, tmp_path):
    wheel = setup_script.find_pip_wheel(ROOT, [])
    name = os.path.basename(wheel)
    assert name in setup_script.PIP_SHA256 and setup_script.sha256(wheel) == setup_script.PIP_SHA256[name]
    bad = tmp_path / "tools" / "wheels"
    bad.mkdir(parents=True)
    (bad / name).write_bytes(open(wheel, "rb").read()[:-10] + b"0123456789")
    with pytest.raises(setup_script.SetupError, match="damaged"):
        setup_script.find_pip_wheel(str(tmp_path), [])
    with pytest.raises(setup_script.SetupError, match="incomplete"):
        setup_script.find_pip_wheel(str(tmp_path / "nowhere"), [])
    assert setup_script.offline_wheels(str(tmp_path)) is None
    (tmp_path / "wheels").mkdir()
    (tmp_path / "wheels" / "numpy-2.0-cp313-cp313-win_amd64.whl").write_bytes(b"")
    assert setup_script.offline_wheels(str(tmp_path)) == str(tmp_path / "wheels")


def test_the_installer_finds_its_python_and_refuses_odd_places(setup_script, tmp_path):
    assert setup_script.interpreters(str(tmp_path)) == ("", "", "")
    exe = "python.exe" if os.name == "nt" else "python"
    scripts = tmp_path / "venv" / ("Scripts" if os.name == "nt" else "bin")
    scripts.mkdir(parents=True)
    (scripts / exe).write_bytes(b"")
    assert setup_script.interpreters(str(tmp_path))[2] == "venv"
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / exe).write_bytes(b"")
    assert setup_script.interpreters(str(tmp_path))[2] == "private"   # its own Python wins
    with pytest.raises(setup_script.SetupError, match="not installed"):
        setup_script.uninstall(str(tmp_path), yes=True)                 # no app folder: nothing is removed
    assert os.path.isdir(tmp_path / "python")
    assert setup_script.main(["uninstall", "--dest", os.path.abspath(os.sep), "--yes"]) == 2


@pytest.mark.skipif(os.name == "nt", reason="on Windows the last step is left to the system")
def test_uninstalling_keeps_the_projects_unless_told_otherwise(setup_script, tmp_path, monkeypatch):
    def installed():
        dest, data = tmp_path / "Programs" / "Taki", tmp_path / "data"
        setup_script.copy_program(ROOT, str(dest / "app"))
        for folder in ("window", "cache"):
            (data / folder).mkdir(parents=True, exist_ok=True)
            (data / folder / "x").write_bytes(b"x")
        for name in ("taki.db", "taki.log", "desktop.lock"):
            (data / name).write_bytes(b"x")
        monkeypatch.setenv("TAKI_DESKTOP_DATA_DIR", str(data))
        return dest, data

    dest, data = installed()
    assert setup_script.data_folder(str(dest)) == str(data)
    assert setup_script.uninstall(str(dest), yes=True) == 0
    assert not dest.exists() and sorted(os.listdir(data)) == ["taki.db"]         # the program is gone, the work is not
    dest, data = installed()
    assert setup_script.main(["uninstall", "--dest", str(dest), "--yes", "--delete-data"]) == 0
    assert not dest.exists() and not data.exists()
    monkeypatch.delenv("TAKI_DESKTOP_DATA_DIR")
    assert os.path.basename(setup_script.data_folder(str(dest))).lower() == "taki"


class _Registry:
    """Stands in for the winreg module: remembers what was written."""
    HKEY_CURRENT_USER, REG_SZ, REG_DWORD = "HKCU", 1, 4

    def __init__(self):
        self.values, self.deleted = {}, []

    def CreateKey(self, hive, path):
        registry = self

        class Key:
            def __enter__(self):
                return (hive, path)

            def __exit__(self, *exc):
                return False
        registry.path = path
        return Key()

    def SetValueEx(self, key, name, _reserved, kind, value):
        self.values[name] = (kind, value)

    def DeleteKey(self, hive, path):
        self.deleted.append((hive, path))


def _windows_stand_ins(setup_script, tmp_path, monkeypatch):
    """Windows is not here. Its commands are replaced by stand-ins that note what they were asked."""
    dest = tmp_path / "Programs" / "Taki"
    (dest / "python").mkdir(parents=True)
    for exe in ("python.exe", "pythonw.exe"):
        (dest / "python" / exe).write_bytes(b"")
    (dest / "python" / "python313._pth").write_text("python313.zip\n.\n\n#import site\n")
    places = {setup_script.CSIDL_DESKTOP: tmp_path / "Desktop", setup_script.CSIDL_PROGRAMS: tmp_path / "Start Menu"}
    for folder in places.values():
        folder.mkdir(exist_ok=True)
    seen = {"run": [], "links": [], "pip": [], "started": [], "registry": _Registry()}

    def run(cmd, cwd=None, env=None, timeout=None, quiet=False):
        seen["run"].append(cmd)
        if "-Command" in cmd:                                     # PowerShell making a shortcut
            seen["links"].append({k: v for k, v in env.items() if k.startswith("TAKI_LNK")})
            open(env["TAKI_LNK"], "w").close()
        return 0

    monkeypatch.setattr(setup_script, "WINDOWS", True)
    monkeypatch.setattr(setup_script, "interpreters", lambda d: (os.path.join(d, "python", "python.exe"),
                                                                 os.path.join(d, "python", "pythonw.exe"), "private"))
    monkeypatch.setattr(setup_script, "shell_folder", lambda csidl: str(places[csidl]))
    monkeypatch.setattr(setup_script, "run", run)
    monkeypatch.setattr(setup_script, "pip_install", lambda pip, lock, wheels, cache=None: seen["pip"].append((pip, lock, wheels, cache)))
    monkeypatch.setitem(sys.modules, "winreg", seen["registry"])
    monkeypatch.setattr(subprocess, "DETACHED_PROCESS", 0x8, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(setup_script.subprocess, "Popen", lambda *a, **k: seen["started"].append((a, k)))
    return dest, places, seen


@pytest.mark.skipif(os.name == "nt", reason="uses stand-ins for Windows")
def test_the_windows_steps_of_the_installer_hang_together(setup_script, tmp_path, monkeypatch):
    from server import config
    dest, places, seen = _windows_stand_ins(setup_script, tmp_path, monkeypatch)
    assert setup_script.main(["install", "--source", ROOT, "--dest", str(dest)]) == 0
    app, python, pythonw = dest / "app", str(dest / "python" / "python.exe"), str(dest / "python" / "pythonw.exe")
    assert (app / "server" / "main.py").is_file() and "import site" in (dest / "python" / "python313._pth").read_text()

    (pip, lock, wheels, cache), = seen["pip"]                       # pip is run from its wheel, with the lock file
    assert pip[0] == python and re.search(r"tools[\\/]wheels[\\/]pip-[\d.]+-py3-none-any\.whl/pip$", pip[1])
    assert lock == str(app / "requirements-desktop.lock") and wheels is None
    assert cache == str(dest / "cache" / "pip") and not (dest / "cache").exists()     # kept in its folder, gone when done
    check = next(c for c in seen["run"] if c[:2] == [python, "-c"])
    assert "import server.main" in check[2] and "numpy" in check[2]

    links = {os.path.relpath(l["TAKI_LNK"], tmp_path): l for l in seen["links"]}
    assert set(links) == {"Desktop/Taki.lnk", "Start Menu/Taki.lnk", "Start Menu/Uninstall Taki.lnk"}
    for name in ("Desktop/Taki.lnk", "Start Menu/Taki.lnk"):
        link = links[name]
        assert link["TAKI_LNK_TARGET"] == pythonw and link["TAKI_LNK_ARGS"] == f'"{app / "desktop.py"}"'
        assert link["TAKI_LNK_DIR"] == str(app) and os.path.isfile(link["TAKI_LNK_ICON"])
    uninstaller = dest / "Uninstall Taki.bat"
    assert links["Start Menu/Uninstall Taki.lnk"]["TAKI_LNK_TARGET"] == str(uninstaller)
    bat = uninstaller.read_bytes()
    assert bat.count(b"\n") == bat.count(b"\r\n") >= 4 and bat.startswith(b"@echo off\r\n")
    assert all(b < 128 for b in bat)                                # it names no folder, so any user name works
    assert b'"%~dp0python\\python.exe" "%~dp0app\\tools\\desktop_setup.py" uninstall --dest "%~dp0."' in bat
    plain = setup_script._batch_text(["@echo off", 'start "" "C:\\Users\\ana\\x.exe"'])
    other = setup_script._batch_text(["@echo off", 'start "" "C:\\Users\\J\u00fcrgen\\x.exe"'])
    assert b"chcp" not in plain and other.split(b"\r\n")[1] == b"chcp 65001 >nul" and "J\u00fcrgen".encode("utf-8") in other

    reg = seen["registry"]
    assert reg.path.endswith("Uninstall\\Taki") and reg.values["DisplayName"] == (reg.REG_SZ, "Taki")
    assert reg.values["DisplayVersion"] == (reg.REG_SZ, config.VERSION)
    assert reg.values["UninstallString"] == (reg.REG_SZ, f'"{uninstaller}"') and reg.values["NoModify"] == (reg.REG_DWORD, 1)
    assert reg.values["EstimatedSize"][1] > 1000

    (args, kw), = seen["started"]                                   # and Taki is started, on its own
    assert args[0] == [pythonw, str(app / "desktop.py")] and kw["cwd"] == str(app) and kw["creationflags"] == 0x208
    log = (dest / "install.log").read_text()
    assert "5 of 5" in log and f"Taki {config.VERSION} is installed" in log

    # a second run updates in place, and asks the running copy to stop first
    seen["run"].clear()
    assert setup_script.main(["install", "--source", ROOT, "--dest", str(dest), "--no-start", "--no-shortcuts"]) == 0
    assert seen["run"][0] == [python, str(app / "desktop.py"), "--quit"] and len(seen["started"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="uses stand-ins for Windows")
def test_the_windows_steps_of_the_uninstaller_hang_together(setup_script, tmp_path, monkeypatch):
    dest, places, seen = _windows_stand_ins(setup_script, tmp_path, monkeypatch)
    setup_script.copy_program(ROOT, str(dest / "app"))
    data = tmp_path / "data"
    data.mkdir()
    (data / "taki.db").write_bytes(b"x")
    monkeypatch.setenv("TAKI_DESKTOP_DATA_DIR", str(data))
    for folder, name in ((places[setup_script.CSIDL_DESKTOP], "Taki.lnk"), (places[setup_script.CSIDL_PROGRAMS], "Taki.lnk"),
                         (places[setup_script.CSIDL_PROGRAMS], "Uninstall Taki.lnk"), (places[setup_script.CSIDL_DESKTOP], "Other.lnk")):
        (folder / name).write_bytes(b"")
    assert setup_script.main(["uninstall", "--dest", str(dest), "--yes"]) == 0
    assert os.listdir(places[setup_script.CSIDL_DESKTOP]) == ["Other.lnk"] and not os.listdir(places[setup_script.CSIDL_PROGRAMS])
    assert seen["registry"].deleted and seen["registry"].deleted[0][1].endswith("Uninstall\\Taki")
    assert (data / "taki.db").is_file()                              # --yes never deletes the work
    assert seen["run"][0][-1] == "--quit"                            # a running copy is stopped first
    (args, kw), = seen["started"]                                    # the folder itself is removed by the system, afterwards
    assert args[0] == f'cmd.exe /d /c "ping -n 3 127.0.0.1 >nul & rmdir /s /q "{dest}""'
    assert os.path.realpath(kw["cwd"]) != os.path.realpath(dest) and dest.exists()


def test_the_lock_file_pins_everything(setup_script):
    text = open(os.path.join(ROOT, "requirements-desktop.lock"), encoding="utf-8").read()
    pins = re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s\\;]+)", text, re.M)
    names = {n.lower() for n, _ in pins}
    wanted = {ln.split(">=")[0].strip().lower() for ln in
              open(os.path.join(ROOT, "requirements-desktop.txt"), encoding="utf-8") if ">=" in ln and not ln.startswith("#")}
    assert wanted == {"fastapi", "uvicorn", "numpy", "matplotlib", "reportlab", "python-docx"} and wanted <= names
    assert "psycopg" not in names and "psycopg-binary" not in names      # the desktop version has no online database
    blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", text)
    assert all("--hash=sha256:" in b for b in blocks if "==" in b.split("\n")[0])
    assert not re.search(r"^[A-Za-z0-9_.\-]+\s*(>=|~=|<|>)", text, re.M)
    # the versions this test run is using are the pinned ones, when it runs on the lock file's own set
    web = {ln.split(">=")[0].strip().lower() for ln in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8")
           if ">=" in ln and not ln.startswith("#")}
    assert wanted | {"psycopg[binary]"} == web


def _labels_and_jumps(text):
    labels = {m.group(1).lower() for m in re.finditer(r"^:([A-Za-z_][\w]*)\s*$", text, re.M)}
    jumps = {m.group(1).lower() for m in re.finditer(r"\b(?:goto|call)\s+:?([A-Za-z_][\w]*)\b(?!\.)", text, re.I)
             if m.group(1).lower() not in ("eof",)}
    return labels, jumps


def test_the_batch_file_avoids_the_usual_traps():
    raw = open(os.path.join(ROOT, "install-desktop.bat"), "rb").read()
    assert raw.count(b"\n") == raw.count(b"\r\n") > 100                # Windows line ends throughout
    assert all(b < 128 for b in raw)                                    # plain ASCII: no code-page surprises
    text = raw.decode("ascii").replace("\r\n", "\n")
    code = [ln for ln in text.split("\n") if ln.strip() and not ln.lower().startswith("rem")]
    assert code[0] == "@echo off" and any(ln.startswith("setlocal") for ln in code)
    labels, jumps = _labels_and_jumps("\n".join(code))
    assert jumps <= labels, jumps - labels                              # every goto and call has somewhere to land
    assert {"done", "failed", "not_extracted", "no_python", "end", "download", "have_python"} <= labels
    for ln in code:
        # no blocks in brackets: a folder named "Taki (1)" or "R&D" must not be able to break the script
        assert not re.search(r"\(\s*$", ln) and not ln.strip().startswith(")"), ln
        assert "!" not in ln, ln                                        # nothing depends on delayed expansion
        if re.match(r"\s*echo\b", ln, re.I):                            # what is shown cannot be taken for a command
            shown = re.sub(r'"[^"]*"', "", ln)
            assert not re.search(r"[&|<>^]", shown), ln
        for var in re.findall(r"%(SRC|DEST|PY|PYDIR|PYZIP|TMPZIP|HERE|CURLEXE|TAREXE|TAKI_OUT|TAKI_URL)%", ln):
            # paths are always inside quotes when they are used
            for m in re.finditer("%" + var + r"%[^\s\"]*", ln):
                before = ln[:m.start()]
                assert before.count('"') % 2 == 1, ln
    assert "https://www.python.org/ftp/python/%1/python-%1-embed-amd64.zip" in text
    assert 'tools\\desktop_setup.py" install --source "%SRC%" --dest "%DEST%"' in text
    assert 'set "DEST=%BASE%\\Programs\\Taki"' in text and 'set "BASE=%LOCALAPPDATA%"' in text
    assert "pause >nul" in text and text.rstrip().endswith("endlocal & exit /b %RC%")
    assert text.index('set "RC=1"') < text.index(":done") < text.index('set "RC=0"') < text.index(":in_use")
    series = re.search(r'set "PYSERIES=(\d+\.\d+)"', text).group(1)
    versions = re.search(r'set "PYVERSIONS=([\d. ]+)"', text).group(1).split()
    assert versions and all(v.startswith(series + ".") for v in versions)
    assert f"sys.version_info[:2] == ({series.replace('.', ', ')})" in text


# The batch file cannot run here. What can be done is to walk it through, line by line, with a
# stand-in for cmd.exe (tests/batch_sim.py) and stand-ins for the programs it starts, in each
# situation it has to cope with. The folder names carry a space, brackets and an ampersand on
# purpose: unquoted, any of them breaks a batch file.
HOME = r"C:\Users\Ana R&D (x64)"
LOCAL = HOME + r"\AppData\Local"
DEST = LOCAL + r"\Programs\Taki"
PY = DEST + r"\python\python.exe"
UNZIPPED = HOME + r"\Downloads\Taki-Desktop-4.3.0 (1)"
TMPZIP = LOCAL + r"\Temp\taki-python-embed.zip"


class PretendWindows:
    """What the programs the installer starts would do on one imagined computer."""

    def __init__(self, online=("3.13.16", "3.13.15", "3.13.9"), curl=True, powershell=True, tar=True,
                 series_ok=True, python_runs=True, has_py=False, has_python=False, setup_exit=0, rmdir_fails=False):
        self.__dict__.update(locals())
        self.fetches, self.setup = [], None

    def __call__(self, argv, bat):
        from batch_sim import norm
        name, rest = norm(argv[0]).rsplit("\\", 1)[-1], [a.strip('"') for a in argv[1:]]
        version = lambda url: re.search(r"/python/([\d.]+)/python-\1-embed-amd64\.zip$", url).group(1)
        if name == "curl.exe":
            out, url = rest[rest.index("--output") + 1], rest[-1]
            self.fetches.append(("curl", version(url)))
            if self.curl and version(url) in self.online:
                bat.add(out)
                return 0
            return 22
        if name == "powershell":
            if "Invoke-WebRequest" in rest[-1]:
                self.fetches.append(("powershell", version(bat.env["TAKI_URL"])))
                if self.powershell and version(bat.env["TAKI_URL"]) in self.online:
                    bat.add(bat.env["TAKI_OUT"])
                    return 0
                return 1
            assert "Expand-Archive" in rest[-1], rest
            if self.powershell and bat.exists(bat.env["TAKI_ZIP"]):
                bat.add(bat.env["TAKI_DIR"] + "\\python.exe")
                return 0
            return 1
        if name == "tar.exe":
            if self.tar and bat.exists(rest[rest.index("-xf") + 1]):
                bat.add(rest[rest.index("-C") + 1] + "\\python.exe")
                return 0
            return 1
        if name == "rmdir":
            return 1 if self.rmdir_fails else 0
        if name in ("python.exe", "py", "python"):
            if name != "python.exe" and not {"py": self.has_py, "python": self.has_python}[name]:
                return 9009                                             # "is not recognized as a command"
            args = rest[1:] if name == "py" else rest
            if args[0] == "-c":
                if name == "python.exe":
                    return 0 if (self.python_runs if args[1] == "import sys" else self.series_ok) else 1
                return 0
            if args[-1] == "--quit":
                return 0
            assert args[1] == "install", argv
            self.setup = (name, args)
            return self.setup_exit
        raise AssertionError(f"the installer started something unexpected: {argv}")


def _install(files=(), layout="download", argv=(), env=None, **computer):
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from batch_sim import Batch
    text = open(os.path.join(ROOT, "install-desktop.bat"), newline="").read()
    if layout == "download":                       # as unzipped from the download: the program is in app\
        script, src = UNZIPPED + r"\Install Taki.bat", UNZIPPED + r"\app"
    else:                                          # as in the project folder: beside run.py
        script, src = UNZIPPED + r"\install-desktop.bat", UNZIPPED
    have = {script, r"C:\Windows\System32\curl.exe", r"C:\Windows\System32\tar.exe",
            src + r"\desktop.py", src + r"\tools\desktop_setup.py", src + r"\server\main.py"}
    have = (have | set(files)) - {f[1:] for f in files if f.startswith("-")}
    settings = {"LOCALAPPDATA": LOCAL, "TEMP": LOCAL + r"\Temp", "SystemRoot": r"C:\Windows", "USERPROFILE": HOME,
                "PROCESSOR_ARCHITECTURE": "AMD64"}
    settings.update(env or {})
    win = PretendWindows(**computer)
    bat = Batch(text, script, have, settings, win, argv)
    code = bat.run()
    return code, bat, win, src


def _programs(bat):
    from batch_sim import norm
    return [norm(w[0]).rsplit("\\", 1)[-1] for w in bat.ran]


def test_the_installer_on_a_fresh_computer():
    code, bat, win, src = _install()
    assert code == 0 and win.fetches == [("curl", "3.13.16")]           # one download, the newest
    assert _programs(bat) == ["curl.exe", "tar.exe", "python.exe", "python.exe"]
    assert win.setup == ("python.exe", [src + r"\tools\desktop_setup.py", "install", "--source", src, "--dest", DEST])
    assert bat.exists(PY) and not bat.exists(TMPZIP) and not bat.exists(TMPZIP + ".part")
    shown = "\n".join(bat.said)
    assert "Fetching Python 3.13.16" in shown and "Unpacking Python" in shown and "Done." in shown
    assert "3.13.15" not in shown and "did not finish" not in shown


def test_the_installer_from_the_project_folder_and_with_arguments():
    code, bat, win, src = _install(layout="project", argv=["--no-start"])
    assert code == 0 and src == UNZIPPED
    assert win.setup[1] == [UNZIPPED + r"\tools\desktop_setup.py", "install", "--source", UNZIPPED, "--dest", DEST,
                            "--no-start"]


def test_the_installer_when_a_version_is_missing_or_a_tool_is():
    # python.org does not carry the first version: the next one is fetched, quietly
    code, bat, win, _ = _install(online=("3.13.15", "3.13.9"))
    assert code == 0 and win.fetches == [("curl", "3.13.16"), ("powershell", "3.13.16"), ("curl", "3.13.15")]
    # an older Windows without curl and without tar: PowerShell does both jobs
    code, bat, win, _ = _install(files=[r"-C:\Windows\System32\curl.exe", r"-C:\Windows\System32\tar.exe"])
    assert code == 0 and win.fetches == [("powershell", "3.13.16")] and _programs(bat)[:2] == ["powershell", "powershell"]
    # curl is there but blocked; tar is there but cannot read the file
    code, bat, win, _ = _install(curl=False, tar=False)
    assert code == 0 and win.fetches == [("curl", "3.13.16"), ("powershell", "3.13.16")]
    assert _programs(bat) == ["curl.exe", "powershell", "tar.exe", "powershell", "python.exe", "python.exe"]


def test_the_installer_after_an_attempt_that_broke_off():
    # a half-fetched file from last time is not taken for a good one: it is fetched again
    code, bat, win, _ = _install(files=[TMPZIP, TMPZIP + ".part"])
    assert code == 0 and win.fetches == [("curl", "3.13.16")] and not bat.exists(TMPZIP)


def test_the_installer_without_python_org():
    # no download works, but Python is on the computer: it is used, through the py launcher or by name
    code, bat, win, src = _install(online=(), has_py=True)
    assert code == 0 and win.setup[0] == "py" and win.setup[1][2:] == ["--source", src, "--dest", DEST]
    assert len(win.fetches) == 6 and not bat.exists(DEST + r"\python")
    code, bat, win, _ = _install(online=(), has_python=True)
    assert code == 0 and win.setup[0] == "python"
    # nothing at all: it says what to do and changes nothing
    code, bat, win, _ = _install(online=())
    assert code == 1 and win.setup is None and "none was found on this computer" in "\n".join(bat.said)
    # the download arrived but will not unpack, and there is no other Python
    code, bat, win, _ = _install(tar=False, powershell=False, curl=True)
    assert code == 1 and win.setup is None and not bat.exists(TMPZIP)
    # a zip put beside the installer by hand is used, and nothing is fetched
    code, bat, win, _ = _install(files=[UNZIPPED + r"\python-3.13.11-embed-amd64.zip"], online=())
    assert code == 0 and win.fetches == [] and bat.exists(PY)
    assert bat.exists(UNZIPPED + r"\python-3.13.11-embed-amd64.zip")       # their file is left alone


def test_the_installer_over_an_earlier_installation():
    earlier = [PY, DEST + r"\app\desktop.py"]
    # the same Python: nothing is fetched; a running copy is asked to stop first
    code, bat, win, _ = _install(files=earlier)
    assert code == 0 and win.fetches == [] and bat.ran[0][-1] == "--quit" and win.setup[0] == "python.exe"
    # a Python of another series: it is replaced
    code, bat, win, _ = _install(files=earlier, series_ok=False)
    assert code == 0 and win.fetches == [("curl", "3.13.16")] and "Replacing the Python" in "\n".join(bat.said)
    # ... unless its files are in use, which is said and nothing more is done
    code, bat, win, _ = _install(files=earlier, series_ok=False, rmdir_fails=True)
    assert code == 1 and win.setup is None and "in use" in "\n".join(bat.said)


def test_the_installer_says_what_went_wrong():
    code, bat, win, _ = _install(setup_exit=2)                           # the Python part reported a problem
    assert code == 1 and "did not finish" in "\n".join(bat.said) and DEST + r"\install.log" in "\n".join(bat.said)
    code, bat, win, _ = _install(files=["-" + UNZIPPED + r"\app\tools\desktop_setup.py"])   # run from inside the zip
    assert code == 1 and bat.ran == [] and "Extract All" in "\n".join(bat.said)
    code, bat, win, _ = _install(env={"PROCESSOR_ARCHITECTURE": "x86"})  # 32-bit Windows
    assert code == 1 and bat.ran == [] and "64-bit" in "\n".join(bat.said)
    code, bat, win, _ = _install(env={"PROCESSOR_ARCHITECTURE": "x86", "PROCESSOR_ARCHITEW6432": "AMD64"})
    assert code == 0                                                     # a 32-bit prompt on 64-bit Windows is fine
    code, bat, win, _ = _install(python_runs=False)                      # a Windows too old for this Python
    assert code == 1 and win.setup is None and "does not run on this computer" in "\n".join(bat.said)
    for run in (_install(), _install(online=()), _install(setup_exit=2)):
        assert run[1].said[-1].startswith("Press any key")               # every ending waits to be read


def test_the_stand_in_for_cmd_is_strict():
    """It must fail where cmd.exe would, or passing it means nothing."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from batch_sim import Batch, BatchError
    run = lambda text: Batch(text, r"C:\x\a.bat", {r"C:\x\a.bat"}, {"P": r"C:\R&D (1)\f"}, lambda a, b: 0).run()
    assert run('set "A=1"\nif defined A goto ok\nexit /b 5\n:ok\nexit /b 7') == 7
    assert run('if exist "%P%" exit /b 1\nmkdir "%P%"\nif exist "%P%" exit /b 2') == 2
    assert run('for %%V in (a b c) do call :sub %%V\nexit /b 0\n:sub\nif "%1"=="b" exit /b 3\nexit /b 0') == 0
    for broken in ('goto nowhere', 'call :nowhere', 'echo saved in %P%', 'if exist %P% exit /b 1', 'mkdir %P%',
                   'set A=1', ':a\ngoto a'):
        with pytest.raises(BatchError):
            run(broken)


def test_the_shell_script_is_sound():
    path = os.path.join(ROOT, "start-desktop.sh")
    assert open(path, "rb").read().count(b"\r") == 0
    assert subprocess.run(["sh", "-n", path]).returncode == 0
    text = open(path, encoding="utf-8").read()
    assert "requirements-desktop.lock" in text and text.rstrip().endswith('exec .venv/bin/python desktop.py "$@"')


# ---------------------------------------------------------------------------
# Installing from the browser
# ---------------------------------------------------------------------------
def test_the_site_can_be_installed_from_a_browser(client):
    from server import config
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["name"] == "Taki" and m["display"] == "standalone" and m["start_url"] == "/" and m["scope"] == "/"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes and any(i.get("purpose") == "maskable" for i in m["icons"])
    for icon in m["icons"]:
        got = client.get(icon["src"])
        assert got.status_code == 200 and got.headers["content-type"].startswith(icon["type"]), icon
    page = client.get("/").text
    assert 'rel="manifest" href="/manifest.webmanifest"' in page and 'rel="apple-touch-icon"' in page
    ico = open(os.path.join(config.STATIC_DIR, "icons", "taki.ico"), "rb").read()
    assert ico[:4] == b"\x00\x00\x01\x00" and int.from_bytes(ico[4:6], "little") >= 6     # an icon file with several sizes


def test_the_desktop_window_does_not_offer_to_install_itself(desk):
    r = desk.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    assert r.json()["display"] == "browser" and r.json()["name"] == "Taki"      # a browser installs only "standalone"


def test_built_files_are_kept_by_the_browser_but_the_page_is_not(client):
    from server import config
    asset = sorted(n for n in os.listdir(os.path.join(config.STATIC_DIR, "assets")) if n.endswith(".css"))[0]
    r = client.get(f"/assets/{asset}")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"] and "max-age=31536000" in r.headers["cache-control"]
    assert client.get("/assets/no-such-file.js").headers.get("cache-control", "") != r.headers["cache-control"]
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
