"""
desktop_setup.py - installs (or removes) the desktop version of Taki on Windows.

Nobody runs this by hand: "Install Taki.bat" fetches a Python of Taki's own and
then starts this file with it. From there on everything is done here, in Python:

    install     1. stop a copy of Taki that is running
                2. copy the program into   <dest>\\app
                3. make the private Python see it and its libraries
                4. install the libraries, at the exact versions in
                   requirements-desktop.lock, each checked against its hash
                5. check that Taki really starts with them
                6. make the shortcuts (desktop, Start menu) and the uninstaller
                7. start Taki

    uninstall   remove the shortcuts and the program; the projects only if asked

Where things go (nothing outside these two folders, no administrator rights):

    %LOCALAPPDATA%\\Programs\\Taki      the program: python\\, app\\, Uninstall Taki.bat
    %LOCALAPPDATA%\\Taki               the projects (made by Taki itself on first start)

Only the standard library is used: the Python this runs on has nothing else yet.
The Windows-only steps are kept in small functions of their own; the rest runs,
and is tested, on any system.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from typing import List, Optional, Tuple

APP = "Taki"
PIP_SHA256 = {                                   # the pip that comes with this file, by its hash
    "pip-26.2.1-py3-none-any.whl": "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e",
}
# What the running program needs, relative to the source folder. Keep in step with
# server/desktop_package.py (tests/test_desktop.py checks that the two agree).
TOP = ("run.py", "desktop.py", "requirements.txt", "requirements-desktop.txt", "requirements-desktop.lock",
       "tools/desktop_setup.py", "install-desktop.bat", "start-desktop.sh")
TREES = {"engine": (".py", ".json"), "server": (".py", ".json")}
STATIC = os.path.join("server", "static")
WHEELS = os.path.join("tools", "wheels")
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
MODULES = "numpy, fastapi, uvicorn, matplotlib, reportlab, docx"
WINDOWS = os.name == "nt"


class SetupError(Exception):
    """Something the person can act on; shown as it is, without a traceback."""


# ---------------------------------------------------------------------------
# Saying what happens
# ---------------------------------------------------------------------------
_log = None


def say(text: str = "") -> None:
    line = f"  {text}" if text else ""
    try:
        print(line, flush=True)
    except Exception:                            # a console that cannot show a character
        pass
    if _log is not None:
        try:
            _log.write(f"{time.strftime('%H:%M:%S')} {text}\n")
            _log.flush()
        except Exception:
            pass


def run(cmd: List[str], cwd: Optional[str] = None, env: Optional[dict] = None, timeout: Optional[float] = None,
        quiet: bool = False) -> int:
    """Run a command, showing what it prints unless `quiet`. Returns its exit code."""
    if _log is not None:
        _log.write(f"{time.strftime('%H:%M:%S')} > {' '.join(cmd)}\n")
        _log.flush()
    out = subprocess.DEVNULL if quiet else None
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, stdout=out, stderr=out).returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError as exc:
        say(f"Could not run {os.path.basename(cmd[0])}: {exc}")
        return 127


# ---------------------------------------------------------------------------
# The program files
# ---------------------------------------------------------------------------
def interface_assets(source: str) -> Optional[set]:
    """
    The names in server/static/assets that the interface really loads: what index.html names,
    and what those files name in turn. Files of an older build can lie beside them (the same
    rule, for the same reason, as server/desktop_package.py). None: it cannot be told, take all.
    """
    folder = os.path.join(source, STATIC, "assets")
    try:
        names = sorted(n for n in os.listdir(folder) if not n.startswith(".") and not n.endswith(".map"))
        with open(os.path.join(source, STATIC, "index.html"), "rb") as fh:
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


def program_files(source: str) -> List[Tuple[str, str]]:
    """(path in the source folder, path relative to the installed app folder) of every file to copy."""
    out: List[Tuple[str, str]] = []
    for name in TOP:
        path = os.path.join(source, *name.split("/"))
        if os.path.isfile(path):
            out.append((path, name))
    for tree, kinds in TREES.items():
        for folder, dirs, names in os.walk(os.path.join(source, tree)):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            rel = os.path.relpath(folder, source)
            if rel == STATIC or rel.startswith(STATIC + os.sep):
                continue
            out += [(os.path.join(folder, n), f"{rel}/{n}".replace(os.sep, "/")) for n in sorted(names)
                    if n.endswith(kinds) and not n.startswith(".")]
    loaded = interface_assets(source)
    for base, keep in ((STATIC, lambda n: not n.endswith(".map")), (WHEELS, lambda n: n.endswith(".whl"))):
        for folder, dirs, names in os.walk(os.path.join(source, base)):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            rel = os.path.relpath(folder, source)
            stale = loaded if rel == os.path.join(STATIC, "assets") else None     # only there do old builds linger
            out += [(os.path.join(folder, n), f"{rel}/{n}".replace(os.sep, "/")) for n in sorted(names)
                    if keep(n) and not n.startswith(".") and (stale is None or n in stale)]
    return out


def _remove_tree(path: str, tries: int = 6) -> None:
    """Delete a folder; Windows sometimes holds a file for a moment after its program has stopped."""
    for attempt in range(tries):
        if not os.path.lexists(path):
            return
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(0.5 + attempt * 0.5)


def copy_program(source: str, app: str) -> int:
    """Put a fresh copy of the program at `app`. The old one is replaced only once the new is complete."""
    files = program_files(source)
    if not any(rel == "desktop.py" for _, rel in files) or not any(rel == "server/main.py" for _, rel in files):
        raise SetupError("The Taki program files were not found next to the installer. "
                         "Take the whole folder out of the zip first (right-click the zip, Extract All).")
    if not any(rel == "server/static/index.html" for _, rel in files):
        raise SetupError("This copy of Taki has no built interface (server/static). "
                         "Build it first:  cd web && npm install && npm run build")
    if os.path.abspath(source) == os.path.abspath(app):
        return len(files)                        # repairing from the installed copy itself
    new, old = app + ".new", app + ".old"
    _remove_tree(new)
    for path, rel in files:
        target = os.path.join(new, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(path, target)
    _remove_tree(old)
    if os.path.lexists(app):
        try:
            os.replace(app, old)
        except OSError:
            raise SetupError("Taki's files are in use. Close Taki (and any window showing its folder) "
                             "and run the installer again.")
    os.replace(new, app)
    try:
        _remove_tree(old)
    except OSError:
        pass                                     # harmless leftovers; the next install clears them
    return len(files)


def app_version(app: str) -> str:
    try:
        with open(os.path.join(app, "server", "config.py"), encoding="utf-8") as fh:
            m = re.search(r'^VERSION\s*=\s*"([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# The Python that runs Taki
# ---------------------------------------------------------------------------
def patch_pth(python_dir: str) -> str:
    """
    The Python that python.org packs for use inside another program looks only at
    its own folder. Its python3xx._pth file lists where else to look: add the
    libraries (Lib\\site-packages), the program (..\\app), and switch `site` on so
    installed packages are set up the usual way.
    """
    found = sorted(glob.glob(os.path.join(python_dir, "python*._pth")))
    if not found:
        raise SetupError("This is not the Python that Taki fetches (no ._pth file). "
                         f"Delete the folder {python_dir} and run the installer again.")
    path = found[0]
    with open(path, encoding="utf-8") as fh:
        kept = [ln.strip() for ln in fh.read().splitlines()]
    kept = [ln for ln in kept if ln and not ln.startswith("#") and ln.lower() not in
            ("import site", "lib\\site-packages", "..\\app")]
    lines = kept + ["Lib\\site-packages", "..\\app", "import site"]
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.makedirs(os.path.join(python_dir, "Lib", "site-packages"), exist_ok=True)
    return path


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def find_pip_wheel(app: str, extra: List[str]) -> str:
    """The pip packed with Taki (checked against its hash), or one put in a `wheels` folder by hand."""
    for folder in [os.path.join(app, WHEELS)] + extra:
        for path in sorted(glob.glob(os.path.join(folder, "pip-*.whl")), reverse=True):
            want = PIP_SHA256.get(os.path.basename(path))
            if want and sha256(path) != want:
                raise SetupError(f"{os.path.basename(path)} is damaged. Download Taki again.")
            return path
    raise SetupError("The installer is incomplete (pip is missing from tools/wheels). Download Taki again.")


def offline_wheels(source: str) -> Optional[str]:
    """A folder named `wheels` beside the installer holds the packages for a computer without internet."""
    for folder in (os.path.join(os.path.dirname(os.path.abspath(source)), "wheels"), os.path.join(source, "wheels")):
        if glob.glob(os.path.join(folder, "numpy-*.whl")):
            return folder
    return None


def pip_install(pip: List[str], lock: str, wheels: Optional[str], cache: Optional[str] = None) -> None:
    """
    Install what the lock file lists. pip says a great deal; the screen gets one
    short line for each package and the log file gets everything. What pip downloads
    is kept in `cache` (inside the program folder, not pip's own place in the profile),
    so a second try after a broken connection does not fetch it again.
    """
    cmd = pip + ["install", "--disable-pip-version-check", "--no-warn-script-location", "--no-input",
                 "--progress-bar", "off", "--only-binary=:all:", "--require-hashes", "-r", os.path.basename(lock)]
    if wheels:
        cmd += ["--no-index", "--find-links", wheels]
    else:
        cmd += ["--retries", "4", "--timeout", "30"]
    if cache:
        cmd += ["--cache-dir", cache]
    if _log is not None:
        _log.write(f"{time.strftime('%H:%M:%S')} > {' '.join(cmd)}\n")
    tail: List[str] = []
    fetched = 0
    try:
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(lock), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SetupError(f"pip could not be started: {exc}")
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if _log is not None:
            _log.write(line + "\n")
        tail = (tail + [line])[-14:]
        m = re.match(r"Collecting ([A-Za-z0-9_.\-]+)==(\S+)", line)
        if m:
            fetched += 1
            say(f"        {m.group(1)} {m.group(2)}")
        elif line.startswith("Installing collected packages"):
            say("        unpacking them ...")
    if proc.wait() == 0 and not fetched:
        say("        all there already; nothing was fetched")
    if proc.returncode != 0:
        for line in tail:
            say("        | " + line[:200])
        raise SetupError(
            "The libraries could not be installed"
            + (" from the wheels folder (a package is missing from it, or is for another Python)." if wheels else
               ". This step needs the internet (pypi.org). Check the connection and run the installer again; "
               "what was already fetched is not fetched twice."))


# ---------------------------------------------------------------------------
# Windows: shortcuts, the list of installed apps, the uninstaller
# ---------------------------------------------------------------------------
CSIDL_PROGRAMS, CSIDL_DESKTOP = 0x0002, 0x0010
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + "\\" + APP
PS_SHORTCUT = ("$ErrorActionPreference='Stop';"
               "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TAKI_LNK);"
               "$s.TargetPath=$env:TAKI_LNK_TARGET;$s.Arguments=[string]$env:TAKI_LNK_ARGS;"
               "$s.WorkingDirectory=$env:TAKI_LNK_DIR;$s.IconLocation=$env:TAKI_LNK_ICON;"
               "$s.Description=$env:TAKI_LNK_NOTE;$s.Save()")


def shell_folder(csidl: int) -> str:
    """The person's Desktop or Start-menu folder, wherever Windows keeps it (OneDrive may have moved it)."""
    import ctypes
    buf = ctypes.create_unicode_buffer(520)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) != 0 or not buf.value:
        raise OSError("folder not found")
    return buf.value


def _powershell() -> str:
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0",
                        "powershell.exe")
    return path if os.path.isfile(path) else "powershell.exe"


def make_shortcut(link: str, target: str, args: str, workdir: str, icon: str, note: str) -> bool:
    env = dict(os.environ, TAKI_LNK=link, TAKI_LNK_TARGET=target, TAKI_LNK_ARGS=args, TAKI_LNK_DIR=workdir,
               TAKI_LNK_ICON=icon, TAKI_LNK_NOTE=note)
    code = run([_powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PS_SHORTCUT],
               env=env, timeout=90, quiet=True)
    return code == 0 and os.path.isfile(link)


def shortcut_places() -> List[Tuple[str, str]]:
    out = []
    for label, csidl in (("the desktop", CSIDL_DESKTOP), ("the Start menu", CSIDL_PROGRAMS)):
        try:
            out.append((label, shell_folder(csidl)))
        except Exception:
            pass
    return out


def make_shortcuts(dest: str, pythonw: str, app: str) -> List[str]:
    """Taki on the desktop and in the Start menu, and Uninstall Taki in the Start menu. Returns where."""
    icon = os.path.join(app, "server", "static", "icons", "taki.ico")
    script = os.path.join(app, "desktop.py")
    made: List[str] = []
    for label, folder in shortcut_places():
        link = os.path.join(folder, f"{APP}.lnk")
        if make_shortcut(link, pythonw, f'"{script}"', app, icon, "Taki - EMF simulation and shielding"):
            made.append(label)
        elif label == "the desktop":             # PowerShell is not allowed here: a plain launcher does the job
            with open(os.path.join(folder, f"{APP}.cmd"), "wb") as fh:
                fh.write(_batch_text(["@echo off", f'start "" "{pythonw}" "{script}"']))
            made.append("the desktop (as Taki.cmd)")
        if label == "the Start menu":
            make_shortcut(os.path.join(folder, f"Uninstall {APP}.lnk"), os.path.join(dest, f"Uninstall {APP}.bat"),
                          "", dest, icon, "Remove Taki from this computer")
    return made


def remove_shortcuts() -> None:
    for _, folder in shortcut_places():
        for name in (f"{APP}.lnk", f"{APP}.cmd", f"Uninstall {APP}.lnk"):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


def folder_size_kb(path: str) -> int:
    total = 0
    for folder, _, names in os.walk(path):
        for n in names:
            try:
                total += os.path.getsize(os.path.join(folder, n))
            except OSError:
                pass
    return total // 1024


def _batch_text(lines: List[str]) -> bytes:
    """
    A batch file as bytes. One that holds only plain letters is read the same everywhere;
    one that must name a folder with other letters in it (a person's name, say) is written
    as UTF-8 and tells Windows so in its first line.
    """
    text = "\r\n".join(lines) + "\r\n"
    try:
        return text.encode("ascii")
    except UnicodeEncodeError:
        return ("\r\n".join([lines[0], "chcp 65001 >nul"] + lines[1:]) + "\r\n").encode("utf-8")


def write_uninstaller(dest: str, python: str, app: str) -> str:
    """
    "Uninstall Taki.bat" in the program folder. It finds everything from where it lies
    (%~dp0), so no folder name is written into it and it works for any user name.
    """
    path = os.path.join(dest, f"Uninstall {APP}.bat")
    rel = os.path.relpath(python, dest).replace("/", "\\")
    with open(path, "wb") as fh:
        fh.write(_batch_text([
            "@echo off",
            "rem Removes Taki from this computer. Your projects are kept unless you say otherwise.",
            f"title Uninstall {APP}",
            f'"%~dp0{rel}" "%~dp0app\\tools\\desktop_setup.py" uninstall --dest "%~dp0."']))
    return path


def register_app(dest: str, app: str, uninstaller: str) -> None:
    """List Taki under Settings > Apps > Installed apps, for this person only."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        for name, value in (("DisplayName", APP), ("DisplayVersion", app_version(app)), ("Publisher", APP),
                            ("InstallLocation", dest), ("UninstallString", f'"{uninstaller}"'),
                            ("DisplayIcon", os.path.join(app, "server", "static", "icons", "taki.ico"))):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name, number in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", folder_size_kb(dest))):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(number))


def unregister_app() -> None:
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# The two jobs
# ---------------------------------------------------------------------------
def interpreters(dest: str) -> Tuple[str, str, str]:
    """(python, pythonw, kind) of the installation at `dest`; kind is "private", "venv" or ""."""
    exe, exew = ("python.exe", "pythonw.exe") if WINDOWS else ("python", "python")
    private = os.path.join(dest, "python")
    if os.path.isfile(os.path.join(private, exe)):
        return os.path.join(private, exe), os.path.join(private, exew), "private"
    scripts = os.path.join(dest, "venv", "Scripts" if WINDOWS else "bin")
    if os.path.isfile(os.path.join(scripts, exe)):
        return os.path.join(scripts, exe), os.path.join(scripts, exew), "venv"
    return "", "", ""


def stop_running(dest: str) -> None:
    """Ask a copy of Taki that is running from `dest` to stop, and wait until it has."""
    python, _, _ = interpreters(dest)
    script = os.path.join(dest, "app", "desktop.py")
    if not python or not os.path.isfile(script):
        return
    if run([python, script, "--quit"], cwd=os.path.dirname(script), timeout=40, quiet=True) != 0:
        raise SetupError("Taki is running and did not stop. Close its window and run this again.")


def install(source: str, dest: str, start: bool = True, shortcuts: bool = True) -> int:
    global _log
    source, dest = os.path.abspath(source), os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    _log = open(os.path.join(dest, "install.log"), "a", encoding="utf-8", errors="replace")
    _log.write(f"\n--- install {time.strftime('%Y-%m-%d %H:%M:%S')} from {source} with {sys.executable} ---\n")
    app = os.path.join(dest, "app")

    say("1 of 5  Copying Taki ...")
    stop_running(dest)
    count = copy_program(source, app)
    version = app_version(app)
    say(f"        {count} files, version {version or 'unknown'}")

    say("2 of 5  Preparing Python ...")
    python, pythonw, kind = interpreters(dest)
    wheels = offline_wheels(source)
    if kind == "private":
        patch_pth(os.path.dirname(python))
        pip = [python, find_pip_wheel(app, [wheels] if wheels else []) + "/pip"]
        shutil.rmtree(os.path.join(dest, "venv"), ignore_errors=True)     # left by an install without its own Python
    else:                                        # no private Python: an environment made by the one running this
        if kind != "venv":
            if run([sys.executable, "-m", "venv", os.path.join(dest, "venv")]) != 0:
                raise SetupError("A Python environment could not be made with the Python on this computer. "
                                 "Install Python 3.13 from python.org and run the installer again.")
            python, pythonw, kind = interpreters(dest)
        pip = [python, "-m", "pip"]
    say(f"        {'its own Python' if kind == 'private' else 'an environment of the Python on this computer'}"
        f"{', libraries from the wheels folder' if wheels else ''}")

    say("3 of 5  Installing the calculation libraries (about 45 MB the first time; a few minutes) ...")
    pip_cache = os.path.join(dest, "cache", "pip")
    pip_install(pip, os.path.join(app, "requirements-desktop.lock"), wheels, pip_cache)

    say("4 of 5  Checking that Taki starts ...")
    env = dict(os.environ, TAKI_DESKTOP="1", TAKI_IGNORE_ENV_FILE="1", MPLBACKEND="Agg",
               TAKI_DATA_DIR=os.path.join(dest, "cache", "check"), MPLCONFIGDIR=os.path.join(dest, "cache", "check"))
    os.makedirs(env["TAKI_DATA_DIR"], exist_ok=True)
    check = f"import sys; sys.path.insert(0, {app!r}); import {MODULES}; import server.main"
    if run([python, "-c", check], cwd=app, env=env, timeout=300) != 0:
        raise SetupError("Taki was copied, but it does not start with the libraries that were installed. "
                         f"The lines above say why; they are also in {os.path.join(dest, 'install.log')}.")
    run([python, "-m", "compileall", "-q", app], quiet=True, timeout=300)      # a quicker first start
    shutil.rmtree(os.path.join(dest, "cache"), ignore_errors=True)             # the downloads are installed now

    say("5 of 5  Making the shortcuts ...")
    if WINDOWS and shortcuts:
        uninstaller = write_uninstaller(dest, python, app)
        made = make_shortcuts(dest, pythonw, app)
        try:
            register_app(dest, app, uninstaller)
        except Exception as exc:
            say(f"        (not listed under installed apps: {exc})")
        say("        Taki is on " + " and ".join(made) if made else
            f"        No shortcut could be made. Start Taki with:  \"{pythonw}\" \"{os.path.join(app, 'desktop.py')}\"")
    else:
        say("        skipped")

    say()
    say(f"Taki {version} is installed in {dest}")
    if start:
        say("Starting Taki ...")
        flags = 0
        if WINDOWS:
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP    # type: ignore[attr-defined]
        subprocess.Popen([pythonw, os.path.join(app, "desktop.py")], cwd=app, creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def data_folder(dest: str) -> str:
    """Where the installed Taki keeps the projects (asked from the program itself when it is there)."""
    if os.environ.get("TAKI_DESKTOP_DATA_DIR"):
        return os.path.abspath(os.environ["TAKI_DESKTOP_DATA_DIR"])
    app = os.path.join(dest, "app")
    try:
        sys.path.insert(0, app)
        from server.desktop import default_data_dir         # type: ignore[import-not-found]
        return default_data_dir()
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, APP)
    finally:
        if app in sys.path:
            sys.path.remove(app)


def _yes(question: str, default: bool = False) -> bool:
    try:
        answer = input(f"  {question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return default if not answer else answer in ("y", "yes")


def uninstall(dest: str, yes: bool = False, delete_data: Optional[bool] = None) -> int:
    dest = os.path.abspath(dest)
    depth = len([part for part in os.path.normpath(dest).split(os.sep) if part])
    if (not os.path.isfile(os.path.join(dest, "app", "desktop.py")) or depth < 2          # never a whole drive,
            or os.path.normcase(dest) == os.path.normcase(os.path.expanduser("~"))):     # never a home folder
        raise SetupError(f"Taki is not installed in {dest}.")
    data = data_folder(dest)
    say(f"This removes Taki from {dest}")
    if not yes and not _yes("Remove Taki from this computer?"):
        say("Nothing was changed.")
        return 1
    if delete_data is None:
        has = os.path.isfile(os.path.join(data, "taki.db"))
        delete_data = has and not yes and _yes(f"Also delete your projects ({data})? They cannot be brought back.")
    stop_running(dest)
    if WINDOWS:
        remove_shortcuts()
        unregister_app()
    if delete_data:
        shutil.rmtree(data, ignore_errors=True)
        say("Your projects were deleted.")
    else:                                        # keep the projects; drop what only the program needed
        for name in ("window", "cache"):         # the window's browser profile, drawing caches
            shutil.rmtree(os.path.join(data, name), ignore_errors=True)
        for name in ("taki.log", "taki.log.1", "desktop.json", "desktop.lock"):
            try:
                os.remove(os.path.join(data, name))
            except OSError:
                pass
        if os.path.isdir(data):
            say(f"Your projects are kept in {data}")
    say("Taki has been removed.")
    if not WINDOWS:
        shutil.rmtree(dest, ignore_errors=True)
        return 0
    if not yes:
        try:
            input("  Press Enter to close this window. ")
        except (EOFError, KeyboardInterrupt):
            pass
    # This very Python lives in the folder to remove, so that last step is left to Windows,
    # two seconds after this program has ended. The command line is given as one string:
    # cmd.exe has quoting rules of its own, and this is the form it documents.
    subprocess.Popen(f'cmd.exe /d /c "ping -n 3 127.0.0.1 >nul & rmdir /s /q "{dest}""',
                     cwd=os.environ.get("TEMP") or os.path.dirname(dest), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,   # type: ignore[attr-defined]
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Install or remove the desktop version of Taki")
    sub = parser.add_subparsers(dest="job", required=True)
    p = sub.add_parser("install")
    p.add_argument("--source", required=True, help="the folder holding desktop.py, engine and server")
    p.add_argument("--dest", required=True, help="where to install, e.g. %%LOCALAPPDATA%%\\Programs\\Taki")
    p.add_argument("--no-start", action="store_true", help="do not start Taki afterwards")
    p.add_argument("--no-shortcuts", action="store_true", help="no shortcuts and no entry under installed apps")
    p = sub.add_parser("uninstall")
    p.add_argument("--dest", required=True)
    p.add_argument("--yes", action="store_true", help="do not ask; the projects are kept")
    p.add_argument("--delete-data", action="store_true", help="also delete the projects")
    args = parser.parse_args(argv)
    try:
        if args.job == "install":
            return install(args.source, args.dest, start=not args.no_start, shortcuts=not args.no_shortcuts)
        return uninstall(args.dest, yes=args.yes, delete_data=True if args.delete_data else None)
    except SetupError as exc:
        say()
        say(str(exc))
        return 2
    except KeyboardInterrupt:
        say("Stopped.")
        return 130
    finally:
        if _log is not None:
            _log.close()


if __name__ == "__main__":
    sys.exit(main())
