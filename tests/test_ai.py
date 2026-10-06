"""
The AI narrative: three services, each person's own key.

Nothing here touches the network: urllib is replaced by a recorder that plays
back replies in the shape each service documents.
"""

import io
import json
import urllib.error

import pytest

from engine import ai_report
from server import config, main, service

from test_api import register

KEY = "sk-test-SECRET-0123456789"
CONTEXT = {"num_lines": 1, "lines": ["Line 1: 132 kV"], "peak_b_uT": 2.5, "peak_e_kVm": 0.4,
           "overall_status": "PASS", "standard_results": ["ICNIRP 2010: PASS"]}


class _Resp:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(url, status, message):
    body = io.BytesIO(json.dumps({"error": {"message": message}}).encode("utf-8"))
    return urllib.error.HTTPError(url, status, "error", {}, body)


@pytest.fixture()
def wire(monkeypatch):
    """Replace the network. wire.replies is a list of payloads (or exceptions) to play back in order."""
    class Wire:
        def __init__(self):
            self.calls, self.replies = [], []

        def urlopen(self, req, timeout=None):
            body = json.loads(req.data.decode("utf-8")) if req.data else None
            self.calls.append({"url": req.full_url, "method": req.get_method(), "timeout": timeout,
                               "headers": {k.lower(): v for k, v in req.header_items()}, "body": body})
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            if callable(reply):
                reply = reply(req.full_url)
                if isinstance(reply, Exception):
                    raise reply
            return _Resp(reply)

    w = Wire()
    monkeypatch.setattr(ai_report.urllib.request, "urlopen", w.urlopen)
    return w


# ---------------------------------------------------------------------------
# One request per service, in that service's own format
# ---------------------------------------------------------------------------
def test_claude_request_and_reply(wire):
    wire.replies = [{"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "Summary."},
                                 {"type": "text", "text": "More."}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, provider="anthropic")
    assert ok and text == "Summary.\nMore."
    call = wire.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages" and call["method"] == "POST"
    assert call["headers"]["x-api-key"] == KEY and call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["headers"]["content-type"] == "application/json"
    body = call["body"]
    assert body["model"] == ai_report.PROVIDERS["anthropic"]["default_model"] and body["max_tokens"] == 1500
    assert body["system"] == ai_report.SYSTEM_PROMPT and body["messages"][0]["role"] == "user"
    assert "Peak B field: 2.500 uT" in body["messages"][0]["content"]


def test_gemini_request_and_reply(wire):
    wire.replies = [{"candidates": [{"content": {"parts": [{"text": "let me think", "thought": True},
                                                            {"text": "The line passes."}]},
                                     "finishReason": "STOP"}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, model="models/gemini-test-1", provider="google")
    assert ok and text == "The line passes."                 # the model's thinking is not part of the report
    call = wire.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-1:generateContent"
    assert KEY not in call["url"]                            # a key in the address would end up in logs
    assert call["headers"]["x-goog-api-key"] == KEY
    body = call["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == ai_report.SYSTEM_PROMPT
    assert body["contents"][0]["role"] == "user" and "COMPLIANCE RESULTS" in body["contents"][0]["parts"][0]["text"]
    assert body["generationConfig"]["maxOutputTokens"] >= 8192


def test_gemini_empty_and_blocked_replies_are_explained(wire):
    wire.replies = [{"promptFeedback": {"blockReason": "SAFETY"}},
                    {"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]},
                    {"candidates": [{"content": {"parts": [{"text": "   "}]}}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, provider="google")
    assert not ok and "blocked: SAFETY" in text
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, provider="google")
    assert not ok and "whole allowance" in text
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, provider="google")
    assert not ok and "empty response" in text


def test_chatgpt_request_and_reply(wire):
    wire.replies = [{"choices": [{"message": {"role": "assistant", "content": "  Within limits.  "},
                                  "finish_reason": "stop"}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, model="gpt-test", provider="openai")
    assert ok and text == "Within limits."
    call = wire.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["authorization"] == f"Bearer {KEY}"
    body = call["body"]
    assert body["model"] == "gpt-test" and body["max_completion_tokens"] >= 6000 and "max_tokens" not in body
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    # some models hand the text back in parts
    wire.replies = [{"choices": [{"message": {"content": [{"type": "text", "text": "A."}, {"type": "text", "text": "B."}]}}]}]
    assert ai_report.generate_ai_report(KEY, CONTEXT, provider="openai") == (True, "A.\nB.")
    wire.replies = [{"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, provider="openai")
    assert not ok and "whole allowance" in text


def test_chatgpt_models_without_chat_completions_use_the_responses_api(wire):
    wire.replies = [
        lambda url: _http_error(url, 404, "This model is only supported in v1/responses and not in v1/chat/completions."),
        {"output": [{"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": "From responses."}]}]}]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, model="gpt-pro-test", provider="openai")
    assert ok and text == "From responses."
    assert [c["url"] for c in wire.calls] == ["https://api.openai.com/v1/chat/completions",
                                              "https://api.openai.com/v1/responses"]
    body = wire.calls[1]["body"]
    assert body["model"] == "gpt-pro-test" and body["instructions"] == ai_report.SYSTEM_PROMPT
    assert isinstance(body["input"], str) and body["store"] is False and body["max_output_tokens"] >= 6000
    assert wire.calls[1]["headers"]["authorization"] == f"Bearer {KEY}"
    # any other 404 is reported, not retried
    wire.calls.clear()
    wire.replies = [lambda url: _http_error(url, 404, "The model `nope` does not exist")]
    ok, text = ai_report.generate_ai_report(KEY, CONTEXT, model="nope", provider="openai")
    assert not ok and len(wire.calls) == 1 and "Load my models" in text


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("provider", list(ai_report.PROVIDERS))
def test_failures_are_explained_and_never_repeat_the_key(wire, provider):
    company = ai_report.PROVIDERS[provider]["company"]
    wire.replies = [
        lambda url: _http_error(url, 401, f"Incorrect API key provided: {KEY}."),
        lambda url: _http_error(url, 429, "You exceeded your current quota."),
        lambda url: _http_error(url, 400, f"API key not valid ({KEY}). Please pass a valid API key."),
        lambda url: _http_error(url, 500, "Internal error"),
        urllib.error.URLError(f"Tunnel connection failed for {KEY}"),
        TimeoutError("timed out"),
    ]
    out = [ai_report.generate_ai_report(KEY, CONTEXT, provider=provider) for _ in range(6)]
    assert not any(ok for ok, _ in out)
    assert all(KEY not in text for _, text in out)
    rejected, limited, invalid, broken, offline, slow = [text for _, text in out]
    assert "did not accept the key" in rejected and company in rejected
    assert "limiting this key" in limited and "quota" in limited
    assert "did not accept the key" in invalid
    assert "returned an error (500)" in broken
    assert "Could not reach" in offline and company in offline and "[key]" in offline
    assert "Could not reach" in slow


def test_without_a_key_nothing_is_sent(wire):
    for provider in ai_report.PROVIDERS:
        ok, text = ai_report.generate_ai_report("   ", CONTEXT, provider=provider)
        assert not ok and "stays in your browser" in text
        assert ai_report.list_models(provider, "")[0] is False
    assert ai_report.generate_ai_report(KEY, CONTEXT, provider="skynet") == (False, "Unknown AI service.")
    assert ai_report.list_models("skynet", KEY) == (False, "Unknown AI service.")
    assert wire.calls == []


def test_model_names_are_made_safe_before_they_reach_an_address():
    clean = ai_report.clean_model
    assert clean("google", "models/gemini-9-flash") == "gemini-9-flash"
    assert clean("openai", " gpt-x.1:custom ") == "gpt-x.1:custom"
    for bad in (None, "", "a/b", "gemini?key=1", "../etc", "x" * 200, "né", "a b", "-leading"):
        assert clean("google", bad) == ai_report.PROVIDERS["google"]["default_model"], bad
    assert clean("anthropic", "anything goes?") == ai_report.DEFAULT_MODEL


def test_the_catalogue_holds_no_secrets():
    cat = ai_report.catalogue()
    assert [c["id"] for c in cat] == ["anthropic", "google", "openai"]
    for c in cat:
        assert c["default_model"] == c["models"][0] and c["key_url"].startswith("https://")
        assert set(c) == {"id", "label", "company", "key_hint", "key_url", "default_model", "models"}


# ---------------------------------------------------------------------------
# Which models can this key use?
# ---------------------------------------------------------------------------
def test_model_lists_come_from_the_service_and_keep_text_models_only(wire):
    wire.replies = [{"data": [{"id": "claude-b-2"}, {"id": "claude-a-1"}, {"id": ""}]}]
    assert ai_report.list_models("anthropic", KEY) == (True, ["claude-b-2", "claude-a-1"])
    assert wire.calls[0]["url"].startswith("https://api.anthropic.com/v1/models") and wire.calls[0]["method"] == "GET"
    assert wire.calls[0]["headers"]["x-api-key"] == KEY and wire.calls[0]["body"] is None

    wire.replies = [{"models": [
        {"name": "models/gemini-2-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
        {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-flash-image", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-1", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/gemini-3-flash-live", "supportedGenerationMethods": ["generateContent", "bidiGenerateContent"]},
        {"name": "models/gemma-3", "supportedGenerationMethods": ["generateContent"]}]}]
    assert ai_report.list_models("google", KEY) == (True, ["gemini-3-pro", "gemini-2-flash"])
    assert KEY not in wire.calls[1]["url"] and wire.calls[1]["headers"]["x-goog-api-key"] == KEY

    wire.replies = [{"data": [{"id": "gpt-old", "created": 10}, {"id": "gpt-new", "created": 30},
                              {"id": "o3-mini", "created": 20}, {"id": "gpt-new-audio-preview", "created": 40},
                              {"id": "text-embedding-3", "created": 50}, {"id": "dall-e-3", "created": 60},
                              {"id": "gpt-image-1", "created": 70}, {"id": "whisper-1", "created": 5}]}]
    assert ai_report.list_models("openai", KEY) == (True, ["gpt-new", "o3-mini", "gpt-old"])
    assert wire.calls[2]["headers"]["authorization"] == f"Bearer {KEY}"

    wire.replies = [{"data": []}, lambda url: _http_error(url, 401, "invalid x-api-key")]
    ok, text = ai_report.list_models("anthropic", KEY)
    assert not ok and "listed no text models" in text
    ok, text = ai_report.list_models("anthropic", KEY)
    assert not ok and "did not accept the key" in text


# ---------------------------------------------------------------------------
# The two endpoints
# ---------------------------------------------------------------------------
@pytest.fixture()
def calls(monkeypatch):
    """Record what the endpoints hand to the AI module instead of calling out."""
    seen = []

    def fake_generate(api_key, context, model=None, max_tokens=1500, timeout_s=90, provider="anthropic"):
        seen.append({"what": "narrative", "key": api_key, "model": model, "provider": provider,
                     "context": context})
        return (True, f"Narrative by {provider}.") if api_key else (False, "No API key was given.")

    def fake_models(provider, api_key, timeout_s=20):
        seen.append({"what": "models", "key": api_key, "provider": provider})
        return (True, ["m-2", "m-1"]) if api_key else (False, "Enter your key first.")

    monkeypatch.setattr(ai_report, "generate_ai_report", fake_generate)
    monkeypatch.setattr(ai_report, "list_models", fake_models)
    monkeypatch.setattr(config, "OPERATOR_AI_KEYS", {"anthropic": "", "google": "", "openai": ""})
    main._ai_uses.clear()
    return seen


def test_narrative_uses_the_key_that_came_with_the_request(guest, calls):
    body = {"config": service.default_config(), "provider": "google", "api_key": f"  {KEY} ", "model": "gemini-x"}
    r = guest.post("/api/ai/narrative", json=body)
    assert r.status_code == 200 and r.json() == {"text": "Narrative by google.", "provider": "google", "model": "gemini-x"}
    assert calls[0]["key"] == KEY and calls[0]["provider"] == "google" and calls[0]["model"] == "gemini-x"
    assert calls[0]["context"]["num_lines"] == 1 and calls[0]["context"]["overall_status"]
    # an unsafe model name is replaced, an unknown service refused
    r = guest.post("/api/ai/narrative", json={**body, "model": "x/../y"})
    assert r.json()["model"] == ai_report.PROVIDERS["google"]["default_model"]
    assert guest.post("/api/ai/narrative", json={**body, "provider": "skynet"}).status_code == 422
    # no key anywhere: a plain message, and nothing is spent
    r = guest.post("/api/ai/narrative", json={"config": service.default_config(), "provider": "openai"})
    assert r.status_code == 400 and "key" in r.json()["detail"].lower()
    assert guest.get("/api/meta").json()["operator_ai"] == []


def test_a_key_is_never_stored(guest, calls, tmp_path):
    guest.post("/api/projects", json={"name": "P", "config": service.default_config()})
    guest.post("/api/ai/narrative", json={"config": service.default_config(), "provider": "openai", "api_key": KEY})
    guest.post("/api/ai/models", json={"provider": "openai", "api_key": KEY})
    from server import db
    rows = 0
    for table in db.TABLES:                                   # every table, whichever database is in use
        for row in db.conn().execute(f"SELECT * FROM {table}").fetchall():
            rows += 1
            assert KEY not in json.dumps(dict(row), default=str), table
    assert rows >= 3                                          # a user, a session and a project were written
    for path in tmp_path.rglob("*"):                          # and nothing on disk beside the database either
        if path.is_file():
            assert KEY.encode() not in path.read_bytes(), path.name


def test_model_list_endpoint(guest, calls):
    r = guest.post("/api/ai/models", json={"provider": "anthropic", "api_key": KEY})
    assert r.status_code == 200 and r.json() == {"provider": "anthropic", "models": ["m-2", "m-1"]}
    assert calls[-1] == {"what": "models", "key": KEY, "provider": "anthropic"}
    assert guest.post("/api/ai/models", json={"provider": "anthropic"}).status_code == 400
    assert guest.post("/api/ai/models", json={"provider": "nope", "api_key": KEY}).status_code == 422


def test_ai_endpoints_need_a_session(client, calls):
    assert client.post("/api/ai/narrative", json={"config": {}, "api_key": KEY}).status_code == 401
    assert client.post("/api/ai/models", json={"provider": "google", "api_key": KEY}).status_code == 401
    assert calls == []


def test_a_key_the_operator_shares_is_for_accounts_and_is_rationed(client, calls, monkeypatch):
    monkeypatch.setattr(config, "OPERATOR_AI_KEYS", {"anthropic": "operator-key", "google": "", "openai": ""})
    monkeypatch.setattr(config, "AI_PER_HOUR", 2)
    assert client.get("/api/meta").json()["operator_ai"] == ["anthropic"]
    body = {"config": service.default_config(), "provider": "anthropic"}
    client.post("/api/auth/guest", json={})
    r = client.post("/api/ai/narrative", json=body)
    assert r.status_code == 403 and "signed-in accounts" in r.json()["detail"] and calls == []
    assert client.post("/api/ai/narrative", json={**body, "api_key": KEY}).status_code == 200   # a guest's own key works
    client.post("/api/auth/logout", json={})
    register(client)
    assert client.post("/api/ai/narrative", json=body).status_code == 200
    assert calls[-1]["key"] == "operator-key"
    assert client.post("/api/ai/models", json={"provider": "anthropic"}).status_code == 200    # listing is not counted
    assert client.post("/api/ai/narrative", json=body).status_code == 200
    r = client.post("/api/ai/narrative", json=body)
    assert r.status_code == 429 and "2 narratives an hour" in r.json()["detail"]
    assert client.post("/api/ai/narrative", json={**body, "api_key": KEY}).status_code == 200   # own key: no limit
    assert calls[-1]["key"] == KEY
    # the shared key is for that one service only
    r = client.post("/api/ai/narrative", json={**body, "provider": "google"})
    assert r.status_code == 400


def test_only_taki_named_keys_are_ever_shared(monkeypatch):
    """A key that sits in the environment for some other program must not be handed to everyone."""
    import importlib
    monkeypatch.setenv("ANTHROPIC_API_KEY", "someone-elses")
    monkeypatch.setenv("GEMINI_API_KEY", "someone-elses")
    monkeypatch.setenv("GOOGLE_API_KEY", "someone-elses")
    monkeypatch.setenv("OPENAI_API_KEY", "someone-elses")
    for name in ("TAKI_ANTHROPIC_API_KEY", "TAKI_GEMINI_API_KEY", "TAKI_OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    data_dir, url = config.DATA_DIR, config.DATABASE_URL
    try:
        fresh = importlib.reload(config)
        assert fresh.OPERATOR_AI_KEYS == {"anthropic": "", "google": "", "openai": ""}
        monkeypatch.setenv("TAKI_GEMINI_API_KEY", " shared ")
        fresh = importlib.reload(config)
        assert fresh.OPERATOR_AI_KEYS == {"anthropic": "", "google": "shared", "openai": ""}
    finally:
        monkeypatch.delenv("TAKI_GEMINI_API_KEY", raising=False)
        importlib.reload(config)
        config.set_data_dir(data_dir)
        config.DATABASE_URL = url
