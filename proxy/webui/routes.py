from __future__ import annotations

import time
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from proxy.webui.auth import AdminAuthConfig, require_admin, public_admin_config
from proxy.webui.state import AdminRuntimeState
from proxy.webui.templates import ADMIN_INDEX_HTML
from proxy.metrics import metrics


def _metrics_summary(state: AdminRuntimeState) -> Dict[str, Any]:
    snap = metrics.snapshot()
    routes = snap.get("routes", {})
    start_time = snap.get("start_time") or state.start_time
    total_requests = sum(v.get("count", 0) for v in routes.values())
    total_errors = sum(v.get("error_count", 0) for v in routes.values())

    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    latency_summary = {"avg_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "count": 0}
    latency_sum = 0.0
    latency_count = 0
    for data in routes.values():
        usage = data.get("usage") or {}
        usage_totals["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_totals["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_totals["total_tokens"] += usage.get("total_tokens", 0)
        lat = data.get("latency_ms") or {}
        count = lat.get("count") or data.get("count") or 0
        if count and lat.get("avg") is not None:
            latency_sum += float(lat.get("avg", 0)) * float(count)
            latency_count += float(count)
        latency_summary["p95_ms"] = max(latency_summary["p95_ms"], float(lat.get("p95") or 0))
        latency_summary["p99_ms"] = max(latency_summary["p99_ms"], float(lat.get("p99") or 0))
    if latency_count > 0:
        latency_summary["avg_ms"] = latency_sum / latency_count
        latency_summary["count"] = int(latency_count)

    return {
        "start_time": start_time,
        "uptime_seconds": int(time.time() - start_time),
        "total_requests": total_requests,
        "total_errors": total_errors,
        "routes": routes,
        "usage_totals": usage_totals,
        "latency": latency_summary,
    }


def _require_user_mgmt(config: AdminAuthConfig, state: AdminRuntimeState) -> None:
    if not config.allow_user_mgmt:
        raise HTTPException(status_code=403, detail="User management not enabled.")
    if not state.token_store:
        raise HTTPException(status_code=500, detail="Token store not configured.")


def _config_snapshot(state: AdminRuntimeState) -> Dict[str, Any]:
    if not state.config_store:
        return {"config": None, "message": "Admin config store not configured."}
    return state.config_store.snapshot()


def create_admin_router(config: AdminAuthConfig, state: AdminRuntimeState) -> APIRouter:
    """Create the /admin router with HTML dashboard plus JSON admin APIs."""
    router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin(config))])

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def admin_index() -> HTMLResponse:
        return HTMLResponse(content=ADMIN_INDEX_HTML)

    @router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def admin_dashboard() -> HTMLResponse:
        return HTMLResponse(content=ADMIN_INDEX_HTML)

    @router.get("/health")
    async def admin_health():
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "config": public_admin_config(config),
        }

    @router.get("/api/summary")
    async def admin_summary():
        users_public = state.token_store.list_public() if state.token_store else {}
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "admin_config": public_admin_config(config),
            "metrics": _metrics_summary(state),
            "user_count": len(users_public),
            "disabled_users": sum(1 for u in users_public.values() if u.get("disabled")),
            "config_store": state.config_store.snapshot() if state.config_store else None,
        }

    @router.get("/config")
    async def admin_config_get():
        return _config_snapshot(state)

    @router.get("/api/config")
    async def admin_config_get_api():
        return _config_snapshot(state)

    @router.post("/config")
    async def admin_config_update(payload: dict):
        if not config.allow_config_edit:
            raise HTTPException(status_code=403, detail="Config editing not enabled.")
        if not state.config_store:
            raise HTTPException(status_code=500, detail="Admin config store not configured.")
        updated = state.config_store.update(payload or {})
        state.events.add("Config updated", f"Fields: {', '.join((payload or {}).keys())}")
        return {"status": "ok", "config": updated}

    @router.post("/api/config")
    async def admin_config_update_api(payload: dict):
        return await admin_config_update(payload)  # type: ignore

    @router.get("/users")
    async def admin_users_get():
        _require_user_mgmt(config, state)
        return {"status": "ok", "users": state.token_store.list_public() if state.token_store else {}}

    @router.get("/users/{user}")
    async def admin_user_detail(user: str):
        _require_user_mgmt(config, state)
        entry = state.token_store.get(user) if state.token_store else None
        if not entry:
            raise HTTPException(status_code=404, detail="User not found.")
        return {
            "status": "ok",
            "user": user,
            "data": {
                "email": entry.email,
                "display_name": entry.display_name,
                "created_at": entry.created_at,
                "last_used": entry.last_used,
                "disabled": entry.disabled,
            },
        }

    @router.post("/users")
    async def admin_users_add(payload: dict):
        _require_user_mgmt(config, state)
        user = (payload or {}).get("user") or (payload or {}).get("id")
        token = (payload or {}).get("token")
        email = (payload or {}).get("email")
        display_name = (payload or {}).get("display_name")
        disabled = bool((payload or {}).get("disabled", False))
        if not user:
            raise HTTPException(status_code=400, detail="Field 'user' is required.")
        if not state.token_store:
            raise HTTPException(status_code=500, detail="Token store not configured.")
        created_token = state.token_store.add_token(
            user,
            token=token,
            email=email,
            display_name=display_name,
            disabled=disabled,
        )
        state.events.add("User created", f"{user} ({email or 'no email'})")
        return {"status": "ok", "user": user, "token": created_token, "disabled": disabled}

    @router.patch("/users/{user}")
    async def admin_users_update(user: str, payload: dict):
        _require_user_mgmt(config, state)
        email = (payload or {}).get("email")
        display_name = (payload or {}).get("display_name")
        if not state.token_store:
            raise HTTPException(status_code=500, detail="Token store not configured.")
        updated = state.token_store.update_metadata(user, email=email, display_name=display_name)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found.")
        state.events.add("User updated", f"{user} metadata")
        return {"status": "ok", "user": user}

    @router.post("/users/{user}/disable")
    async def admin_users_disable(user: str):
        _require_user_mgmt(config, state)
        if not state.token_store or not state.token_store.set_disabled(user, True):
            raise HTTPException(status_code=404, detail="User not found.")
        state.events.add("User disabled", user)
        return {"status": "ok", "user": user, "disabled": True}

    @router.post("/users/{user}/enable")
    async def admin_users_enable(user: str):
        _require_user_mgmt(config, state)
        if not state.token_store or not state.token_store.set_disabled(user, False):
            raise HTTPException(status_code=404, detail="User not found.")
        state.events.add("User enabled", user)
        return {"status": "ok", "user": user, "disabled": False}

    @router.post("/users/{user}/reset")
    async def admin_users_reset(user: str, payload: dict | None = None):
        _require_user_mgmt(config, state)
        new_token = state.token_store.reset_token(user, (payload or {}).get("token")) if state.token_store else None
        if not new_token:
            raise HTTPException(status_code=404, detail="User not found.")
        state.events.add("User token reset", user)
        return {"status": "ok", "user": user, "token": new_token}

    @router.delete("/users/{user}")
    async def admin_users_delete(user: str):
        _require_user_mgmt(config, state)
        removed = state.token_store.delete_token(user) if state.token_store else False
        if not removed:
            raise HTTPException(status_code=404, detail="User not found.")
        state.events.add("User deleted", user)
        return {"status": "ok", "user": user}

    @router.get("/metrics")
    async def admin_metrics():
        return _metrics_summary(state)

    @router.get("/api/metrics")
    async def admin_metrics_api():
        return _metrics_summary(state)

    @router.post("/metrics/reset")
    async def admin_metrics_reset():
        if not config.allow_reset:
            raise HTTPException(status_code=403, detail="Metrics reset not enabled.")
        metrics.reset()
        state.events.add("Metrics reset", f"By {config.username}")
        return {"status": "ok", "reset_at": int(time.time())}

    @router.get("/logs")
    async def admin_logs():
        return {
            "status": "ok",
            "events": state.events.snapshot(),
            "message": "Showing recent admin-side events.",
            "persisted": bool(state.events.path),
            "path": state.events.path,
        }

    @router.get("/logs/download", response_class=PlainTextResponse)
    async def admin_logs_download():
        if state.events.path and os.path.exists(state.events.path):
            try:
                with open(state.events.path, "r") as f:
                    return PlainTextResponse(content=f.read(), media_type="text/plain")
            except Exception:
                # fallback to in-memory
                pass
        return PlainTextResponse(content=state.events.export_lines(), media_type="text/plain")

    @router.get("/overview")
    async def admin_overview():
        users_public = state.token_store.list_public() if state.token_store else {}
        summary = _metrics_summary(state)
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "total_requests": summary["total_requests"],
            "total_errors": summary["total_errors"],
            "routes": summary["routes"],
            "config": public_admin_config(config),
            "admin_config": state.config_store.snapshot() if state.config_store else None,
            "tokens": users_public,
        }

    return router
