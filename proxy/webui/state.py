from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from proxy.webui.auth import AdminAuthConfig, public_admin_config
from proxy.metrics import metrics as global_metrics, MetricsTracker
from proxy.admin_config import AdminConfigStore
from proxy.auth_tokens import TokenStore


@dataclass
class AdminEvent:
    ts: float
    title: str
    detail: str | None = None


class AdminEventLog:
    """In-memory ring buffer for recent admin events."""

    def __init__(self, max_events: int = 200, path: Optional[str] = None) -> None:
        self.max_events = max_events
        self.events: List[AdminEvent] = []
        self.path = path
        self._load()

    def add(self, title: str, detail: str | None = None) -> None:
        self.events.append(AdminEvent(ts=time.time(), title=title, detail=detail))
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]
        self._persist_last()

    def snapshot(self) -> List[Dict[str, Any]]:
        return [
            {"ts": e.ts, "title": e.title, "detail": e.detail}
            for e in reversed(self.events)
        ]

    def export_lines(self) -> str:
        """Return events as NDJSON."""
        lines = []
        for e in self.events:
            lines.append(json.dumps({"ts": e.ts, "title": e.title, "detail": e.detail}))
        return "\n".join(lines) + ("\n" if lines else "")

    # ---------- persistence helpers ----------
    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self.events.append(
                        AdminEvent(
                            ts=float(data.get("ts") or time.time()),
                            title=data.get("title") or "Event",
                            detail=data.get("detail"),
                        )
                    )
            self.events = self.events[-self.max_events :]
        except Exception:
            # best-effort; ignore corrupt logs
            self.events = []

    def _persist_last(self) -> None:
        if not self.path or not self.events:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a") as f:
                last = self.events[-1]
                f.write(json.dumps({"ts": last.ts, "title": last.title, "detail": last.detail}) + "\n")
        except Exception:
            # best-effort; avoid crashing admin UI
            return


@dataclass
class AdminRuntimeState:
    start_time: float
    admin_config_public: Dict[str, Any]
    metrics: MetricsTracker = global_metrics
    config_store: AdminConfigStore | None = None
    token_store: TokenStore | None = None
    events: AdminEventLog = field(default_factory=AdminEventLog)


def init_admin_state(
    config: AdminAuthConfig,
    config_store: AdminConfigStore | None = None,
    token_store: TokenStore | None = None,
    event_log_path: str | None = None,
) -> AdminRuntimeState:
    """Capture startup time and store a redacted admin config snapshot."""
    return AdminRuntimeState(
        start_time=time.time(),
        admin_config_public=public_admin_config(config),
        metrics=global_metrics,
        config_store=config_store,
        token_store=token_store,
        events=AdminEventLog(path=event_log_path),
    )
