import json

from fastapi.testclient import TestClient

from foundry_openai_proxy import app
import proxy.routes_embeddings as routes_embeddings


client = TestClient(app)


def test_embeddings_success(monkeypatch):
    def fake_create(self, inputs):
        return {
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
            "usage": {"input_tokens": 5, "output_tokens": 0},
            "created": 123,
        }

    monkeypatch.setattr(routes_embeddings.FoundryEmbeddingsClient, "create_embeddings", fake_create)
    resp = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer resource:key"},
        json={"model": "text-embedding-3-large", "input": "hello"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert data["usage"]["prompt_tokens"] == 5


def test_embeddings_not_supported(monkeypatch):
    def fake_create(self, inputs):
        raise NotImplementedError("not available")

    monkeypatch.setattr(routes_embeddings.FoundryEmbeddingsClient, "create_embeddings", fake_create)
    resp = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer resource:key"},
        json={"model": "text-embedding-3-large", "input": "hello"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["type"] == "not_supported_error"


def test_moderations_unsupported():
    resp = client.post(
        "/v1/moderations",
        headers={"Authorization": "Bearer resource:key"},
        json={"model": "text-moderation-latest", "input": "hello"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["type"] == "not_supported_error"
