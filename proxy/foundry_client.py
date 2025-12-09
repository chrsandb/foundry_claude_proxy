from typing import Any, Dict, List
import json
import os

import requests

from anthropic import AnthropicFoundry

from .config import dlog


def _to_dict(obj: Any) -> Dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    try:
        return json.loads(obj.model_dump_json())  # type: ignore[attr-defined]
    except Exception:
        try:
            return obj.__dict__
        except Exception:
            return {}


def map_usage(foundry_json: Dict) -> Dict:
    usage = foundry_json.get("usage", {})
    prompt = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    comp = usage.get("output_tokens", usage.get("completion_tokens", 0))
    total = usage.get("total_tokens", prompt + comp)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": comp,
        "total_tokens": total,
    }


DEFAULT_EMBEDDINGS_API_VERSION = os.environ.get("EMBEDDINGS_API_VERSION") or os.environ.get("OPENAI_API_VERSION") or "2024-05-01-preview"


class FoundryEmbeddingsClient:
    """Minimal client for Foundry/OpenAI-compatible embeddings endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        resource: str,
        model: str,
        api_version: str | None = None,
    ) -> None:
        self._resource = resource
        self._model = model
        self._api_key = api_key
        self._api_version = api_version or DEFAULT_EMBEDDINGS_API_VERSION
        base_url = f"https://{self._resource}.services.ai.azure.com"
        self._url = f"{base_url}/openai/deployments/{self._model}/embeddings?api-version={self._api_version}"

    def create_embeddings(self, inputs: List[str] | str) -> Dict:
        payload = {"input": inputs, "model": self._model}
        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
        }
        dlog(
            "foundry_embeddings_request",
            {"url": self._url, "payload_preview": str(payload)[:256]},
        )
        try:
            resp = requests.post(self._url, json=payload, headers=headers, timeout=30)
        except Exception as e:
            raise ValueError(f"Could not reach Foundry embeddings endpoint: {e}") from e

        if resp.status_code == 404:
            # Explicit not-supported case for resources without embeddings.
            raise NotImplementedError(
                "Embeddings are not available on this Foundry resource/model. "
                "Verify that the deployment exists and supports the embeddings route."
            )
        if resp.status_code >= 400:
            try:
                err_json = resp.json()
                err_msg = err_json.get("error", {}).get("message") or err_json.get("message") or resp.text
            except Exception:
                err_msg = resp.text
            raise ValueError(f"Upstream embeddings error ({resp.status_code}): {err_msg}")

        try:
            data = resp.json()
        except Exception as e:
            raise ValueError(f"Invalid JSON from embeddings response: {e}") from e

        dlog(
            "foundry_embeddings_response",
            {
                "usage": data.get("usage"),
                "data_len": len(data.get("data", []) or []),
            },
        )
        return data


class FoundryAnthropicClient:
    """Thin wrapper around AnthropicFoundry for non-stream chat/completions.

    Routes should pass per-request settings (api_key/resource/model)
    derived from proxy.encoding. Env/.env values act as fallbacks.
    """

    def __init__(
        self,
        *,
        api_key: str,
        resource: str,
        model: str,
    ) -> None:
        self._resource = resource
        base_url = f"https://{self._resource}.services.ai.azure.com/anthropic/"
        self._client = AnthropicFoundry(api_key=api_key, base_url=base_url)
        self._model = model

    def create_messages(
        self,
        system: str | None,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Dict:
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens or 1024,
            "stream": False,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        dlog("foundry_payload", {"payload": {"system": system, "messages": messages}, "auth_mode": "api-key-anthropic"})
        try:
            resp = self._client.messages.create(**kwargs)
        except Exception as e:
            message = str(e)
            # Provide a clearer hint when the Foundry resource cannot be reached.
            if "Connection error" in message or "Name or service not known" in message or "getaddrinfo failed" in message:
                raise ValueError(
                    f"Could not reach Foundry resource '{self._resource}'. "
                    "Verify that the resource name in your apiKey is correct and accessible. "
                    f"Underlying error: {message}"
                ) from e
            raise
        data = _to_dict(resp)
        dlog(
            "foundry_response",
            {
                "model": data.get("model"),
                "id": data.get("id"),
                "usage": data.get("usage"),
                "content_preview": data.get("content"),
            },
        )
        return data
