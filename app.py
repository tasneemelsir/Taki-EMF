"""
app.py - the entrance Vercel uses.

Vercel runs a FastAPI project by loading an application called "app" from a file of
this name beside requirements.txt. Only Vercel reads this file: on a computer and in
the Docker image Taki starts with run.py.

README, "Publishing on Vercel"; what changes there is in server/vercel.py.
"""

from server import vercel

vercel.prepare()                       # before the application reads its settings
from server.main import app            # noqa: E402

vercel.adapt(app)
