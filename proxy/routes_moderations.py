import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from proxy.config import dlog


router = APIRouter()


def moderation_error(message: str, model: str | None, err_type: str = "not_supported_error") -> dict:
    return {
        "error": {
            "message": message,
            "type": err_type,
            "param": None,
            "code": None,
        },
        "model": model or "unknown-model",
    }


@router.post("/v1/moderations")
async def create_moderation(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(moderation_error(f"Invalid JSON: {e}", None, err_type="invalid_request_error"), status_code=400)

    logical_model = body.get("model")
    raw_input = body.get("input")

    # For now, moderation is not supported; return deterministic OpenAI-style error.
    message = (
        "Moderations are not currently supported on this proxy. "
        "Azure AI Foundry does not expose an OpenAI-compatible /v1/moderations endpoint; "
        "use Azure AI Content Safety directly if needed."
    )

    dlog(
        "incoming_request_moderations",
        {
            "logical_model": logical_model,
            "input_present": raw_input is not None,
        },
    )

    return JSONResponse(moderation_error(message, logical_model), status_code=400)
