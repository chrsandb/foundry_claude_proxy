from __future__ import annotations

import os
import time
import json
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Mapping
import secrets

import bcrypt

from proxy.config import dlog


TOKENS_SCHEMA_VERSION = 2


@dataclass
class TokenEntry:
    user: str
    hash: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    disabled: bool = False


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

        version = raw.get("version") or 1
        if version not in (1, TOKENS_SCHEMA_VERSION):
            dlog("proxy_token_load_skip", f"Incompatible token store version: {version}")
            return

        tokens_raw = raw.get("tokens") or {}
        for user, entry in tokens_raw.items():
            h = entry.get("hash")
            created_at = entry.get("created_at") or time.time()
            if not h:
                continue
            if version == 1:
                self.tokens[user] = TokenEntry(user=user, hash=h, created_at=float(created_at))
            else:
                self.tokens[user] = TokenEntry(
                    user=user,
                    hash=h,
                    email=entry.get("email"),
                    display_name=entry.get("display_name"),
                    created_at=float(created_at),
                    last_used=entry.get("last_used"),
                    disabled=bool(entry.get("disabled", False)),
                )

    def save(self) -> None:
        if not self.path:
            return
        payload = {
            "version": TOKENS_SCHEMA_VERSION,
            "tokens": {
                user: {
                    "hash": entry.hash,
                    "email": entry.email,
                    "display_name": entry.display_name,
                    "created_at": entry.created_at,
                    "last_used": entry.last_used,
                    "disabled": entry.disabled,
                }
                for user, entry in self.tokens.items()
            },
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

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def add_token(
        self,
        user: str,
        token: Optional[str] = None,
        *,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        disabled: bool = False,
    ) -> str:
        plain = token or self._generate_token()
        hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self.tokens[user] = TokenEntry(
            user=user,
            hash=hashed,
            email=email,
            display_name=display_name,
            created_at=time.time(),
            disabled=disabled,
        )
        self.save()
        return plain

    def reset_token(self, user: str, token: Optional[str] = None) -> Optional[str]:
        if user not in self.tokens:
            return None
        plain = token or self._generate_token()
        hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        entry = self.tokens[user]
        entry.hash = hashed
        entry.created_at = time.time()
        entry.last_used = None
        self.save()
        return plain

    def set_disabled(self, user: str, disabled: bool) -> bool:
        entry = self.tokens.get(user)
        if not entry:
            return False
        entry.disabled = disabled
        self.save()
        return True

    def update_metadata(self, user: str, *, email: Optional[str], display_name: Optional[str]) -> bool:
        entry = self.tokens.get(user)
        if not entry:
            return False
        if email is not None:
            entry.email = email
        if display_name is not None:
            entry.display_name = display_name
        self.save()
        return True

    def delete_token(self, user: str) -> bool:
        if user in self.tokens:
            del self.tokens[user]
            self.save()
            return True
        return False

    def validate(self, token: str) -> Optional[str]:
        for user, entry in self.tokens.items():
            try:
                if entry.disabled:
                    continue
                if bcrypt.checkpw(token.encode("utf-8"), entry.hash.encode("utf-8")):
                    entry.last_used = time.time()
                    return user
            except Exception:
                continue
        return None

    def list_public(self) -> Dict[str, Dict]:
        return {
            user: {
                "created_at": entry.created_at,
                "email": entry.email,
                "display_name": entry.display_name,
                "last_used": entry.last_used,
                "disabled": entry.disabled,
            }
            for user, entry in self.tokens.items()
        }

    def get(self, user: str) -> Optional[TokenEntry]:
        return self.tokens.get(user)


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
