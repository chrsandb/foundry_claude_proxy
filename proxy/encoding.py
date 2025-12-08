from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class FoundrySettings:
    """Effective per-request Foundry configuration derived from apiKey + model."""

    resource: str
    model: str
    api_key: str


def decode_api_key(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Decode logical apiKey into (foundry_resource, foundry_api_key).

    - None/empty -> (None, None)
    - \"resource:key\" -> (resource, key) when resource looks like a simple identifier
    - anything else -> (None, raw)  (treated as unstructured key)
    """
    if not raw:
        return None, None

    # Structured form: "<foundry_resource>:<foundry_api_key>"
    if raw.count(":") == 1:
        left, right = raw.split(":", 1)
        left = left.strip()
        right = right.strip()
        if left and right and _looks_like_resource(left):
            return left, right

    # Unstructured key: treat whole token as API key, no resource
    return None, raw


def decode_model(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Decode logical model into (foundry_resource_override, foundry_model).

    - None/empty -> (None, None)
    - \"resource/model\" -> (resource, model)
    - anything else -> (None, raw)  (treated as unstructured model name)
    """
    if not raw:
        return None, None

    # Structured form: "<foundry_resource>/<foundry_model>"
    if raw.count("/") == 1:
        left, right = raw.split("/", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            return left, right

    return None, raw


def derive_foundry_settings(
    logical_api_key: Optional[str],
    logical_model: Optional[str],
) -> FoundrySettings:
    """Derive a complete (resource, model, api_key) triple for this request.

    Uses only apiKey/model encoding; there are no central Foundry defaults.
    Raises ValueError with a human-readable message if it cannot derive a
    complete configuration.
    """
    api_key_resource, api_key_value = decode_api_key(logical_api_key)
    model_resource, model_value = decode_model(logical_model)

    # API key must always come from the logical apiKey (structured or plain).
    foundry_api_key = api_key_value

    # Resource precedence: from apiKey first, then from model.
    foundry_resource = api_key_resource or model_resource

    # Model precedence: from structured model, else raw logical model.
    foundry_model = model_value or logical_model

    missing_parts = []
    if not foundry_api_key:
        missing_parts.append("Foundry API key (must be provided via apiKey)")
    if not foundry_resource:
        missing_parts.append("Foundry resource (must be encoded in apiKey or model)")
    if not foundry_model:
        missing_parts.append("Foundry model (must be provided via model)")

    if missing_parts:
        raise ValueError(
            "Could not derive complete Foundry configuration; missing: "
            + "; ".join(missing_parts)
        )

    return FoundrySettings(
        resource=foundry_resource,
        model=foundry_model,
        api_key=foundry_api_key,
    )


def _looks_like_resource(text: str) -> bool:
    """Heuristic for resource segment in \"resource:key\" apiKey."""
    if not text:
        return False
    for ch in text:
        if not (ch.isalnum() or ch in "-_"):
            return False
    return True
