import os

from dotenv import load_dotenv
from fastapi import FastAPI

from proxy.routes_models import router as models_router
from proxy.routes_chat import router as chat_router
from proxy.routes_completions import router as completions_router
from proxy.routes_embeddings import router as embeddings_router
from proxy.routes_moderations import router as moderations_router
from proxy.webui.auth import load_admin_auth_config
from proxy.webui.routes import create_admin_router
from proxy.webui.state import init_admin_state
from proxy.config import dlog
from proxy.metrics import metrics
from proxy.admin_config import AdminConfigStore
from proxy.auth_tokens import TokenStore, configure_proxy_auth


load_dotenv()
app = FastAPI()
app.include_router(models_router)
app.include_router(chat_router)
app.include_router(completions_router)
app.include_router(embeddings_router)
app.include_router(moderations_router)

# Enable metrics persistence if configured.
metrics_file = os.environ.get("METRICS_FILE") or os.environ.get("PROXY_METRICS_FILE")
if metrics_file:
    metrics.configure_persistence(metrics_file)
    dlog("metrics_persistence_enabled", metrics_file)

# Optional admin config store (for safe config flags only).
admin_config_store: AdminConfigStore | None = None
admin_config_path = os.environ.get("ADMIN_CONFIG_FILE") or os.environ.get("PROXY_CONFIG_FILE")
if admin_config_path:
    admin_config_store = AdminConfigStore(path=admin_config_path)
    admin_config_store.load()
    dlog("admin_config_store_enabled", admin_config_path)

# Optional user auth token store and enforcement.
token_store: TokenStore | None = None
proxy_auth_required = os.environ.get("ENABLE_PROXY_AUTH") == "1" or os.environ.get("PROXY_REQUIRE_AUTH") == "1"
token_store_path = os.environ.get("PROXY_AUTH_FILE") or os.environ.get("PROXY_USER_FILE")
if token_store_path:
    token_store = TokenStore(path=token_store_path)
    token_store.load()
    dlog("proxy_token_store_enabled", token_store_path)

configure_proxy_auth(token_store, proxy_auth_required)

# Optionally mount /admin when explicitly enabled and configured.
_admin_config = load_admin_auth_config()
if _admin_config.enabled:
    _admin_state = init_admin_state(_admin_config, admin_config_store, token_store)
    app.include_router(create_admin_router(_admin_config, _admin_state))
else:
    if _admin_config.disabled_reason:
        dlog("admin_disabled", _admin_config.disabled_reason)


if __name__ == "__main__":
    # Convenience for local runs: python foundry_openai_proxy.py --proxy-debug
    import uvicorn
    import os

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "18000"))
    uvicorn.run("foundry_openai_proxy:app", host=host, port=port, reload=False)
