"""
make_lock.py - write requirements-desktop.lock from requirements-desktop.txt.

    pip install uv
    python tools/make_lock.py

The lock file names one exact version of every package the desktop version needs,
for every system and every Python from 3.10 on, and the SHA-256 of each file. The
desktop installer hands it to pip, which then installs exactly what Taki was
tested with and refuses a download that does not match.

Run this after changing requirements-desktop.txt, or to move to newer versions of
the libraries; then run the tests on the result (pip install -r the lock file
into a fresh environment) before giving it to anyone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = """\
# Taki - the exact versions the desktop version installs, for every system and every
# Python from 3.10 on. Each file is listed with its SHA-256, which pip checks before
# it installs anything. Made from requirements-desktop.txt by:  python tools/make_lock.py
# Do not edit by hand.
"""


def main() -> int:
    uv = shutil.which("uv")
    cmd = [uv] if uv else [sys.executable, "-m", "uv"]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "lock.txt")
        code = subprocess.run(cmd + ["pip", "compile", os.path.join(ROOT, "requirements-desktop.txt"),
                                     "--universal", "--python-version", "3.10", "--generate-hashes",
                                     "--no-build", "--no-header", "--no-annotate", "--quiet", "-o", out]).returncode
        if code != 0:
            print("uv could not work the versions out (is it installed?  pip install uv)")
            return code
        with open(out, encoding="utf-8") as fh:
            body = fh.read()
    with open(os.path.join(ROOT, "requirements-desktop.lock"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER + body)
    names = [ln.split("==")[0] for ln in body.splitlines() if "==" in ln and not ln.startswith(" ")]
    print(f"requirements-desktop.lock: {len(set(names))} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
