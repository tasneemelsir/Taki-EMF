"""
desktop.py
==========
Taki as a program on one computer instead of a site in a browser.

    python run.py desktop           (or the Taki icon the desktop installer makes)

What is different from the web copy:

  * One person, no sign-in. The program signs its own window in, as the one
    account of that computer; there is no password to remember.
  * Everything is kept in a folder of that person, not next to the program:
        Windows   %LOCALAPPDATA%\\Taki
        macOS     ~/Library/Application Support/Taki
        Linux     ~/.local/share/taki        (or $XDG_DATA_HOME/taki)
    The .env file and DATABASE_URL are ignored: the desktop version never uses an
    online database. Projects move between copies of Taki as files.
  * It opens in a window of its own (Microsoft Edge or Chrome in "app" mode; every
    Windows computer has Edge), or failing that in a tab of the usual browser.
  * It listens on 127.0.0.1 only, so it is not reachable from other computers, and
    it stops by itself when its last window is closed.
  * Starting it again while it runs opens a second window on the same copy.

How it starts: the port is taken first and the window is opened at once, so
there is something to look at within a second. A small stand-in application
answers with a "starting" page while the real one (NumPy, the report libraries)
is loaded behind it, and then hands over.

Nothing here needs more than the standard library until the server is started,
and this module must not import the rest of Taki at the top: the settings in
config.py are read when that is first imported, after prepare_environment().
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any, Callable, List, Optional

APP_NAME = "Taki"
DEFAULT_PORT = 8254             # T-A-K-I on a telephone keypad; a fixed port keeps the browser's
#                                 saved choices (theme, AI key), which belong to host AND port
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")

# When to stop. All in seconds.
STARTUP_S = 90.0                # how long the first window may take to load the page
GRACE_S = 8.0                   # between the last window closing and the server stopping
ORPHAN_S = 600.0                # the same when the window was a tab of the usual browser, which may
#                                 put a hidden tab to sleep for a while and wake it again
ZOMBIE_S = 12 * 3600.0          # the browser is still running but has shown no page for this long
DUPLICATE_S = 8.0               # a second start this soon after the first is an impatient double-click


# ---------------------------------------------------------------------------
# What the running copy knows about its windows
# ---------------------------------------------------------------------------
class State:
    """Shared by the launcher (this module) and the desktop routes in main.py."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.key = ""                       # proves a request comes from this computer's launcher
        self.port = 0
        self.started = time.time()
        self.windows = 0                    # pages that are open right now
        self.ever = False                   # a page has been open at some time
        self.last_gone = 0.0                # when the last page closed
        self.owner: Optional[subprocess.Popen] = None   # the browser process of the app window
        self.owner_exit = 0.0               # when that process ended (0 = it has not)
        self.quit = False                   # asked to stop (by the installer or the uninstaller)
        self.requests = 0                   # pages and calls asked for so far (not the launcher's own questions)
        self.data_dir = ""
        self.log_path = ""

    def check_key(self, candidate: Optional[str]) -> bool:
        return bool(self.key) and hmac.compare_digest(str(candidate or ""), self.key)

    def window_opened(self) -> None:
        with self._lock:
            self.windows += 1
            self.ever = True

    def window_closed(self) -> None:
        with self._lock:
            self.windows = max(0, self.windows - 1)
            self.last_gone = time.time()

    def owner_alive(self) -> bool:
        proc = self.owner
        if proc is None or self.owner_exit:
            return False
        if proc.poll() is None:
            return True
        self.owner_exit = time.time()
        return False

    def snapshot(self) -> dict:
        alive = self.owner_alive()
        with self._lock:
            return {"started": self.started, "windows": self.windows, "ever": self.ever,
                    "last_gone": self.last_gone, "owner_alive": alive, "owner_exit": self.owner_exit,
                    "quit": self.quit, "requests": self.requests}


STATE = State()


def should_stop(now: float, s: dict) -> bool:
    """
    True when nobody is using this copy any more. `s` is State.snapshot().

    A page that is open keeps it running, always. So does the browser process of
    the app window while it lives, even with no page connected: a window that was
    minimised for hours may have had its page put to sleep, and must find the
    server still there when it wakes. Once that process has ended and no page is
    left, the server stops a few seconds later. A page that was opened as a tab of
    the usual browser has no process of its own to watch, so it gets a longer wait.
    """
    if s["quit"]:
        return True
    if s["windows"] > 0:
        return False
    if s["owner_alive"]:
        return now - max(s["started"], s["last_gone"]) > ZOMBIE_S
    if not s["ever"]:                               # nothing has loaded the page yet
        if s["owner_exit"]:                         # the window was closed before it finished loading
            return now - s["owner_exit"] > GRACE_S and now - s["started"] > 2 * GRACE_S
        return now - s["started"] > STARTUP_S
    # The app window's own process ended about when its page went: it was closed on purpose.
    closed_on_purpose = bool(s["owner_exit"]) and s["owner_exit"] >= s["last_gone"] - 5.0
    return now - s["last_gone"] > (GRACE_S if closed_on_purpose else ORPHAN_S)


def host_allowed(host_header: Optional[str]) -> bool:
    """
    The desktop version answers only when it is addressed as this computer. A web
    page elsewhere can point a name of its own at 127.0.0.1 ("DNS rebinding") to get
    its scripts past the browser's same-origin rule; the Host header then carries
    that name, and is refused here.
    """
    host = (host_header or "").strip().lower()
    if host.startswith("["):                        # [::1]:8254
        name = host.split("]", 1)[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if ":" in host else host
    return name in LOCAL_HOSTS


# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------
def default_data_dir() -> str:
    """The folder of the person at this computer where the desktop version keeps everything."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local"), APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"), APP_NAME.lower())


def prepare_environment(data_dir: Optional[str] = None) -> str:
    """
    Set what config.py reads, before it is imported: desktop behaviour, the data
    folder, and nothing from a .env file or an online database.
    """
    data = os.path.abspath(data_dir or os.environ.get("TAKI_DESKTOP_DATA_DIR") or default_data_dir())
    os.makedirs(data, exist_ok=True)
    os.environ["TAKI_DESKTOP"] = "1"
    os.environ["TAKI_IGNORE_ENV_FILE"] = "1"
    os.environ["TAKI_DATA_DIR"] = data
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("TAKI_DATABASE_URL", None)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(data, "cache", "matplotlib"))
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
    if "server.config" in sys.modules:              # already imported (the tests): switch it over
        cfg = sys.modules["server.config"]
        cfg.set_desktop(True)
        cfg.set_data_dir(data)
    STATE.data_dir = data
    return data


def default_user_name() -> str:
    """The name of the person signed in to this computer; it goes on reports as the author."""
    name = ""
    try:
        if sys.platform == "win32":
            import ctypes
            size = ctypes.c_ulong(256)
            buf = ctypes.create_unicode_buffer(size.value)
            if ctypes.windll.secur32.GetUserNameExW(3, buf, ctypes.byref(size)):      # 3 = display name
                name = buf.value
        else:
            import pwd
            name = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0]
    except Exception:
        name = ""
    if not name.strip():
        try:
            import getpass
            name = getpass.getuser()
        except Exception:
            name = ""
    name = name.strip()[:80]
    if name and name == name.lower():
        name = name[:1].upper() + name[1:]
    return name or "User"


def open_folder(path: str) -> None:
    """Show a folder in the file manager of this computer."""
    if sys.platform == "win32":
        os.startfile(path)                                              # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# One copy at a time
# ---------------------------------------------------------------------------
class InstanceLock:
    """Held by the running copy for as long as it lives; the system lets go of it if it dies."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        fh = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)        # type: ignore[attr-defined]
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)        # type: ignore[attr-defined]
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


def _info_path(data: str) -> str:
    return os.path.join(data, "desktop.json")


def read_info(data: str) -> Optional[dict]:
    """Where the running copy listens, as it wrote it down when it started."""
    try:
        with open(_info_path(data), encoding="utf-8") as fh:
            info = json.load(fh)
        return info if isinstance(info, dict) and info.get("port") and info.get("key") else None
    except (OSError, ValueError):
        return None


def write_info(data: str, info: dict) -> None:
    path, tmp = _info_path(data), _info_path(data) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    try:
        os.chmod(tmp, 0o600)                        # the key in it is for this person only
    except OSError:
        pass
    os.replace(tmp, path)


def remove_info(data: str) -> None:
    try:
        os.remove(_info_path(data))
    except OSError:
        pass


_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # never through a proxy


def probe(info: dict, timeout: float = 1.5) -> Optional[dict]:
    """Ask the copy described by `info` whether it is there. None when nothing answers as Taki."""
    url = "http://127.0.0.1:%d/api/desktop/alive?k=%s" % (int(info["port"]), urllib.parse.quote(str(info["key"])))
    try:
        with _direct.open(url, timeout=timeout) as res:
            body = json.loads(res.read().decode("utf-8"))
        return body if isinstance(body, dict) and body.get("ok") else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def ask_to_quit(info: dict, timeout: float = 3.0) -> bool:
    req = urllib.request.Request("http://127.0.0.1:%d/api/desktop/quit" % int(info["port"]), data=b"{}",
                                 method="POST", headers={"X-Taki-Key": str(info["key"]),
                                                         "X-Requested-With": "taki",
                                                         "Content-Type": "application/json"})
    try:
        with _direct.open(req, timeout=timeout) as res:
            return res.status == 200
    except (OSError, urllib.error.URLError):
        return False


def listen(preferred: int) -> socket.socket:
    """A listening socket on this computer only: the usual port, or a free one when that is taken."""
    last: Optional[OSError] = None
    for port in (preferred, preferred + 1, preferred + 2, 0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == "nt":                     # on Windows SO_REUSEADDR would let two programs share a port
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)    # type: ignore[attr-defined]
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(128)                        # from here on a browser can connect and wait
            return sock
        except OSError as exc:
            last = exc
            sock.close()
    raise OSError(f"No port could be opened on this computer ({last}).")


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
def _registry_app_path(exe: str) -> Optional[str]:
    try:
        import winreg                                                   # type: ignore[import-not-found]
    except ImportError:
        return None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + exe) as key:
                value, _ = winreg.QueryValueEx(key, None)
                if value and os.path.isfile(value):
                    return value
        except OSError:
            continue
    return None


def find_browser() -> Optional[str]:
    """A browser that can show a page in a window of its own (Edge, Chrome, Brave, Chromium)."""
    forced = os.environ.get("TAKI_BROWSER", "").strip()
    if forced:
        return forced if os.path.isfile(forced) else shutil.which(forced)
    found: List[str] = []
    if sys.platform == "win32":
        roots = [os.environ.get(v) for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        for sub, exe in ((r"Microsoft\Edge\Application", "msedge.exe"), (r"Google\Chrome\Application", "chrome.exe"),
                         (r"BraveSoftware\Brave-Browser\Application", "brave.exe"), (r"Chromium\Application", "chrome.exe")):
            found += [os.path.join(r, sub, exe) for r in roots if r]
            if exe != "chrome.exe" or "Google" in sub:
                reg = _registry_app_path(exe)
                if reg:
                    found.append(reg)
    elif sys.platform == "darwin":
        for app, exe in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge"),
                         ("Brave Browser", "Brave Browser"), ("Chromium", "Chromium")):
            for base in ("/Applications", os.path.expanduser("~/Applications")):
                found.append(f"{base}/{app}.app/Contents/MacOS/{exe}")
    else:
        for name in ("google-chrome", "google-chrome-stable", "microsoft-edge", "microsoft-edge-stable",
                     "chromium", "chromium-browser", "brave-browser"):
            path = shutil.which(name)
            if path:
                found.append(path)
    for path in found:
        if os.path.isfile(path):
            return path
    return None


def window_command(browser: str, url: str, profile: str) -> List[str]:
    """The command that shows `url` in an app window with a browser profile of its own."""
    cmd = [browser, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
           "--disable-background-mode", "--disable-sync", "--edge-skip-compat-layer-relaunch",
           "--window-size=1440,900"]
    return cmd + os.environ.get("TAKI_BROWSER_ARGS", "").split()


def open_window(url: str, data: str, how: str = "app") -> Optional[subprocess.Popen]:
    """
    Show Taki. Returns the browser process when the page got a window of its own,
    None when it went to a tab of the usual browser (or nowhere, how="none").
    """
    if how == "none":
        return None
    browser = find_browser() if how == "app" else None
    if browser:
        try:
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            return subprocess.Popen(window_command(browser, url, os.path.join(data, "window")),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=flags)
        except OSError:
            pass
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return None


def windowless() -> bool:
    """True when there is nobody to print to: started from its icon (pythonw), not from a terminal."""
    if sys.stdout is None or sys.stderr is None or STATE.log_path:
        return True
    return os.path.basename(sys.executable or "").lower().startswith("pythonw")


def alert(text: str, title: str = APP_NAME) -> None:
    """Tell the person something went wrong, also when there is no console to print to."""
    try:
        print(f"{title}: {text}", file=sys.stderr)
    except Exception:
        pass
    if sys.platform == "win32" and windowless():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 | 0x10000)     # error icon, in front
        except Exception:
            pass


# ---------------------------------------------------------------------------
# The stand-in application shown while the real one loads
# ---------------------------------------------------------------------------
_MARK = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' "
         "fill='%23004B87'/><path d='M18.5 4 8 18h6.5L12.5 28 24 13h-7z' fill='%23fff'/></svg>")

SPLASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Taki</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:image/svg+xml,__MARK__">
<style>
:root{--bg:#F7F9FA;--ink:#0F1B24;--muted:#5A6B7B}
:root[data-theme=dark]{--bg:#0B131D;--ink:#E6EDF4;--muted:#8FA1B3}
html,body{height:100%;margin:0}
body{display:grid;place-items:center;background:var(--bg);color:var(--ink);
  font:15px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,sans-serif}
main{text-align:center;padding:24px;max-width:560px}
.mark{width:72px;height:72px;margin:0 auto 20px;animation:breathe 1.8s ease-in-out infinite}
.mark.still{animation:none}
@keyframes breathe{50%{transform:scale(1.07)}}
h1{font-size:19px;font-weight:600;margin:0 0 4px}
p{margin:0;color:var(--muted);font-size:13.5px}
pre{white-space:pre-wrap;word-break:break-word;text-align:left;font-size:12px;margin:14px 0 0;
  padding:10px 12px;border:1px solid color-mix(in srgb,var(--muted) 40%,transparent);border-radius:8px}
@media (prefers-reduced-motion: reduce){.mark{animation:none}}
</style></head><body><main>
<div class="mark" id="mark"><img alt="" width="72" height="72" src="data:image/svg+xml,__MARK__"></div>
<h1 id="h">Starting Taki</h1><p id="p">Loading the calculation engine&hellip;</p><pre id="e" hidden></pre>
</main><script>
try{if(localStorage.getItem('taki.theme')==='dark')document.documentElement.dataset.theme='dark'}catch(e){}
var n=0;
function fail(text){document.getElementById('mark').className='mark still';
  document.getElementById('h').textContent='Taki could not start';
  document.getElementById('p').textContent='Close this window and try again. If it keeps happening, the details below say why.';
  var e=document.getElementById('e');e.hidden=false;e.textContent=text}
function again(){n++;if(n===24)document.getElementById('p').textContent='The first start after installing takes a little longer\\u2026';
  setTimeout(poll,n<8?150:300)}
function poll(){fetch('/api/health',{cache:'no-store'}).then(function(r){return r.json()}).then(function(j){
  if(j&&j.ok)location.replace(location.href);else if(j&&j.error)fail(j.error);else again()}).catch(again)}
poll();
</script></body></html>
""".replace("__MARK__", _MARK)


class Boot:
    """
    An ASGI application that answers from the first moment. Until the real
    application has been imported it shows the "starting" page (and tells API
    callers to wait); after that it passes everything through. Two small
    questions it always answers itself, so they work even if loading failed:
    is this copy alive, and please stop.
    """

    def __init__(self, load: Optional[Callable[[], Any]] = None) -> None:
        self.app: Any = None
        self.error: Optional[str] = None
        self._load = load or _load_application

    def start_loading(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, name="taki-load", daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        try:
            self.app = self._load()
        except BaseException as exc:                # also SystemExit from a half-installed package
            self.error = f"{type(exc).__name__}: {exc}"
            try:
                traceback.print_exc()
            except Exception:
                pass

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] == "lifespan":             # nothing to do: loading happens in a thread
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            if self.app is not None:
                await self.app(scope, receive, send)
            return
        path, method = scope.get("path", ""), scope.get("method", "GET")
        if path == "/api/desktop/alive":
            query = urllib.parse.parse_qs(scope.get("query_string", b"").decode("latin-1"))
            if not STATE.check_key((query.get("k") or [""])[0]):
                return await _reply(send, 403, {"detail": "Not for you."})
            snap = STATE.snapshot()
            return await _reply(send, 200, {"ok": True, "version": _version(), "pid": os.getpid(),
                                            "started": snap["started"], "windows": snap["windows"],
                                            "ready": self.app is not None, "error": self.error})
        if path == "/api/desktop/quit" and method == "POST":
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            if not STATE.check_key(headers.get("x-taki-key")):
                return await _reply(send, 403, {"detail": "Not for you."})
            STATE.quit = True
            return await _reply(send, 200, {"ok": True})
        STATE.requests += 1
        if self.app is not None:
            return await self.app(scope, receive, send)
        if path.startswith("/api/"):
            body = {"ok": False, "starting": self.error is None, "detail": "Taki is starting."}
            if self.error:
                body.update(error=f"{self.error}\n\nLog: {STATE.log_path or 'not kept'}", detail="Taki could not start.")
            return await _reply(send, 500 if self.error else 503, body)
        await _reply(send, 200, SPLASH.encode("utf-8"), b"text/html; charset=utf-8")


async def _reply(send: Callable, status: int, body: Any, ctype: bytes = b"application/json") -> None:
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", ctype), (b"content-length", str(len(data)).encode()),
                            (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]})
    await send({"type": "http.response.body", "body": data})


def _version() -> str:
    cfg = sys.modules.get("server.config")
    return getattr(cfg, "VERSION", "") if cfg else ""


def _load_application() -> Any:
    """Import the real application and do what its start-up would do under a normal server."""
    from . import auth, db, main
    db.conn()                                       # creates the database file and its tables
    try:
        auth.purge_expired()
    except Exception:
        pass
    return main.app


# ---------------------------------------------------------------------------
# Running it
# ---------------------------------------------------------------------------
def _start_url(port: int, key: str) -> str:
    return f"http://127.0.0.1:{port}/desktop/start?k={urllib.parse.quote(key)}"


def _keep_log(data: str) -> str:
    """Send prints and errors to a file when there is no console (the installed app has none)."""
    path = os.path.join(data, "taki.log")
    if not windowless() and not os.environ.get("TAKI_DESKTOP_LOG"):
        return ""
    try:
        if os.path.getsize(path) > 1_000_000:       # keep one older file, no more
            os.replace(path, path + ".1")
    except OSError:
        pass
    log = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = sys.stderr = log
    print(f"\n--- Taki desktop started {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    return path


def _second_start(data: str, how: str) -> int:
    """Another copy holds the lock: show its window instead of starting again."""
    deadline = time.time() + 45.0
    while time.time() < deadline:
        info = read_info(data)
        live = probe(info) if info else None
        if live:
            if time.time() - float(live.get("started") or 0) > DUPLICATE_S:
                open_window(_start_url(int(info["port"]), str(info["key"])), data, how)
            return 0
        time.sleep(0.3)
    alert("Taki is already starting on this computer but has not answered yet. Give it a moment and try again. "
          "If it keeps happening, restart the computer.")
    return 1


def _watch(server: Any, data: str, url: str, how: str) -> None:
    """Runs beside the server: stops it when its last window is gone."""
    retried = how != "app"
    while not server.should_exit:
        time.sleep(0.5)
        now, snap = time.time(), STATE.snapshot()
        # The app window never showed up: its browser has ended and nothing ever asked for a page.
        # (A window that was closed early did ask; a browser that passed the job on to one already
        # running had that one ask.) Open Taki as a tab of the usual browser instead.
        if (not retried and snap["requests"] == 0 and STATE.owner is not None and snap["owner_exit"]
                and now - snap["owner_exit"] > 5.0 and now - snap["started"] > 10.0):
            retried = True
            print("The app window did not open; opening Taki in the usual browser instead.")
            STATE.owner, STATE.owner_exit = None, 0.0
            STATE.started = now
            open_window(url, data, "tab")
            continue
        if should_stop(now, snap):
            server.should_exit = True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="taki desktop", description="Taki as a desktop program")
    parser.add_argument("--data-dir", help="keep the projects in this folder instead of the usual one")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TAKI_DESKTOP_PORT") or DEFAULT_PORT))
    parser.add_argument("--window", choices=("app", "tab", "none"), default=os.environ.get("TAKI_DESKTOP_WINDOW", "app"),
                        help="app: a window of its own (default); tab: the usual browser; none: only start it")
    parser.add_argument("--quit", action="store_true", help="ask the copy that is running to stop, and wait for it")
    parser.add_argument("--where", action="store_true", help="print the data folder and stop")
    args = parser.parse_args(argv)

    data = prepare_environment(args.data_dir)
    if args.where:
        print(data)
        return 0
    lock = InstanceLock(os.path.join(data, "desktop.lock"))

    if args.quit:
        if lock.acquire():                          # nothing is running
            lock.release()
            return 0
        info = read_info(data)
        if info:
            ask_to_quit(info)
        for _ in range(60):
            if lock.acquire():
                lock.release()
                return 0
            time.sleep(0.25)
        return 1

    STATE.log_path = _keep_log(data)
    if not lock.acquire():
        return _second_start(data, args.window)

    try:
        try:
            sock = listen(args.port)
        except OSError as exc:
            alert(str(exc))
            return 1
        port = sock.getsockname()[1]
        STATE.key, STATE.port, STATE.started = secrets.token_urlsafe(24), port, time.time()
        write_info(data, {"pid": os.getpid(), "port": port, "key": STATE.key, "started": STATE.started})
        url = _start_url(port, STATE.key)
        # The window first: the socket is already listening, so the page simply waits a moment.
        STATE.owner = open_window(url, data, args.window)

        try:
            import uvicorn
        except ImportError:
            alert("Taki is not completely installed (the package 'uvicorn' is missing). Run its installer again.")
            return 1
        boot = Boot()
        server = uvicorn.Server(uvicorn.Config(boot, lifespan="off", log_level="warning", access_log=False,
                                               timeout_graceful_shutdown=3, server_header=False))
        boot.start_loading()
        threading.Thread(target=_watch, args=(server, data, url, args.window), name="taki-watch", daemon=True).start()
        if not STATE.log_path:
            print(f"\n  Taki desktop is running on this computer only (port {port}).\n"
                  f"  Projects are kept in {data}\n"
                  + ("  Open it at: " + url + "\n" if args.window == "none" else "")
                  + "  Close its window to stop it, or press Ctrl+C here.\n", flush=True)
        server.run(sockets=[sock])
        return 0
    finally:
        remove_info(data)
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
