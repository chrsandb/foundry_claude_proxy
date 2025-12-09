from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from proxy.webui.auth import AdminAuthConfig, require_admin, public_admin_config
from proxy.webui.state import AdminRuntimeState
from proxy.metrics import metrics
from proxy.admin_config import AdminConfigStore
from proxy.auth_tokens import TokenStore


def create_admin_router(config: AdminAuthConfig, state: AdminRuntimeState) -> APIRouter:
    """Create the /admin router with baseline auth and health endpoints."""
    router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin(config))])

    @router.get("/")
    async def admin_root():
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "config": public_admin_config(config),
        }

    @router.get("/health")
    async def admin_health():
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "config": public_admin_config(config),
        }

    @router.get("/config")
    async def admin_config_get():
        if not state.config_store:
            return {"config": None, "message": "Admin config store not configured."}
        return state.config_store.snapshot()

    @router.post("/config")
    async def admin_config_update(payload: dict):
        if not config.allow_config_edit:
            return {"status": "disabled", "message": "Config editing not enabled."}
        if not state.config_store:
            return {"status": "error", "message": "Admin config store not configured."}
        updated = state.config_store.update(payload or {})
        return {"status": "ok", "config": updated}

    @router.get("/users")
    async def admin_users_get():
        if not config.allow_user_mgmt:
            return {"status": "disabled", "message": "User management not enabled."}
        if not state.token_store:
            return {"status": "error", "message": "Token store not configured."}
        return {"status": "ok", "users": state.token_store.list_public()}

    @router.post("/users")
    async def admin_users_add(payload: dict):
        if not config.allow_user_mgmt:
            return {"status": "disabled", "message": "User management not enabled."}
        if not state.token_store:
            return {"status": "error", "message": "Token store not configured."}
        user = payload.get("user")
        token = payload.get("token")
        if not user or not token:
            return {"status": "error", "message": "Both 'user' and 'token' are required."}
        state.token_store.add_token(user, token)
        return {"status": "ok", "user": user}

    @router.delete("/users/{user}")
    async def admin_users_delete(user: str):
        if not config.allow_user_mgmt:
            return {"status": "disabled", "message": "User management not enabled."}
        if not state.token_store:
            return {"status": "error", "message": "Token store not configured."}
        removed = state.token_store.delete_token(user)
        if not removed:
            return {"status": "error", "message": "User not found."}
        return {"status": "ok", "user": user}

    @router.get("/metrics")
    async def admin_metrics():
        return metrics.snapshot()

    @router.post("/metrics/reset")
    async def admin_metrics_reset():
        if not config.allow_reset:
            return {"status": "disabled", "message": "Metrics reset not enabled"}
        metrics.reset()
        return {"status": "ok", "reset_at": int(time.time())}

    @router.get("/overview")
    async def admin_overview():
        snap = metrics.snapshot()
        routes = snap.get("routes", {})
        total_requests = sum(v.get("count", 0) for v in routes.values())
        total_errors = sum(v.get("error_count", 0) for v in routes.values())
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - state.start_time),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "routes": routes,
            "config": public_admin_config(config),
            "admin_config": state.config_store.snapshot() if state.config_store else None,
            "tokens": state.token_store.list_public() if state.token_store else None,
        }

    @router.get("/dashboard", response_class=None)
    async def admin_dashboard():
        snap = metrics.snapshot()
        routes = snap.get("routes", {})
        total_requests = sum(v.get("count", 0) for v in routes.values())
        total_errors = sum(v.get("error_count", 0) for v in routes.values())
        html_rows = []
        for route, data in routes.items():
            html_rows.append(
                f"<tr><td>{route}</td><td>{data.get('count',0)}</td><td>{data.get('error_count',0)}</td>"
                f"<td>{data.get('usage',{}).get('prompt_tokens',0)}</td>"
                f"<td>{data.get('usage',{}).get('completion_tokens',0)}</td>"
                f"<td>{data.get('usage',{}).get('total_tokens',0)}</td></tr>"
            )
        body = f"""
        <html>
            <head><title>Proxy Admin</title></head>
            <body>
                <h1>Proxy Admin</h1>
                <p>Status: ok</p>
                <p>Uptime (s): {int(time.time() - state.start_time)}</p>
                <p>Total requests: {total_requests} | Total errors: {total_errors}</p>
                <table border="1" cellpadding="4" cellspacing="0">
                    <thead><tr><th>Route</th><th>Count</th><th>Errors</th><th>Prompt</th><th>Completion</th><th>Total</th></tr></thead>
                    <tbody>{"".join(html_rows) or "<tr><td colspan='6'>No data</td></tr>"}</tbody>
                </table>
            </body>
        </html>
        """
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=body)

    return router
