import importlib
import json
import sys
import tempfile
import time

import bcrypt
from fastapi.testclient import TestClient


def _reload_app(monkeypatch, extra_env=None):
    keys_to_clear = [
        "ENABLE_ADMIN",
        "ADMIN_ENABLED",
        "ADMIN_PASSWORD",
        "ADMIN_PASSWORD_HASH",
        "ADMIN_USERNAME",
        "ENABLE_ADMIN_RESET",
        "ADMIN_ALLOW_RESET",
        "ENABLE_ADMIN_CONFIG_EDIT",
        "ADMIN_ALLOW_CONFIG_EDIT",
        "ENABLE_ADMIN_USER_MGMT",
        "ADMIN_ALLOW_USER_MGMT",
        "ENABLE_PROXY_AUTH",
        "PROXY_REQUIRE_AUTH",
        "PROXY_AUTH_FILE",
        "PROXY_USER_FILE",
        "METRICS_FILE",
        "PROXY_METRICS_FILE",
        "ADMIN_CONFIG_FILE",
        "PROXY_CONFIG_FILE",
    ]
    for key in keys_to_clear:
        monkeypatch.delenv(key, raising=False)
    if extra_env:
        for k, v in extra_env.items():
            monkeypatch.setenv(k, str(v))

    for mod in list(sys.modules.keys()):
        if mod == "foundry_openai_proxy" or mod.startswith("proxy."):
            sys.modules.pop(mod, None)

    import foundry_openai_proxy

    importlib.reload(foundry_openai_proxy)
    return foundry_openai_proxy.app


def test_admin_disabled_by_default(monkeypatch):
    app = _reload_app(monkeypatch, {})
    client = TestClient(app)
    resp = client.get("/admin/health")
    assert resp.status_code == 404


def test_admin_enabled_with_password(monkeypatch):
    app = _reload_app(monkeypatch, {"ENABLE_ADMIN": "1", "ADMIN_PASSWORD": "secret"})
    client = TestClient(app)
    resp = client.get("/admin/health", auth=("admin", "secret"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["config"]["enabled"] is True


def test_proxy_auth_enforced(monkeypatch):
    token_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    token = "token123"
    hashed = bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode()
    json.dump({"version": 1, "tokens": {"alice": {"hash": hashed, "created_at": time.time()}}}, token_file)
    token_file.flush()

    app = _reload_app(
        monkeypatch,
        {"ENABLE_PROXY_AUTH": "1", "PROXY_AUTH_FILE": token_file.name, "ENABLE_ADMIN": "0"},
    )
    import proxy.routes_chat as routes_chat

    def fake_create_messages(self, system, messages, max_tokens=None, temperature=None):
        return {
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "id": "resp1",
            "model": "claude",
        }

    monkeypatch.setattr(routes_chat.FoundryAnthropicClient, "create_messages", fake_create_messages)

    client = TestClient(app)

    resp_missing = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer resource:key"},
        json={"model": "claude-3", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp_missing.status_code == 200
    assert "Proxy auth required" in resp_missing.json()["choices"][0]["message"]["content"]

    resp_ok = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer resource:key", "X-Proxy-Token": token},
        json={"model": "claude-3", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["choices"][0]["message"]["content"] == "hi"
