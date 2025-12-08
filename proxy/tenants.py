import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional

from .config import dlog


@dataclass(frozen=True)
class TenantConfig:
    """Internal mapping from logical apiKey/model to concrete Foundry settings."""

    tenant_id: str
    logical_model: str
    foundry_resource: str
    foundry_model: str
    foundry_api_key: str


TenantKey = Tuple[str, str]


def _load_json_from_env_var(var_name: str) -> Dict:
    raw = os.environ.get(var_name)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"{var_name} is set but is not valid JSON: {e}") from e


def _load_json_from_file(path: Path) -> Dict:
    if not path.is_file():
        raise RuntimeError(f"TENANT_CONFIG_FILE points to missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to parse tenant config file {path}: {e}") from e


def _flatten_tenant_config(raw: Dict) -> Dict[TenantKey, TenantConfig]:
    """
    Flatten a nested tenant config JSON object into a mapping of
    (logical_api_key, logical_model) -> TenantConfig.

    Expected shape (either of):
      {
        "tenantA": {
          "models": {
            "model-1": {
              "foundry_resource": "...",
              "foundry_model": "...",
              "foundry_api_key": "..."
            }
          }
        },
        "tenantB": { ... }
      }
    """
    tenants_obj = raw.get("tenants") if isinstance(raw.get("tenants"), dict) else raw
    if not isinstance(tenants_obj, dict):
        raise RuntimeError("Tenant config JSON must be an object mapping tenant IDs to model configs")

    mapping: Dict[TenantKey, TenantConfig] = {}
    for tenant_id, tenant_data in tenants_obj.items():
        if not isinstance(tenant_data, dict):
            continue
        models = tenant_data.get("models", {})
        if not isinstance(models, dict):
            continue
        for logical_model, cfg in models.items():
            if not isinstance(cfg, dict):
                continue
            foundry_resource = cfg.get("foundry_resource", "").strip()
            foundry_model = cfg.get("foundry_model", "").strip()
            foundry_api_key = cfg.get("foundry_api_key", "").strip()
            if not (tenant_id and logical_model and foundry_resource and foundry_model and foundry_api_key):
                raise RuntimeError(
                    f"Incomplete tenant config for tenant '{tenant_id}', model '{logical_model}'; "
                    "expected non-empty foundry_resource, foundry_model, foundry_api_key"
                )
            key: TenantKey = (tenant_id, logical_model)
            if key in mapping:
                raise RuntimeError(f"Duplicate tenant config entry for (tenant_id='{tenant_id}', model='{logical_model}')")
            mapping[key] = TenantConfig(
                tenant_id=tenant_id,
                logical_model=logical_model,
                foundry_resource=foundry_resource,
                foundry_model=foundry_model,
                foundry_api_key=foundry_api_key,
            )
    return mapping


def _load_tenant_mappings() -> Dict[TenantKey, TenantConfig]:
    """
    Load tenant mappings from environment and optional file.

    - TENANT_CONFIG_JSON: JSON string with tenant mapping structure.
    - TENANT_CONFIG_FILE: path to JSON file with the same structure.
    """
    merged_raw: Dict = {}

    env_obj = _load_json_from_env_var("TENANT_CONFIG_JSON")
    if env_obj:
        merged_raw.update(env_obj)

    file_var = os.environ.get("TENANT_CONFIG_FILE")
    if file_var:
        file_obj = _load_json_from_file(Path(file_var))
        # File entries override env entries on key collision
        merged_raw.update(file_obj)

    if not merged_raw:
        dlog("tenant_config_loaded", {"enabled": False, "reason": "no TENANT_CONFIG_JSON or TENANT_CONFIG_FILE set"})
        return {}

    mapping = _flatten_tenant_config(merged_raw)
    dlog(
        "tenant_config_loaded",
        {
            "enabled": True,
            "tenant_count": len({t.tenant_id for t in mapping.values()}),
            "mapping_count": len(mapping),
        },
    )
    return mapping


_TENANT_MAPPINGS: Dict[TenantKey, TenantConfig] = _load_tenant_mappings()


def multi_tenant_enabled() -> bool:
    """Return True if any tenant mappings are configured."""
    return bool(_TENANT_MAPPINGS)


def resolve_tenant(logical_api_key: str, logical_model: str) -> Optional[TenantConfig]:
    """
    Resolve (apiKey, model) into a TenantConfig using the loaded mappings.

    For now, this only implements exact match lookup:
      (logical_api_key, logical_model) -> TenantConfig

    Fallbacks (tenant-level defaults, global defaults) can be layered on
    later following the design decisions in PLAN.md.
    """
    if not _TENANT_MAPPINGS:
        return None

    key: TenantKey = (logical_api_key, logical_model)
    tenant = _TENANT_MAPPINGS.get(key)
    if tenant:
        dlog(
            "tenant_resolved",
            {
                "tenant_id": tenant.tenant_id,
                "logical_model": tenant.logical_model,
                "foundry_resource": tenant.foundry_resource,
                "foundry_model": tenant.foundry_model,
            },
        )
        return tenant

    dlog(
        "tenant_resolution_failed",
        {"logical_api_key": logical_api_key, "logical_model": logical_model},
    )
    return None

