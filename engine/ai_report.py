"""
ai_report.py
============
Optional AI-drafted narrative for the report.

Three services can write it, and each person chooses their own:

    anthropic   Claude    api.anthropic.com        Messages API
    google      Gemini    generativelanguage.googleapis.com   generateContent
    openai      ChatGPT   api.openai.com           Chat Completions (Responses as a fallback)

The call uses the key of whoever asks for the narrative. The key arrives with
that one request, is used for that one call and is not written anywhere: not to
the database, not to a log, not into an error message. A deployment may also
set its own key for a service (see server/config.py), in which case people can
leave theirs empty; that is the operator's choice and the operator's bill.

The call is optional: every other feature works without it, and a failed call
returns a readable message instead of raising.

ARCHITECTURAL RULE
------------------
AI never makes or modifies the compliance determination. PASS / MARGINAL / FAIL
comes from standards.py, deterministically, from the physics solve. This module
only asks the model to NARRATE numbers that are already final; the prompt tells
it not to assert a different determination, and every place the text is shown
or exported labels it as AI-drafted.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

ANTHROPIC_VERSION = "2023-06-01"

#: What each service is called, where its keys come from, and model names to
#: offer before the person's own list has been fetched. Model names change
#: often; "Load my models" in the app asks the service which ones the key can use.
PROVIDERS: Dict[str, dict] = {
    "anthropic": {
        "label": "Claude (Anthropic)", "company": "Anthropic", "key_hint": "sk-ant-...",
        "key_url": "https://console.anthropic.com/settings/keys",
        "default_model": "claude-sonnet-5-5",
        "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"],
    },
    "google": {
        "label": "Gemini (Google)", "company": "Google", "key_hint": "AIza...",
        "key_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-3.8-flash",
        "models": ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"],
    },
    "openai": {
        "label": "ChatGPT (OpenAI)", "company": "OpenAI", "key_hint": "sk-...",
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-6.1-sol",
        "models": ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"],
    },
}
DEFAULT_PROVIDER = "anthropic"

# kept for callers written before there was a choice of service
API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = PROVIDERS["anthropic"]["default_model"]
AVAILABLE_MODELS = PROVIDERS["anthropic"]["models"]

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,119}$")

SYSTEM_PROMPT = (
    "You are an assistant helping an electrical engineer draft the narrative section of an EMF "
    "(electric and magnetic field) transmission-line assessment report. Write in a professional, "
    "factual, engineering-report tone (no marketing language, no first person). Ground every "
    "claim only in the data provided to you - do not invent measurements, standards, limit "
    "values, material properties or citations beyond what is given. The PASS / MARGINAL / FAIL "
    "compliance determination for each standard is already final, computed by the application's "
    "compliance engine, and provided to you below - restate it accurately but do not "
    "reinterpret, soften or contradict it, and do not compute or imply a different "
    "determination of your own. Structure the output as short paragraphs under plain-text "
    "headings (no markdown symbols). Cover, in order: (1) a one-paragraph executive summary of "
    "the configuration, earth-return model and peak fields; (2) a compliance summary that "
    "restates the given per-standard results and names the governing standard, distinguishing "
    "exposure limits from precautionary planning values where the data does; (3) if shield or "
    "building data is provided, an assessment of the shielding effect: say which model produced "
    "the numbers, explain in physical terms why the electric and magnetic fields respond "
    "differently, note any location where the field increases, repeat any caveat given, and "
    "never present shielding as a compliance credit; (4) one paragraph of plain-language risk "
    "communication for a non-specialist stakeholder; (5) two to four recommendations as short "
    "lines. Keep the whole thing under 450 words."
)


def catalogue() -> List[dict]:
    """The services on offer, for the browser (no keys, nothing secret)."""
    return [{"id": k, "label": v["label"], "company": v["company"], "key_hint": v["key_hint"],
             "key_url": v["key_url"], "default_model": v["default_model"], "models": list(v["models"])}
            for k, v in PROVIDERS.items()]


def clean_model(provider: str, model: Optional[str]) -> str:
    """A model name that is safe to put in a request, or the service's default."""
    m = str(model or "").strip()
    if m.startswith("models/"):
        m = m[len("models/"):]
    return m if _MODEL_RE.match(m) else PROVIDERS[provider]["default_model"]


def build_user_prompt(context: Dict) -> str:
    lines = ["SIMULATION CONTEXT (all figures already computed by the simulator and the "
             "compliance engine):", ""]
    lines.append(f"Number of parallel lines: {context.get('num_lines')}")
    for line in context.get("lines", []):
        lines.append(f"  - {line}")
    lines += ["", f"Earth-return model: {context.get('ground_note', 'not specified')}",
              f"System frequency: {context.get('freq_hz', 50):g} Hz",
              f"Peak B field: {context.get('peak_b_uT', 0):.3f} uT at x = "
              f"{context.get('peak_b_location_m', 0):.1f} m",
              f"Peak E field: {context.get('peak_e_kVm', 0):.3f} kV/m", "",
              "COMPLIANCE RESULTS (final - do not recompute or contradict):"]
    for r in context.get("standard_results", []):
        lines.append(f"  - {r}")
    lines.append(f"Overall (worst case across selected standards): {context.get('overall_status')}")

    for title, key in (("BUILDING RECEPTORS (informational - separate from compliance):", "buildings"),
                       ("SHIELD (informational - never a compliance credit):", "shield"),
                       ("MEASUREMENT POINTS (without -> with the shield):", "points"),
                       ("NOTES AND CAVEATS TO RESPECT:", "caveats")):
        items = context.get(key)
        if items:
            lines += ["", title] + [f"  - {ln}" for ln in items]
    if context.get("references"):
        lines += ["", "Available reference citations (use only if directly relevant; do not "
                      "fabricate others):"] + [f"  - {r}" for r in context["references"]]
    lines += ["", "Write the narrative report section now, following the structure in your "
                  "instructions."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class _Reply(Exception):
    """An HTTP error from a service: its status code and the message it gave."""
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _call(url: str, headers: Dict[str, str], payload: Optional[dict], timeout_s: int) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    head = dict(headers)
    if data is not None:
        head["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET", headers=head)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            err = body.get("error") if isinstance(body, dict) else None
            detail = (err.get("message") if isinstance(err, dict) else err) or ""
        except Exception:
            detail = ""
        raise _Reply(exc.code, str(detail))


def _explain(provider: str, exc: Exception, api_key: str) -> str:
    """A failure in plain words. Never repeats the key."""
    name = PROVIDERS[provider]["company"]
    if isinstance(exc, _Reply):
        detail = exc.message.replace(api_key, "[key]") if api_key else exc.message
        low = detail.lower()
        if exc.status in (401, 403) or "api key not valid" in low or "invalid api key" in low \
                or "incorrect api key" in low or "invalid x-api-key" in low:
            return (f"{name} did not accept the key ({exc.status}). Check that it was copied whole and "
                    f"that it is a key for {name}.")
        if exc.status == 429:
            return (f"{name} is limiting this key ({exc.status}): too many requests, or the key's quota "
                    "or credit is used up. " + detail).strip()
        if exc.status == 404 or "model" in low and ("not found" in low or "does not exist" in low
                                                      or "not supported" in low):
            return (f"{name} does not offer that model to this key ({exc.status}). Use \"Load my models\" "
                    "and choose one from the list. " + detail).strip()
        return f"{name} returned an error ({exc.status}). {detail}".strip()
    text = str(getattr(exc, "reason", None) or exc)
    if api_key:
        text = text.replace(api_key, "[key]")
    return (f"Could not reach {name} from the computer that runs Taki ({text}). Check its internet "
            "connection, or whether a firewall or proxy blocks that service.")


# ---------------------------------------------------------------------------
# One request per service
# ---------------------------------------------------------------------------
def _anthropic(key: str, model: str, prompt: str, max_tokens: int, timeout_s: int) -> str:
    data = _call(API_URL, {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
                 {"model": model, "max_tokens": max_tokens, "system": SYSTEM_PROMPT,
                  "messages": [{"role": "user", "content": prompt}]}, timeout_s)
    return "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def _google(key: str, model: str, prompt: str, max_tokens: int, timeout_s: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    data = _call(url, {"x-goog-api-key": key},
                 {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                  "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                  # these models think before they answer, and the thinking counts against the limit
                  "generationConfig": {"maxOutputTokens": max(max_tokens, 8192)}}, timeout_s)
    cands = data.get("candidates") or []
    if not cands:
        reason = (data.get("promptFeedback") or {}).get("blockReason")
        raise _Reply(200, f"No text came back{f' (blocked: {reason})' if reason else ''}.")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "\n".join(p.get("text", "") for p in parts if p.get("text") and not p.get("thought")).strip()
    if not text and cands[0].get("finishReason") == "MAX_TOKENS":
        raise _Reply(200, "The model used its whole allowance before writing anything. Try a smaller, "
                          "faster model.")
    return text


def _openai(key: str, model: str, prompt: str, max_tokens: int, timeout_s: int) -> str:
    head = {"Authorization": f"Bearer {key}"}
    allowance = max(max_tokens, 6000)           # reasoning models spend part of it on thinking
    try:
        data = _call("https://api.openai.com/v1/chat/completions", head,
                     {"model": model, "max_completion_tokens": allowance,
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": prompt}]}, timeout_s)
    except _Reply as exc:
        if exc.status in (400, 404) and "responses" in exc.message.lower():
            return _openai_responses(head, model, prompt, allowance, timeout_s)   # a model without chat completions
        raise
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):               # some models return the text in parts
        content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    text = (content or "").strip()
    if not text and choice.get("finish_reason") == "length":
        raise _Reply(200, "The model used its whole allowance before writing anything. Try a smaller, "
                          "faster model.")
    return text


def _openai_responses(head: Dict[str, str], model: str, prompt: str, allowance: int, timeout_s: int) -> str:
    data = _call("https://api.openai.com/v1/responses", head,
                 {"model": model, "instructions": SYSTEM_PROMPT, "input": prompt,
                  "max_output_tokens": allowance, "store": False}, timeout_s)
    out = []
    for item in data.get("output") or []:
        if item.get("type") == "message":
            out += [c.get("text", "") for c in item.get("content") or [] if c.get("type") == "output_text"]
    return "\n".join(t for t in out if t).strip()


_WRITERS = {"anthropic": _anthropic, "google": _google, "openai": _openai}


def generate_ai_report(api_key: str, context: Dict, model: Optional[str] = None,
                       max_tokens: int = 1500, timeout_s: int = 90,
                       provider: str = DEFAULT_PROVIDER) -> Tuple[bool, str]:
    """Returns (success, text). On failure, text is a short explanation for the person."""
    if provider not in PROVIDERS:
        return False, "Unknown AI service."
    key = (api_key or "").strip()
    if not key:
        return False, (f"No API key was given for {PROVIDERS[provider]['company']}. Enter yours in the AI "
                       "narrative box; it stays in your browser.")
    try:
        text = _WRITERS[provider](key, clean_model(provider, model), build_user_prompt(context),
                                  max_tokens, timeout_s)
    except Exception as exc:                      # HTTP errors, network errors, timeouts, bad JSON
        return False, _explain(provider, exc, key)
    if not text:
        return False, f"{PROVIDERS[provider]['company']} returned an empty response. Try again."
    return True, text


# ---------------------------------------------------------------------------
# Which models can this key use?
# ---------------------------------------------------------------------------
_NOT_TEXT = ("embed", "image", "imagen", "tts", "audio", "live", "realtime", "transcri", "speech", "whisper",
             "moderation", "search", "robotics", "computer-use", "veo", "sora", "dall", "aqa", "instruct",
             "omni")


def _text_model(name: str) -> bool:
    low = name.lower()
    return not any(k in low for k in _NOT_TEXT)


def list_models(provider: str, api_key: str, timeout_s: int = 20) -> Tuple[bool, object]:
    """
    Ask the service which text models this key can use.
    Returns (True, [model names, newest first where the service says]) or (False, message).
    """
    if provider not in PROVIDERS:
        return False, "Unknown AI service."
    key = (api_key or "").strip()
    if not key:
        return False, f"Enter your {PROVIDERS[provider]['company']} key first."
    try:
        if provider == "anthropic":
            data = _call("https://api.anthropic.com/v1/models?limit=100",
                         {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}, None, timeout_s)
            names = [m.get("id", "") for m in data.get("data", [])]
        elif provider == "google":
            data = _call("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                         {"x-goog-api-key": key}, None, timeout_s)
            names = [m.get("name", "").split("/", 1)[-1] for m in data.get("models", [])
                     if "generateContent" in (m.get("supportedGenerationMethods") or [])]
            names = sorted((n for n in names if n.startswith("gemini")), reverse=True)
        else:
            data = _call("https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"}, None, timeout_s)
            rows = [m for m in data.get("data", [])
                    if str(m.get("id", "")).startswith(("gpt-", "o1", "o3", "o4", "o5", "chatgpt-"))]
            rows.sort(key=lambda m: m.get("created") or 0, reverse=True)
            names = [m["id"] for m in rows]
    except Exception as exc:
        return False, _explain(provider, exc, key)
    names = [n for n in names if n and _MODEL_RE.match(n) and _text_model(n)]
    if not names:
        return False, f"{PROVIDERS[provider]['company']} listed no text models for this key."
    return True, names[:60]
