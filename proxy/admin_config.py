from __future__ import annotations

import json
import os
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from proxy.config import dlog


CONFIG_SCHEMA_VERSION = 1


def _default_config() -> Dict[str, Any]:
    return {"default_model": None, "default_resource": None, "flags": {}}


@dataclass
class AdminConfigStore:
    path: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=_default_config)
    loaded_at: float = field(default_factory=time.time)

    def load(self) -> None:
        """Load config from file if present and schema-compatible."""
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                raw = json.load(f)
        except Exception as e:
            dlog("admin_config_load_error", f"Could not read config: {e}")
            return

        if raw.get("version") != CONFIG_SCHEMA_VERSION:
            dlog("admin_config_load_skip", f"Incompatible config version: {raw.get('version')}")
            return
        data = raw.get("data")
        if not isinstance(data, dict):
            dlog("admin_config_load_skip", "Config data not a dict")
            return

        self.data = _default_config()
        self.data.update({
            "default_model": data.get("default_model"),
            "default_resource": data.get("default_resource"),
            "flags": data.get("flags") or {},
        })
        self.loaded_at = time.time()

    def save(self) -> None:
        if not self.path:
            return
        payload = {"version": CONFIG_SCHEMA_VERSION, "data": self.data}
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(self.path) or ".") as tmp:
                json.dump(payload, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self.path)
        except Exception as e:
            dlog("admin_config_save_error", str(e))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": CONFIG_SCHEMA_VERSION,
            "data": deepcopy(self.data),
            "path": self.path,
            "loaded_at": self.loaded_at,
        }

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update allowed fields only and persist if a path is set."""
        if "default_model" in payload:
            self.data["default_model"] = payload.get("default_model")
        if "default_resource" in payload:
            self.data["default_resource"] = payload.get("default_resource")
        if "flags" in payload:
            flags = payload.get("flags")
            if isinstance(flags, dict):
                self.data["flags"] = flags
        self.save()
        return self.snapshot()
