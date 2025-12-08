import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from proxy.config import dlog
from proxy.encoding import derive_foundry_settings
from proxy.foundry_client import FoundryAnthropicClient, map_usage
from proxy.models import to_anthropic_payload, error_response


router = APIRouter()


@router.post("/v1/completions")
async def completions(request: Request):
    """
    Basic support for the legacy /v1/completions endpoint.

    Maps:
    - prompt (str) -> single user message
    - max_tokens, temperature -> Anthropic parameters
    and returns an OpenAI-style text completion response.
    """
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(error_response(f"Invalid JSON: {e}"))

    prompt = body.get("prompt")
    if prompt is None:
        return JSONResponse(error_response("No 'prompt' field provided"))

    if isinstance(prompt, list):
        prompt = "".join(str(p) for p in prompt)
    elif not isinstance(prompt, str):
        prompt = str(prompt)

    logical_model = body.get("model")
    max_tokens = body.get("max_tokens")
    temperature = body.get("temperature")

    messages = [{"role": "user", "content": prompt}]

    dlog(
        "incoming_request_completions",
        {
            "prompt_preview": prompt[:128] if isinstance(prompt, str) else str(prompt)[:128],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logical_model": logical_model,
        },
    )

    if not logical_model:
        return JSONResponse(error_response("No 'model' field provided", model=None))

    # Resolve logical API key from Authorization header or dev override.
    logical_api_key = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        logical_api_key = auth_header.split(" ", 1)[1].strip()
    elif os.environ.get("DEV_DEFAULT_LOGICAL_API_KEY"):
        logical_api_key = os.environ["DEV_DEFAULT_LOGICAL_API_KEY"]

    try:
        payload = to_anthropic_payload(messages)
        settings = derive_foundry_settings(logical_api_key, logical_model)
        client = FoundryAnthropicClient(
            api_key=settings.api_key,
            resource=settings.resource,
            model=settings.model,
        )
        foundry_json = client.create_messages(
            system=payload.get("system"),
            messages=payload.get("messages") or [],
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except ValueError as e:
        # Configuration/derivation error: return OpenAI-style error payload.
        return JSONResponse(error_response(str(e), model=logical_model))
    except Exception as e:
        return JSONResponse(error_response(str(e), model=logical_model))

    # Map Anthropic response -> completion.text
    text_parts: list[str] = []
    content_blocks = foundry_json.get("content", [])
    if isinstance(content_blocks, dict):
        content_blocks = [content_blocks]
    for c in content_blocks:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text" and c.get("text"):
            text_parts.append(c["text"])
    completion_text = "\n".join(text_parts)
    if not completion_text and isinstance(foundry_json.get("content"), str):
        completion_text = foundry_json["content"]

    usage_info = map_usage(foundry_json)
    # Prefer the logical model requested by the client when available.
    model_name = logical_model or foundry_json.get("model", "unknown-model")
    created_raw = foundry_json.get("created_at", 0) or 0
    created = int(created_raw) if created_raw else int(time.time())
    resp_id = foundry_json.get("id", "resp_local")

    return JSONResponse(
        {
            "id": resp_id,
            "object": "text_completion",
            "model": model_name,
            "created": created,
            "choices": [
                {
                    "index": 0,
                    "text": completion_text or "(no content returned)",
                    "finish_reason": "stop",
                }
            ],
            "usage": usage_info,
        }
    )
