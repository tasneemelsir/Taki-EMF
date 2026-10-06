"""
make_examples.py - work out the numbers shown on the example cards and keep them.

    python tools/make_examples.py

The projects page shows a few numbers on each example (peak fields, compliance).
Solving all eight examples takes a second on a PC but many seconds on a small
server, each time it wakes. This writes the numbers into server/templates_cache.json
so they are simply read. They are used only when they belong to exactly these
examples in exactly this version; after any change to the examples, the engine or
the version number, run this again (a test fails until you do).
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("TAKI_IGNORE_ENV_FILE", "1")


def main() -> int:
    from server import service
    path = service.write_templates_file()
    print(f"{os.path.relpath(path, ROOT)}: {len(service.templates())} examples")
    return 0


if __name__ == "__main__":
    sys.exit(main())
