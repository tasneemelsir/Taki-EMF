#!/bin/sh
# Taki - the desktop version on macOS and Linux:  sh start-desktop.sh
# Its own window, no sign-in, projects kept in your own folder (not here).
# The first run sets up a Python environment in .venv (a few minutes);
# later runs start at once. Anything after the name is passed to desktop.py.
cd "$(dirname "$0")" || exit 1
[ -f app/desktop.py ] && cd app        # in the desktop download the program is one folder down
PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10 or newer is needed: https://www.python.org/downloads/"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "  Setting Taki up for the first time. This takes a few minutes..."
  "$PY" -m venv .venv || exit 1
fi
if ! .venv/bin/python -c "import fastapi, uvicorn, numpy, matplotlib, reportlab, docx" 2>/dev/null; then
  echo "  Installing what Taki needs..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  # the exact versions Taki was tested with; the open list only where those have no ready-made build
  .venv/bin/python -m pip install --quiet --only-binary=:all: -r requirements-desktop.lock \
    || .venv/bin/python -m pip install --quiet -r requirements-desktop.txt \
    || { echo "  Installation failed. Check the internet connection and run this again."; exit 1; }
fi
exec .venv/bin/python desktop.py "$@"
