"""
desktop.py - Taki as a desktop program.

    python desktop.py        the same as:  python run.py desktop

The Taki icon made by the desktop installer runs this file with pythonw, which
has no console: anything that goes wrong is shown in a message box and written
to taki.log in the data folder. What the desktop version is and how it behaves
is described in server/desktop.py.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:                 # the private Python of the installed app does not add it itself
    sys.path.insert(0, HERE)


def _fail(text: str) -> None:
    try:
        from server import desktop
        desktop.alert(text)
    except Exception:
        if sys.stderr is not None:
            print(text, file=sys.stderr)


def main() -> int:
    try:
        from server import desktop
    except Exception as exc:
        _fail(f"Taki is not completely installed ({type(exc).__name__}: {exc}). Run its installer again.")
        return 1
    try:
        return desktop.main()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        _fail(f"Taki stopped because of a problem: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
