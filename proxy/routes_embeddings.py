import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from proxy.config import dlog
from proxy.encoding import derive_foundry_settings
from proxy.foundry_client import FoundryEmbeddingsClient, map_usage
from proxy.metrics import metrics, derive_user_id, ZERO_USAGE
from proxy.auth_tokens import extract_and_validate_proxy_token


router = APIRouter()


def embeddings_error(message: str, model: str | None, err_type: str = "invalid_request_error") -> dict:
    return {
        "error": {
            "message": message,
            "type": err_type,
            "param": None,
            "code": None,
        },
        "model": model or "unknown-model",
    }


@router.post("/v1/embeddings")
async def create_embeddings(request: Request):
    start_time = time.time()

    def duration_ms() -> int:
        return int((time.time() - start_time) * 1000)

    try:
        body = await request.json()
    except Exception as e:
        metrics.record(
            route="/v1/embeddings",
            model=None,
            resource=None,
            user_id="unknown",
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error(f"Invalid JSON: {e}", None), status_code=400)

    logical_model = body.get("model")
    proxy_user = None
    try:
        logical_model, proxy_user = extract_and_validate_proxy_token(logical_model, request.headers)
    except ValueError as e:
        return JSONResponse(embeddings_error(str(e), logical_model or "unknown-model"), status_code=401)
    if not logical_model:
        metrics.record(
            route="/v1/embeddings",
            model=None,
            resource=None,
            user_id="unknown",
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error("No 'model' field provided", None), status_code=400)

    raw_input = body.get("input")
    if raw_input is None:
        metrics.record(
            route="/v1/embeddings",
            model=logical_model,
            resource=None,
            user_id=user_id if "user_id" in locals() else "unknown",
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error("No 'input' field provided", logical_model), status_code=400)

    settings = None

    def normalize_value(val):
        if isinstance(val, str):
            return val
        # Preserve numbers/bools via str to match OpenAI input expectations for embeddings.
        if isinstance(val, (int, float, bool)):
            return str(val)
        return str(val)

    inputs = raw_input
    if isinstance(raw_input, list):
        inputs = [normalize_value(v) for v in raw_input]
    elif not isinstance(raw_input, str):
        inputs = normalize_value(raw_input)

    logical_api_key = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        logical_api_key = auth_header.split(" ", 1)[1].strip()
    elif os.environ.get("DEV_DEFAULT_LOGICAL_API_KEY"):
        logical_api_key = os.environ["DEV_DEFAULT_LOGICAL_API_KEY"]
    user_id = proxy_user or derive_user_id(logical_api_key, body.get("user"))

    dlog(
        "incoming_request_embeddings",
        {
            "logical_model": logical_model,
            "input_preview": str(inputs)[:128],
        },
    )

    try:
        settings = derive_foundry_settings(logical_api_key, logical_model)
        client = FoundryEmbeddingsClient(
            api_key=settings.api_key,
            resource=settings.resource,
            model=settings.model,
        )
        upstream = client.create_embeddings(inputs)
    except NotImplementedError as e:
        metrics.record(
            route="/v1/embeddings",
            model=logical_model,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error(str(e), logical_model, err_type="not_supported_error"), status_code=400)
    except ValueError as e:
        metrics.record(
            route="/v1/embeddings",
            model=logical_model,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error(str(e), logical_model), status_code=400)
    except Exception as e:
        metrics.record(
            route="/v1/embeddings",
            model=logical_model,
            resource=settings.resource if settings else None,
            user_id=user_id,
            usage=ZERO_USAGE,
            error=True,
            duration_ms=duration_ms(),
        )
        return JSONResponse(embeddings_error(str(e), logical_model, err_type="server_error"), status_code=500)

    raw_data = upstream.get("data", [])
    if isinstance(raw_data, dict):
        raw_data = [raw_data]

    data_items = []
    for idx, item in enumerate(raw_data):
        embedding_vec = item.get("embedding") or item.get("vector") or []
        data_items.append(
            {
                "object": item.get("object", "embedding"),
                "index": item.get("index", idx),
                "embedding": embedding_vec,
            }
        )

    created_raw = upstream.get("created") or upstream.get("created_at") or int(time.time())
    usage_info = map_usage(upstream)
    metrics.record(
        route="/v1/embeddings",
        model=logical_model,
        resource=settings.resource if settings else None,
        user_id=user_id,
        usage=usage_info,
        error=False,
        duration_ms=duration_ms(),
    )
    response = {
        "object": "list",
        "model": logical_model,
        "data": data_items,
        "usage": usage_info,
        "created": int(created_raw) if created_raw else int(time.time()),
    }
    return JSONResponse(response)
