"""
main.py
=======
The Taki web server: a JSON API over the physics engine, accounts and saved
projects, and the built front end served as static files.

Run with:  python run.py        (or: uvicorn server.main:app)
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles

from engine import ai_report, lines as lines_mod

from . import (auth, config, db, desktop, desktop_package, mailer, report_service, service, twin_service,
               validation_service)

HOUSEKEEPING_S = 6 * 3600


def _housekeeping(stop: threading.Event) -> None:
    """Every few hours: drop expired sign-ins and reset links, and long-idle guests."""
    while True:
        try:
            auth.purge_expired()
        except Exception:
            pass
        if stop.wait(HOUSEKEEPING_S):
            return


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.conn()
    stop = threading.Event()
    threading.Thread(target=_housekeeping, args=(stop,), daemon=True, name="taki-housekeeping").start()
    yield
    stop.set()


app = FastAPI(title="Taki", version=config.VERSION, docs_url="/api/docs", redoc_url=None,
              openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1200)

MAX_BODY = 2_000_000
MAX_BODY_REPORT = 20_000_000
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    if config.DESKTOP and not desktop.host_allowed(request.headers.get("host")):
        return PlainTextResponse("Not found.", status_code=404)      # see desktop.host_allowed
    if path.startswith("/api/"):
        if request.method in MUTATING:
            # Browsers cannot send a custom header cross-site without a CORS preflight, which
            # this server never approves - a simple, robust CSRF defence for a cookie session.
            if request.headers.get("x-requested-with") != "taki":
                return JSONResponse({"detail": "Missing request header."}, status_code=400)
            limit = MAX_BODY_REPORT if path.startswith("/api/report") else MAX_BODY
            try:
                if int(request.headers.get("content-length", "0")) > limit:
                    return JSONResponse({"detail": "Request too large."}, status_code=413)
            except ValueError:
                pass
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/assets/") and response.status_code == 200:
        # Built files carry a hash of their content in their name: a changed file is a new name.
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response


@app.exception_handler(auth.AuthError)
async def _auth_error(_request: Request, exc: auth.AuthError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.exception_handler(lines_mod.LineError)
async def _line_error(_request: Request, exc: lines_mod.LineError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(ValueError)
async def _value_error(_request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def _client(request: Request) -> str:
    # Behind a trusted proxy uvicorn has already replaced this with the forwarded address
    # (TAKI_TRUSTED_PROXIES). The raw X-Forwarded-For header is not read here: anyone can send it.
    return (request.client.host if request.client else "") or "?"


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(config.COOKIE_NAME, token, max_age=config.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=config.SECURE_COOKIES, path="/")


def optional_user(request: Request) -> Optional[dict]:
    return auth.user_for_token(request.cookies.get(config.COOKIE_NAME))


def current_user(request: Request) -> dict:
    user = optional_user(request)
    if user is None:
        raise HTTPException(401, "Sign in to continue.")
    return user


def _cfg(body: Dict[str, Any]) -> dict:
    return service.normalise_config(body.get("config"))


def _meta() -> dict:
    return {"version": config.VERSION, "allow_signup": config.ALLOW_SIGNUP,
            "allow_guests": config.ALLOW_GUESTS,
            # AI services for which this copy shares a key of its own (normally none)
            "operator_ai": [p for p, k in config.OPERATOR_AI_KEYS.items() if k],
            "database": db.backend_name(), "database_host": db.provider(),
            "email": mailer.configured(), "min_password": auth.MIN_PASSWORD,
            # True in the desktop version: one person on this computer, no sign-in
            "desktop": config.DESKTOP,
            # whether this copy hands out the desktop version as a download
            "desktop_download": config.ALLOW_DESKTOP_DOWNLOAD and desktop_package.available()}


def _public_url(request: Request) -> str:
    return config.PUBLIC_URL or str(request.base_url).rstrip("/")


# ---------------------------------------------------------------------------
# Meta and accounts
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "version": config.VERSION, "time": time.time(), "database": db.backend_name()}


@app.get("/api/meta")
def meta(request: Request):
    user = optional_user(request)
    out = {**_meta(), "user": user}
    if config.DESKTOP and user:
        out["data_dir"] = config.DATA_DIR            # shown under Account, so the folder can be backed up
    return out


@app.post("/api/auth/register")
def register(request: Request, response: Response, body: Dict[str, Any] = Body(...)):
    existing = optional_user(request)
    user = auth.register(body.get("email", ""), body.get("password", ""), body.get("name", ""),
                         body.get("organisation", ""),
                         upgrade_user_id=existing["id"] if existing and existing["is_guest"] else None,
                         client=_client(request))
    if not (existing and existing["id"] == user["id"]):
        token, _ = auth.create_session(user["id"], request.headers.get("user-agent", ""))
        _set_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/login")
def login(request: Request, response: Response, body: Dict[str, Any] = Body(...)):
    user = auth.login(body.get("email", ""), body.get("password", ""), client=_client(request))
    auth.end_session(request.cookies.get(config.COOKIE_NAME))
    token, _ = auth.create_session(user["id"], request.headers.get("user-agent", ""))
    _set_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/guest")
def guest(request: Request, response: Response):
    existing = optional_user(request)
    if existing:
        return {"user": existing}
    user = auth.create_guest()
    token, _ = auth.create_session(user["id"], request.headers.get("user-agent", ""))
    _set_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.end_session(request.cookies.get(config.COOKIE_NAME))
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": user}


@app.patch("/api/auth/me")
def update_me(body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    prefs = body.get("prefs") if isinstance(body.get("prefs"), dict) else None
    return {"user": auth.update_profile(user["id"], body.get("name"), body.get("organisation"), prefs)}


@app.post("/api/auth/password")
def change_password(request: Request, body: Dict[str, Any] = Body(...),
                    user: dict = Depends(current_user)):
    if user["is_guest"]:
        raise HTTPException(400, "Guest sessions have no password. Create an account first.")
    auth.change_password(user["id"], body.get("current", ""), body.get("new", ""))
    auth.end_other_sessions(user["id"], request.cookies.get(config.COOKIE_NAME))
    return {"ok": True}


@app.post("/api/auth/forgot")
def forgot_password(request: Request, body: Dict[str, Any] = Body(...)):
    """Always answers the same way, whether or not the email belongs to an account."""
    found = auth.start_password_reset(str(body.get("email", "")), client=_client(request))
    if found:
        user, token = found
        link = f"{_public_url(request)}/reset?token={token}"
        if mailer.configured():
            mailer.send_async(user["email"], "Reset your Taki password", (
                f"Hello {user['name']},\n\nSomeone asked to reset the password of your Taki account. "
                f"Open this link within {auth.RESET_MINUTES} minutes to choose a new one:\n\n{link}\n\n"
                "If that was not you, ignore this message: your password has not changed.\n"))
        else:
            print(f"\n  Password reset requested for {user['email']}.\n"
                  f"  Link (valid {auth.RESET_MINUTES} minutes, single use):\n  {link}\n", flush=True)
    return {"ok": True, "email": mailer.configured()}


@app.post("/api/auth/reset")
def reset_password(request: Request, response: Response, body: Dict[str, Any] = Body(...)):
    user = auth.finish_password_reset(str(body.get("token", "")), str(body.get("password", "")),
                                      client=_client(request))
    token, _ = auth.create_session(user["id"], request.headers.get("user-agent", ""))
    _set_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/delete")
def delete_account(response: Response, body: Dict[str, Any] = Body(...),
                   user: dict = Depends(current_user)):
    auth.delete_account(user["id"], body.get("password"))
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


# ---------------------------------------------------------------------------
# The desktop version (server/desktop.py): no sign-in, and it stops with its window
# ---------------------------------------------------------------------------
def _desktop_only() -> None:
    if not config.DESKTOP:
        raise HTTPException(404, "Not found.")


_EXPIRED = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Taki</title>
<body style="font:15px/1.5 'Segoe UI',system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center;max-width:420px;padding:24px"><h1 style="font-size:19px">This window is out of date</h1>
<p>Close it and start Taki again from its icon.</p></div></body></html>"""


@app.get("/desktop/start", include_in_schema=False)
def desktop_start(request: Request, k: str = ""):
    """
    Where the launcher points the window. The key in the address proves the request
    comes from the launcher on this computer; it is traded for a session cookie and
    the browser is sent on to the application, so the key never stays in view.
    """
    _desktop_only()
    token = request.cookies.get(config.COOKIE_NAME)
    user = auth.user_for_token(token)
    mine = bool(user and user["id"] == auth.DESKTOP_USER_ID)
    if not desktop.STATE.check_key(k) and not mine:
        return HTMLResponse(_EXPIRED, status_code=403)
    response = RedirectResponse("/", status_code=303)
    if not mine:
        auth.desktop_user(desktop.default_user_name())
        token, _ = auth.create_session(auth.DESKTOP_USER_ID, request.headers.get("user-agent", ""))
    _set_cookie(response, token)                     # also when it was there: its lifetime starts again
    return response


@app.get("/api/desktop/presence")
async def desktop_presence(request: Request):
    """
    A stream each open page holds for as long as it is open. Nothing of interest is
    sent on it: the server counts these to know when its last window has closed.
    """
    _desktop_only()
    if auth.user_for_token(request.cookies.get(config.COOKIE_NAME)) is None:
        raise HTTPException(401, "Sign in to continue.")

    async def stream():
        desktop.STATE.window_opened()
        try:
            yield b"retry: 1000\n\n"                # a page that lost the stream asks again after 1 s
            while True:
                await asyncio.sleep(2.0)
                yield b": here\n\n"                 # a comment; writing it is how a closed page is noticed
        finally:
            desktop.STATE.window_closed()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/desktop/open-data-folder")
def desktop_open_data_folder(_user: dict = Depends(current_user)):
    """Show the folder that holds the projects, so it can be backed up or moved."""
    _desktop_only()
    try:
        desktop.open_folder(config.DATA_DIR)
    except Exception as exc:
        raise HTTPException(500, f"Could not open the folder: {exc}")
    return {"ok": True, "path": config.DATA_DIR}


@app.get("/api/desktop/package")
def desktop_download():
    """The desktop version as a zip, built from the files this copy runs on."""
    if not (config.ALLOW_DESKTOP_DOWNLOAD and desktop_package.available()):
        raise HTTPException(404, "The desktop version cannot be downloaded from this copy of Taki.")
    data, name = desktop_package.build()
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Content-Length": str(len(data)), "Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
_library_cache: Optional[dict] = None


@app.get("/api/library")
def library(_user: dict = Depends(current_user)):
    global _library_cache
    if _library_cache is None:
        _library_cache = {**service.library(), "report": report_service.options_catalogue()}
    return _library_cache


_templates_cache: Optional[list] = None


@app.get("/api/templates")
def templates(_user: dict = Depends(current_user)):
    global _templates_cache
    if _templates_cache is None:
        _templates_cache = service.templates()
    return {"templates": _templates_cache}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
@app.post("/api/changes")
def changes(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.what_changed(_cfg(body))


@app.post("/api/solve")
def solve(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.solve(_cfg(body))


@app.post("/api/normalise")
def normalise(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    """Clean an imported configuration (also converts scenario files from older Taki versions)."""
    raw = body.get("config")
    migrated = isinstance(raw, dict) and "corridor" not in raw and "lines" in raw
    cfg = _cfg(body)
    notes = []
    if migrated and any(abs(float(ln.get("load_pct", 100)) - 100.0) > 1e-9 for ln in cfg["lines"]):
        notes.append("This file has lines below 100 % loading. Earlier versions of Taki ignored loading "
                     "when setting the current, so the magnetic field will now be lower than it "
                     "showed before. Settings > What changed gives both numbers.")
    return {"config": cfg, "migrated": bool(migrated), "notes": notes}


@app.post("/api/grid")
def grid(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.grid(_cfg(body), float(body.get("z", 0.0) or 0.0))


@app.post("/api/points")
def points(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    pts = body.get("points")
    return service.points(_cfg(body), pts if isinstance(pts, list) else None)


@app.post("/api/earth")
def earth_envelope(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.earth_envelope(_cfg(body))


@app.post("/api/fieldlines")
def fieldlines(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.fieldlines(_cfg(body))


@app.post("/api/efieldlines")
def efieldlines(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.efieldlines(_cfg(body))


@app.post("/api/shield/models")
def shield_models(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.shield_models(_cfg(body), body.get("receptor"))


@app.post("/api/shield/sweep")
def shield_sweep(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.shield_sweep(_cfg(body), str(body.get("kind", "material")), body.get("receptor"))


@app.post("/api/shield/suggest")
def shield_suggest(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    """Suggested placement for the conductor-based measures (passive loop, screening wires)."""
    site = service.site_for(_cfg(body))
    with site.lock:
        return service.suggestion(site, str(body.get("preset", "")))


@app.post("/api/shield/assistant")
def shield_assistant(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return service.shield_assistant(_cfg(body), body.get("target_b"), body.get("receptor"))


@app.post("/api/twin")
def twin(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return twin_service.scene(_cfg(body))


@app.post("/api/twin/section")
def twin_section(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return twin_service.section(_cfg(body), float(body.get("z", 0.0) or 0.0))


@app.post("/api/twin/volume")
def twin_volume(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    return twin_service.volume(_cfg(body))


@app.post("/api/scenarios/compare")
def scenarios_compare(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    items = body.get("items")
    if not isinstance(items, list):
        raise HTTPException(422, "Expected a list of scenarios.")
    return service.compare_scenarios(items)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@app.get("/api/validation/catalogue")
def validation_catalogue(_user: dict = Depends(current_user)):
    return validation_service.catalogue()


@app.get("/api/validation/checks")
def validation_checks(_user: dict = Depends(current_user)):
    return {"checks": validation_service.checks()}


@app.get("/api/validation/template.csv")
def validation_template(_user: dict = Depends(current_user)):
    return Response(validation_service.template_csv(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="taki_reference_template.csv"'})


@app.post("/api/validation/compare")
def validation_compare(body: Dict[str, Any] = Body(...), _user: dict = Depends(current_user)):
    csv_text = body.get("csv_text")
    if csv_text is not None and len(str(csv_text)) > 400_000:
        raise HTTPException(413, "That file is too large.")
    return validation_service.compare(
        _cfg(body), dataset_id=body.get("dataset_id"), csv_text=csv_text,
        use_published_geometry=bool(body.get("use_published_geometry", False)),
        match_ground=bool(body.get("match_ground", True)),
        with_shield=bool(body.get("with_shield", False)))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@app.post("/api/report/preview")
def report_preview(body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    return report_service.preview(_cfg(body), body.get("options") or {}, user)


@app.post("/api/report/{fmt}")
def report_file(fmt: str, body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    if fmt not in ("txt", "pdf", "docx"):
        raise HTTPException(404, "Unknown report format.")
    data, media, name = report_service.render(_cfg(body), fmt, body.get("options") or {}, user)
    return Response(data, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


_ai_uses: Dict[str, list] = {}


def _ai_key(body: Dict[str, Any], user: dict, count: bool):
    """
    (provider, key) for an AI request. The person's own key, sent with this
    request and never kept, comes first. Only when they sent none is a key the
    operator chose to share used - for signed-in accounts, a few times an hour.
    """
    provider = str(body.get("provider") or ai_report.DEFAULT_PROVIDER)
    if provider not in ai_report.PROVIDERS:
        raise HTTPException(422, "Unknown AI service.")
    key = str(body.get("api_key") or "").strip()
    if key:
        return provider, key
    shared = config.OPERATOR_AI_KEYS.get(provider, "")
    if not shared:
        return provider, ""
    if user["is_guest"]:
        raise HTTPException(403, "The key this server shares is for signed-in accounts. Create an account, "
                                 "or enter your own key.")
    if count:
        now = time.time()
        used = [t for t in _ai_uses.get(user["id"], []) if now - t < 3600.0]
        if len(used) >= config.AI_PER_HOUR:
            raise HTTPException(429, f"The key this server shares allows {config.AI_PER_HOUR} narratives an "
                                     "hour for each account. Try again later, or enter your own key.")
        _ai_uses[user["id"]] = used + [now]
    return provider, shared


@app.post("/api/ai/narrative")
def ai_narrative(body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    provider, key = _ai_key(body, user, count=True)
    model = ai_report.clean_model(provider, body.get("model"))
    ok, text = ai_report.generate_ai_report(key, report_service.ai_context(_cfg(body)), model=model,
                                            provider=provider)
    if not ok:
        raise HTTPException(502 if key else 400, text)
    return {"text": text, "provider": provider, "model": model}


@app.post("/api/ai/models")
def ai_models(body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    """The text models the given key can use, asked from the service itself."""
    provider, key = _ai_key(body, user, count=False)
    ok, got = ai_report.list_models(provider, key)
    if not ok:
        raise HTTPException(400, str(got))
    return {"provider": provider, "models": got}


# ---------------------------------------------------------------------------
# Projects and scenarios
# ---------------------------------------------------------------------------
def _summary_of(cfg: dict) -> dict:
    try:
        s = service.solve(cfg)
        return {"peak_b": s["peak_b"], "peak_e": s["peak_e"], "overall": s["overall"],
                "lines": len(s["lines"]), "kv": sorted({ln["kv"] for ln in s["lines"]}),
                "shield": s["shield"]["on"], "buildings": len(s["receptors"])}
    except Exception:
        return {}


@app.get("/api/projects")
def projects_list(user: dict = Depends(current_user)):
    return {"projects": db.list_projects(user["id"])}


@app.get("/api/projects/export")
def projects_export(user: dict = Depends(current_user)):
    """
    Every project of this account with its scenarios, as one file: a backup, and the
    way to carry work between copies of Taki (the web one and the desktop one).
    The projects page reads the same file back in.
    """
    items = []
    for row in db.list_projects(user["id"]):
        p = db.get_project(user["id"], row["id"])
        if p is None:                                # deleted in another tab a moment ago
            continue
        items.append({"name": p["name"], "description": p["description"], "updated_at": p["updated_at"],
                      "config": service.normalise_config(p["config"]),
                      "scenarios": [{"name": sc["name"], "note": sc["note"], "config": sc["config"]}
                                    for sc in p["scenarios"]]})
    stamp = time.strftime("%Y-%m-%d")
    return JSONResponse({"taki": "projects", "version": 4, "app_version": config.VERSION,
                         "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "projects": items},
                        headers={"Content-Disposition": f'attachment; filename="taki-projects-{stamp}.taki.json"'})


@app.post("/api/projects")
def projects_create(body: Dict[str, Any] = Body(...), user: dict = Depends(current_user)):
    if db.count_projects(user["id"]) >= config.MAX_PROJECTS:
        raise HTTPException(400, "Project limit reached. Delete one first.")
    cfg = service.normalise_config(body.get("config"))
    name = str(body.get("name") or "Untitled project").strip() or "Untitled project"
    return {"project": db.create_project(user["id"], name, cfg, str(body.get("description") or ""),
                                         _summary_of(cfg))}


@app.get("/api/projects/{project_id}")
def projects_get(project_id: str, user: dict = Depends(current_user)):
    p = db.get_project(user["id"], project_id)
    if p is None:
        raise HTTPException(404, "Project not found.")
    p["config"] = service.normalise_config(p["config"])
    return {"project": p}


@app.put("/api/projects/{project_id}")
def projects_update(project_id: str, body: Dict[str, Any] = Body(...),
                    user: dict = Depends(current_user)):
    cfg = service.normalise_config(body["config"]) if "config" in body else None
    p = db.update_project(user["id"], project_id, body.get("name"), body.get("description"), cfg,
                          _summary_of(cfg) if cfg is not None else None)
    if p is None:
        raise HTTPException(404, "Project not found.")
    return {"project": p}


@app.delete("/api/projects/{project_id}")
def projects_delete(project_id: str, user: dict = Depends(current_user)):
    if not db.delete_project(user["id"], project_id):
        raise HTTPException(404, "Project not found.")
    return {"ok": True}


@app.post("/api/projects/{project_id}/duplicate")
def projects_duplicate(project_id: str, user: dict = Depends(current_user)):
    p = db.get_project(user["id"], project_id)
    if p is None:
        raise HTTPException(404, "Project not found.")
    if db.count_projects(user["id"]) >= config.MAX_PROJECTS:
        raise HTTPException(400, "Project limit reached. Delete one first.")
    return {"project": _copy_project(user["id"], p, f"{p['name']} (copy)")}


def _copy_project(user_id: str, p: dict, name: str) -> dict:
    new = db.create_project(user_id, name, p["config"], p["description"], p["summary"])
    for s in p["scenarios"]:
        db.add_scenario(new["id"], s["name"], s["config"], s["note"], s["summary"])
    return db.get_project(user_id, new["id"])  # type: ignore[return-value]


@app.post("/api/projects/{project_id}/share")
def projects_share(project_id: str, request: Request, user: dict = Depends(current_user)):
    """A link that gives whoever opens it their own copy of this project."""
    token = db.share_project(user["id"], project_id)
    if token is None:
        raise HTTPException(404, "Project not found.")
    return {"token": token, "url": f"{_public_url(request)}/s/{token}"}


@app.delete("/api/projects/{project_id}/share")
def projects_unshare(project_id: str, user: dict = Depends(current_user)):
    db.unshare_project(user["id"], project_id)
    return {"ok": True}


@app.get("/api/shared/{token}")
def shared_preview(token: str):
    """What a share link shows before it is opened. No sign-in needed; the inputs are not sent."""
    p = db.shared_project(token)
    if p is None:
        raise HTTPException(404, "This link is not active. The owner may have stopped sharing.")
    return {"name": p["name"], "description": p["description"], "owner": p["owner"],
            "summary": p["summary"], "updated_at": p["updated_at"], "scenarios": len(p["scenarios"])}


@app.post("/api/shared/{token}/open")
def shared_open(token: str, user: dict = Depends(current_user)):
    p = db.shared_project(token)
    if p is None:
        raise HTTPException(404, "This link is not active. The owner may have stopped sharing.")
    if p["owner_id"] == user["id"]:
        return {"project": db.get_project(user["id"], p["id"]), "own": True}
    if db.count_projects(user["id"]) >= config.MAX_PROJECTS:
        raise HTTPException(400, "Project limit reached. Delete one first.")
    p["config"] = service.normalise_config(p["config"])
    db.count_share_open(token)
    return {"project": _copy_project(user["id"], p, p["name"]), "own": False}


@app.post("/api/projects/{project_id}/scenarios")
def scenarios_add(project_id: str, body: Dict[str, Any] = Body(...),
                  user: dict = Depends(current_user)):
    if db.get_project(user["id"], project_id) is None:
        raise HTTPException(404, "Project not found.")
    if db.count_scenarios(project_id) >= config.MAX_SCENARIOS:
        raise HTTPException(400, "Scenario limit reached for this project.")
    cfg = service.normalise_config(body.get("config"))
    name = str(body.get("name") or "Scenario").strip() or "Scenario"
    return {"scenario": db.add_scenario(project_id, name, cfg, str(body.get("note") or ""),
                                        _summary_of(cfg))}


@app.patch("/api/projects/{project_id}/scenarios/{scenario_id}")
def scenarios_rename(project_id: str, scenario_id: str, body: Dict[str, Any] = Body(...),
                     user: dict = Depends(current_user)):
    if db.get_project(user["id"], project_id) is None:
        raise HTTPException(404, "Project not found.")
    if not db.rename_scenario(project_id, scenario_id, str(body.get("name") or "Scenario"),
                              body.get("note")):
        raise HTTPException(404, "Scenario not found.")
    return {"ok": True}


@app.delete("/api/projects/{project_id}/scenarios/{scenario_id}")
def scenarios_delete(project_id: str, scenario_id: str, user: dict = Depends(current_user)):
    if db.get_project(user["id"], project_id) is None:
        raise HTTPException(404, "Project not found.")
    if not db.delete_scenario(project_id, scenario_id):
        raise HTTPException(404, "Scenario not found.")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Front end (built files) with single-page-app fallback
# ---------------------------------------------------------------------------
_assets = os.path.join(config.STATIC_DIR, "assets")
if os.path.isdir(_assets):
    app.mount("/assets", StaticFiles(directory=_assets), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    candidate = os.path.normpath(os.path.join(config.STATIC_DIR, full_path))
    if full_path and candidate.startswith(config.STATIC_DIR) and os.path.isfile(candidate):
        if candidate.endswith(".webmanifest"):       # not every Python knows this file type
            if config.DESKTOP:
                # The desktop version is a program already. Its window must not offer to "install"
                # the page as well: that icon would point at a run that has ended.
                with open(candidate, encoding="utf-8") as fh:
                    manifest = json.load(fh)
                manifest["display"] = "browser"
                return JSONResponse(manifest, media_type="application/manifest+json",
                                    headers={"Cache-Control": "no-cache"})
            return FileResponse(candidate, media_type="application/manifest+json",
                                headers={"Cache-Control": "no-cache"})
        return FileResponse(candidate)
    index = os.path.join(config.STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse(
        "The Taki server is running, but the web interface has not been built.\n"
        "Run:  cd web && npm install && npm run build", status_code=503)
