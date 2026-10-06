"""
desktop_package.py
==================
The download of the desktop version: a zip made from the very files this copy
runs on, so what people install is the version they have been using in the
browser.

    Taki-Desktop-<version>/
        Install Taki.bat        Windows: double-click
        start-desktop.sh        macOS and Linux
        READ ME.txt
        app/                    the program (engine, server, built interface, installer script)

Only files named here go in: the program and nothing else. The .env file, the
data folder and anything else beside the program can never end up in it.
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import Dict, List, Optional, Tuple

from . import config

# Files beside run.py that the desktop version needs.
TOP = ("run.py", "desktop.py", "requirements.txt", "requirements-desktop.txt", "requirements-desktop.lock",
       "tools/desktop_setup.py", "install-desktop.bat", "start-desktop.sh")
# Whole folders, and which kinds of file are taken from them.
TREES = {"engine": (".py", ".json"), "server": (".py", ".json")}
STATIC = "server/static"                # the built interface, taken whole
WHEELS = "tools/wheels"                 # pip itself, so the installer has one fewer thing to fetch
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
# What must be there for a download to be offered at all.
REQUIRED = ("desktop.py", "requirements-desktop.lock", "tools/desktop_setup.py", "install-desktop.bat",
            "server/static/index.html")
# These also sit at the top of the zip, where they are found; "app/" holds the whole program.
AT_TOP = {"install-desktop.bat": "Install Taki.bat", "start-desktop.sh": "start-desktop.sh"}
CRLF = (".bat", ".cmd", "read me.txt")  # Windows scripts fail in odd ways with Unix line ends

READ_ME = """{title}
{rule}

Taki on your own computer: a window of its own, no sign-in, and no internet
needed once it is installed. Your projects stay on the computer.


WINDOWS
-------
1. Take this folder out of the zip first: right-click the zip, Extract All.
   Installing from inside the zip does not work.
2. Double-click "Install Taki".
   Windows may ask whether to run it, because it came from the internet:
   choose Run (or "More info", then "Run anyway").
3. Wait a few minutes. It fetches Python from python.org and the calculation
   libraries from pypi.org, about 55 MB, into a folder of its own. It asks for
   no administrator password and installs nothing system-wide.

Taki then opens. From now on start it with the Taki icon on the desktop or in
the Start menu. This folder can be deleted afterwards.

  The program       %LOCALAPPDATA%\\Programs\\Taki      (about 200 MB)
  Your projects     %LOCALAPPDATA%\\Taki
  To update         run "Install Taki" from a newer download; projects are kept
  To remove         Start menu, "Uninstall Taki"
  On the taskbar    pin the Taki icon from the desktop, not the open window

No internet on that computer? Install Taki on one that has it, copy the folder
%LOCALAPPDATA%\\Programs\\Taki from there to the same place on the other
computer, open its "app" folder and double-click "install-desktop". That makes
the shortcuts; nothing is fetched.


MACOS AND LINUX
---------------
In a terminal, in this folder:

    sh start-desktop.sh

It needs Python 3.10 or newer, and Chrome, Edge or Chromium for the window
(without one of them Taki opens as a tab of your usual browser). The first run
sets up its own Python environment in app/.venv; later runs start at once.
Projects are kept in ~/Library/Application Support/Taki (macOS) or
~/.local/share/taki (Linux).


MOVING PROJECTS
---------------
Projects travel between the web version and the desktop version as one file:
on the projects page choose "Export all", and "Import" on the other side.


The desktop version keeps everything on this computer and contacts no server.
The one exception is the optional AI narrative in reports: when you ask for it,
the results of that project go to the AI service you chose, with your own key.
"""


def _root(*parts: str) -> str:
    return os.path.join(config.ROOT, *parts)


def available() -> bool:
    """Whether this copy has everything a download needs (a trimmed deployment may not)."""
    if not all(os.path.isfile(_root(*name.split("/"))) for name in REQUIRED):
        return False
    try:
        return any(n.startswith("pip-") and n.endswith(".whl") for n in os.listdir(_root(*WHEELS.split("/"))))
    except OSError:
        return False


def interface_assets() -> Optional[set]:
    """
    The names in server/static/assets that the built interface really loads: what index.html
    names, and what those files name in turn. A folder copied over an older one keeps the
    older build's files beside the new ones (every name carries a hash of its contents, so
    nothing overwrites them). They are never loaded, and they do not belong in the download.
    None when that cannot be worked out; then every file is taken.
    """
    folder = _root(*STATIC.split("/"), "assets")
    try:
        names = sorted(n for n in os.listdir(folder) if not n.startswith(".") and not n.endswith(".map"))
        with open(_root(*STATIC.split("/"), "index.html"), "rb") as fh:
            page = fh.read()
    except OSError:
        return None
    used = {n for n in names if n.encode("utf-8") in page}
    if not used:
        return None
    todo = list(used)
    while todo:
        name = todo.pop()
        if not name.endswith((".js", ".css")):
            continue
        try:
            with open(os.path.join(folder, name), "rb") as fh:
                text = fh.read()
        except OSError:
            return None
        for other in names:
            if other not in used and other.encode("utf-8") in text:
                used.add(other)
                todo.append(other)
    return used


def files() -> List[Tuple[str, str]]:
    """(path on disk, name inside the zip) for everything that goes in, in a fixed order."""
    out: List[Tuple[str, str]] = []
    for name in TOP:
        path = _root(*name.split("/"))
        if os.path.isfile(path):
            if name in AT_TOP:                       # where it is found and double-clicked ...
                out.append((path, AT_TOP[name]))
            out.append((path, "app/" + name))        # ... and with the program, which can then hand itself on
    for tree, kinds in TREES.items():
        for folder, dirs, names in os.walk(_root(tree)):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            rel = os.path.relpath(folder, config.ROOT).replace(os.sep, "/")
            if rel == STATIC or rel.startswith(STATIC + "/"):
                continue
            for n in sorted(names):
                if n.endswith(kinds) and not n.startswith("."):
                    out.append((os.path.join(folder, n), f"app/{rel}/{n}"))
    loaded = interface_assets()
    for base, keep in ((STATIC, lambda n: not n.endswith(".map")), (WHEELS, lambda n: n.endswith(".whl"))):
        for folder, dirs, names in os.walk(_root(*base.split("/"))):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            rel = os.path.relpath(folder, config.ROOT).replace(os.sep, "/")
            for n in sorted(names):
                if rel == STATIC + "/assets" and loaded is not None and n not in loaded:
                    continue                                 # left over from an older build
                if keep(n) and not n.startswith("."):
                    out.append((os.path.join(folder, n), f"app/{rel}/{n}"))
    return out


_cache: Dict[str, object] = {"stamp": None, "data": b""}


def _stamp(items: List[Tuple[str, str]]) -> Tuple:
    newest = 0.0
    for path, _ in items:
        try:
            newest = max(newest, os.path.getmtime(path))
        except OSError:
            pass
    return (config.VERSION, len(items), newest)


def build(folder: Optional[str] = None) -> Tuple[bytes, str]:
    """(the zip, its file name). Built once and kept until a file in it changes."""
    top = folder or f"Taki-Desktop-{config.VERSION}"
    items = files()
    stamp = (top,) + _stamp(items)
    if _cache["stamp"] != stamp:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            def add(name: str, data: bytes, mode: int = 0o644) -> None:
                if name.lower().endswith(CRLF):
                    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                info = zipfile.ZipInfo(f"{top}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (mode & 0xFFFF) << 16
                z.writestr(info, data)

            title = f"Taki {config.VERSION} - desktop version"
            add("READ ME.txt", READ_ME.format(title=title, rule="=" * len(title)).encode("utf-8"))
            for path, name in items:
                with open(path, "rb") as fh:
                    add(name, fh.read(), 0o755 if name.endswith(".sh") else 0o644)
        _cache["stamp"], _cache["data"] = stamp, buf.getvalue()
    return _cache["data"], f"{top}.zip"            # type: ignore[return-value]
