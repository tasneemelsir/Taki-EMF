#!/bin/sh
# Taki - start it:  sh start.sh
# The first run sets up its own Python environment in .venv (a few minutes);
# later runs start at once. Anything after the name is passed to run.py.
cd "$(dirname "$0")" || exit 1
PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10 or newer is needed: https://www.python.org/downloads/"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "  Setting Taki up for the first time. This takes a few minutes..."
  "$PY" -m venv .venv || exit 1
fi
if ! .venv/bin/python -c "import fastapi, uvicorn, numpy, matplotlib, reportlab, docx, psycopg" 2>/dev/null; then
  echo "  Installing what Taki needs..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt || { echo "  Installation failed."; exit 1; }
fi
exec .venv/bin/python run.py "$@"
