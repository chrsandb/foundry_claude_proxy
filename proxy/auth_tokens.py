from __future__ import annotations

import os
import time
import json
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Mapping

import bcrypt

from proxy.config import dlog


TOKENS_SCHEMA_VERSION = 1


@dataclass
class TokenEntry:
    user: str
    hash: str
    created_at: float = field(default_factory=time.time)


class TokenStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.tokens: Dict[str, TokenEntry] = {}

    def load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                raw = json.load(f)
        except Exception as e:
            dlog("proxy_token_load_error", f"Could not read token store: {e}")
            return

        if raw.get("version") != TOKENS_SCHEMA_VERSION:
            dlog("proxy_token_load_skip", f"Incompatible token store version: {raw.get('version')}")
            return

        tokens_raw = raw.get("tokens") or {}
        for user, entry in tokens_raw.items():
            h = entry.get("hash")
            created_at = entry.get("created_at") or time.time()
            if not h:
                continue
            self.tokens[user] = TokenEntry(user=user, hash=h, created_at=float(created_at))

    def save(self) -> None:
        if not self.path:
            return
        payload = {
            "version": TOKENS_SCHEMA_VERSION,
            "tokens": {user: {"hash": entry.hash, "created_at": entry.created_at} for user, entry in self.tokens.items()},
        }
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(self.path) or ".") as tmp:
                json.dump(payload, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self.path)
        except Exception as e:
            dlog("proxy_token_save_error", str(e))

    def add_token(self, user: str, token: str) -> None:
        hashed = bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self.tokens[user] = TokenEntry(user=user, hash=hashed, created_at=time.time())
        self.save()

    def delete_token(self, user: str) -> bool:
        if user in self.tokens:
            del self.tokens[user]
            self.save()
            return True
        return False

    def validate(self, token: str) -> Optional[str]:
        for user, entry in self.tokens.items():
            try:
                if bcrypt.checkpw(token.encode("utf-8"), entry.hash.encode("utf-8")):
                    return user
            except Exception:
                continue
        return None

    def list_public(self) -> Dict[str, Dict]:
        return {
            user: {"created_at": entry.created_at}
            for user, entry in self.tokens.items()
        }


# Global proxy-auth configuration (set at startup)
proxy_auth_required: bool = False
token_store: Optional[TokenStore] = None


def configure_proxy_auth(store: Optional[TokenStore], required: bool) -> None:
    global proxy_auth_required, token_store
    proxy_auth_required = required
    token_store = store
    dlog(
        "proxy_auth_config",
        {"required": proxy_auth_required, "store_configured": bool(token_store and token_store.path)},
    )


def extract_and_validate_proxy_token(
    logical_model: Optional[str],
    headers: Mapping[str, str],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (clean_model, user_id) or raise ValueError if required and missing/invalid."""
    if not proxy_auth_required:
        return logical_model, None

    token = None
    hdr = headers.get("x-proxy-token") or headers.get("X-Proxy-Token")
    if hdr:
        token = hdr.strip()

    model_value = logical_model
    if not token and isinstance(logical_model, str) and ":" in logical_model:
        token, model_value = logical_model.split(":", 1)

    if not token:
        raise ValueError("Proxy auth required: no token provided.")

    if not token_store:
        raise ValueError("Proxy auth required but token store not configured.")

    user = token_store.validate(token)
    if not user:
        raise ValueError("Proxy auth token is invalid.")

    return model_value, user
