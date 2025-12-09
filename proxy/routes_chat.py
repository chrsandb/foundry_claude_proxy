import json
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from proxy.config import dlog
from proxy.encoding import derive_foundry_settings
from proxy.foundry_client import FoundryAnthropicClient, map_usage
from proxy.models import to_anthropic_payload, error_response
from proxy.tools import extract_tool_calls_from_text
from proxy.metrics import metrics, derive_user_id, ZERO_USAGE
from proxy.auth_tokens import extract_and_validate_proxy_token


router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    settings = None
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(error_response(f"Invalid JSON: {e}"))

    if isinstance(body, list):
        return JSONResponse(
            error_response("Batch chat requests are not supported; send a single request object.", model=None)
        )

    messages = body.get("messages", [])
    if not messages:
        return JSONResponse(error_response("No 'messages' field provided"))

    logical_model = body.get("model")
    proxy_user = None
    try:
        logical_model, proxy_user = extract_and_validate_proxy_token(logical_model, request.headers)
    except ValueError as e:
        return JSONResponse(error_response(str(e), model=logical_model or "unknown-model"))

    stream = bool(body.get("stream", False))
    # Support both "tools" and legacy "functions" lists; no fallback when client doesn't request tools.
    tool_defs = body.get("tools") or body.get("functions") or []
    has_tools = bool(tool_defs)

    dlog(
        "incoming_request_chat",
        {
            "stream": stream,
            "has_tools": has_tools,
            "tools_keys": [t.get("function", {}).get("name") for t in tool_defs],
            "logical_model": logical_model,
        },
    )

    max_tokens = body.get("max_tokens")
    temperature = body.get("temperature")

    # Resolve logical API key from Authorization header or dev override.
    logical_api_key = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        logical_api_key = auth_header.split(" ", 1)[1].strip()
    elif os.environ.get("DEV_DEFAULT_LOGICAL_API_KEY"):
        logical_api_key = os.environ["DEV_DEFAULT_LOGICAL_API_KEY"]
    user_id = proxy_user or derive_user_id(logical_api_key, body.get("user"))

    if not logical_model:
        metrics.record(
            route="/v1/chat/completions",
            model=None,
            resource=None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
        )
        return JSONResponse(error_response("No 'model' field provided", model=None))

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
        # Configuration/derivation error.
        error_text = str(e)
        dlog("foundry_config_error", error_text)
        if stream:
            metrics.record(
                route="/v1/chat/completions",
                model=logical_model,
                resource=settings.resource if settings else None,
                user_id=user_id,
                usage=ZERO_USAGE,
                error=True,
            )
            async def error_event_gen():
                created = int(time.time())
                resp_id = "error"
                first_chunk = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "model": logical_model or "unknown-model",
                    "created": created,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": error_text},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(first_chunk)}\n\n"

                done = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "model": logical_model or "unknown-model",
                    "created": created,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
                yield f"data: {json.dumps(done)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(error_event_gen(), media_type="text/event-stream")
        metrics.record(
            route="/v1/chat/completions",
            model=logical_model,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
        )
        return JSONResponse(error_response(error_text, model=logical_model))
    except Exception as e:
        error_text = str(e)
        dlog("foundry_unexpected_error", error_text)
        if stream:
            metrics.record(
                route="/v1/chat/completions",
                model=logical_model,
                resource=settings.resource if settings else None,
                user_id=user_id,
                usage=ZERO_USAGE,
                error=True,
            )
            async def error_event_gen():
                created = int(time.time())
                resp_id = "error"
                first_chunk = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "model": logical_model or "unknown-model",
                    "created": created,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": error_text},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(first_chunk)}\n\n"

                done = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "model": logical_model or "unknown-model",
                    "created": created,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
                yield f"data: {json.dumps(done)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(error_event_gen(), media_type="text/event-stream")
        metrics.record(
            route="/v1/chat/completions",
            model=logical_model,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
        )
        return JSONResponse(error_response(error_text, model=logical_model))

    # Map Anthropic response (non-stream)
    text_parts: list[str] = []
    content_blocks = foundry_json.get("content", [])
    if isinstance(content_blocks, dict):
        content_blocks = [content_blocks]
    for c in content_blocks:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text" and c.get("text"):
            text_parts.append(c["text"])
    assistant_text = "\n".join(text_parts)
    if not assistant_text and isinstance(foundry_json.get("content"), str):
        assistant_text = foundry_json["content"]

    usage_info = map_usage(foundry_json)
    # Prefer the logical model requested by the client.
    model_name = logical_model or foundry_json.get("model", "unknown-model")
    created = int(foundry_json.get("created_at", time.time()))
    resp_id = foundry_json.get("id", "resp_local")
    if not assistant_text:
        dlog("assistant_text_raw_empty", foundry_json)
    else:
        dlog("assistant_text_raw", assistant_text)

    # ---------- TOOL BRIDGE (shared for stream / non-stream) ----------
    tool_calls = []
    remaining_text = assistant_text
    if has_tools:
        tool_calls, remaining_text = extract_tool_calls_from_text(assistant_text, tool_defs)

    # ---------- STREAMING (SSE, OpenAI-style) ----------
    if stream:
        metrics.record(
            route="/v1/chat/completions",
            model=model_name,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=usage_info,
            error=False,
        )
        async def event_gen():
            first_delta = {"role": "assistant"}
            if tool_calls:
                # OpenAI streaming tool deltas expect index, id, function{name, arguments}
                delta_tool_calls = []
                for idx, tc in enumerate(tool_calls):
                    delta_tool_calls.append(
                        {
                            "index": idx,
                            "id": tc.get("id", f"call_{idx+1}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name"),
                                "arguments": tc.get("function", {}).get("arguments", ""),
                            },
                        }
                    )
                first_delta["tool_calls"] = delta_tool_calls
            else:
                first_delta["content"] = assistant_text or "(no content returned)"

            chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "delta": first_delta,
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

            done = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if tool_calls else "stop",
                    }
                ],
                "usage": usage_info,
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # ---------- NON-STREAMING ----------
    # If tools are present, try to bridge tag-based tool markers -> tool_calls
    if has_tools and tool_calls:
        metrics.record(
            route="/v1/chat/completions",
            model=model_name,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=usage_info,
            error=False,
        )
        return JSONResponse(
            {
                "id": resp_id,
                "object": "chat.completion",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": remaining_text,
                            "tool_calls": tool_calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": usage_info,
            }
        )

    # Fallback: plain assistant message (no tool calls)
    metrics.record(
        route="/v1/chat/completions",
        model=model_name,
        resource=settings.resource if settings else None,
        user_id=user_id,
        usage=usage_info,
        error=False,
    )
    return JSONResponse(
        {
            "id": resp_id,
            "object": "chat.completion",
            "model": model_name,
            "created": created,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": assistant_text or "(no content returned)"},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage_info,
        }
    )
