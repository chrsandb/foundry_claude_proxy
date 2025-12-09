from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Any

from proxy.webui.auth import AdminAuthConfig, public_admin_config
from proxy.metrics import metrics as global_metrics, MetricsTracker
from proxy.admin_config import AdminConfigStore
from proxy.auth_tokens import TokenStore


@dataclass
class AdminRuntimeState:
    start_time: float
    admin_config_public: Dict[str, Any]
    metrics: MetricsTracker = global_metrics
    config_store: AdminConfigStore | None = None
    token_store: TokenStore | None = None


def init_admin_state(
    config: AdminAuthConfig,
    config_store: AdminConfigStore | None = None,
    token_store: TokenStore | None = None,
) -> AdminRuntimeState:
    """Capture startup time and store a redacted admin config snapshot."""
    return AdminRuntimeState(
        start_time=time.time(),
        admin_config_public=public_admin_config(config),
        metrics=global_metrics,
        config_store=config_store,
        token_store=token_store,
    )
