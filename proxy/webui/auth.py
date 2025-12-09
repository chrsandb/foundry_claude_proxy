from __future__ import annotations

import os
import hmac
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from proxy.config import dlog


security = HTTPBasic(auto_error=False)


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AdminAuthConfig:
    enabled: bool
    username: str
    password_hash: Optional[str]
    password_plain: Optional[str]
    allow_reset: bool
    allow_config_edit: bool
    allow_user_mgmt: bool
    disabled_reason: Optional[str] = None

    @property
    def auth_mode(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.password_hash:
            return "hash"
        if self.password_plain:
            return "password"
        return "unknown"


def load_admin_auth_config() -> AdminAuthConfig:
    """Read admin auth settings from env."""
    enabled = _truthy(os.environ.get("ENABLE_ADMIN") or os.environ.get("ADMIN_ENABLED"))
    username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
    password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    password_plain = os.environ.get("ADMIN_PASSWORD")
    allow_reset = _truthy(os.environ.get("ENABLE_ADMIN_RESET") or os.environ.get("ADMIN_ALLOW_RESET"))
    allow_config_edit = _truthy(os.environ.get("ENABLE_ADMIN_CONFIG_EDIT") or os.environ.get("ADMIN_ALLOW_CONFIG_EDIT"))
    allow_user_mgmt = _truthy(os.environ.get("ENABLE_ADMIN_USER_MGMT") or os.environ.get("ADMIN_ALLOW_USER_MGMT"))

    disabled_reason = None
    if enabled and not (password_hash or password_plain):
        disabled_reason = "Admin disabled: ENABLE_ADMIN set but no ADMIN_PASSWORD_HASH or ADMIN_PASSWORD provided."
        enabled = False

    cfg = AdminAuthConfig(
        enabled=enabled,
        username=username,
        password_hash=password_hash,
        password_plain=password_plain,
        allow_reset=allow_reset,
        allow_config_edit=allow_config_edit,
        allow_user_mgmt=allow_user_mgmt,
        disabled_reason=disabled_reason,
    )
    dlog(
        "admin_auth_config",
        {
            "enabled": cfg.enabled,
            "username": cfg.username,
            "auth_mode": cfg.auth_mode,
            "disabled_reason": cfg.disabled_reason,
        },
    )
    return cfg


def _verify_username(expected: str, provided: str) -> bool:
    return hmac.compare_digest(expected or "", provided or "")


def _verify_password(config: AdminAuthConfig, provided: str) -> bool:
    if config.password_hash:
        try:
            return bcrypt.checkpw(provided.encode("utf-8"), config.password_hash.encode("utf-8"))
        except Exception:
            return False
    if config.password_plain:
        return hmac.compare_digest(config.password_plain, provided or "")
    return False


def require_admin(config: AdminAuthConfig) -> Callable[[HTTPBasicCredentials], Dict[str, Any]]:
    def dependency(credentials: HTTPBasicCredentials = Depends(security)) -> Dict[str, Any]:
        if not config.enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        if credentials is None or credentials.username is None or credentials.password is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Basic"},
            )

        if not _verify_username(config.username, credentials.username) or not _verify_password(config, credentials.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

        return {"username": config.username, "auth_mode": config.auth_mode}

    return dependency


def public_admin_config(config: AdminAuthConfig) -> Dict[str, Any]:
    """Return a redacted view suitable for admin status endpoints."""
    return {
        "enabled": config.enabled,
        "username": config.username if config.enabled else None,
        "auth_mode": config.auth_mode,
        "has_password_hash": bool(config.password_hash),
        "has_password_plain": bool(config.password_plain),
        "allow_reset": config.allow_reset,
        "allow_config_edit": config.allow_config_edit,
        "allow_user_mgmt": config.allow_user_mgmt,
        "disabled_reason": config.disabled_reason,
    }
