from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, Optional

from proxy.config import dlog


def _now() -> float:
    return time.time()


def _hash_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"key:{digest}"


def derive_user_id(logical_api_key: Optional[str], explicit_user: Optional[str]) -> str:
    """Choose a user identifier without storing raw API keys."""
    if explicit_user:
        return str(explicit_user)
    if logical_api_key:
        return _hash_token(logical_api_key)
    return "unknown"


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: Dict) -> None:
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)


@dataclass
class RouteMetrics:
    count: int = 0
    error_count: int = 0
    last_seen: float = field(default_factory=_now)
    usage: TokenUsage = field(default_factory=TokenUsage)
    by_model: Dict[str, TokenUsage] = field(default_factory=dict)
    by_resource: Dict[str, TokenUsage] = field(default_factory=dict)
    by_user: Dict[str, TokenUsage] = field(default_factory=dict)
    durations_ms: list[float] = field(default_factory=list)
    durations_sum_ms: float = 0.0

    def to_dict(self) -> Dict:
        def usage_to_dict(u: TokenUsage) -> Dict:
            return {
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens,
            }

        return {
            "count": self.count,
            "error_count": self.error_count,
            "last_seen": self.last_seen,
            "usage": usage_to_dict(self.usage),
            "by_model": {k: usage_to_dict(v) for k, v in self.by_model.items()},
            "by_resource": {k: usage_to_dict(v) for k, v in self.by_resource.items()},
            "by_user": {k: usage_to_dict(v) for k, v in self.by_user.items()},
            "latency_ms": self._latency_snapshot(),
        }

    def _latency_snapshot(self) -> Dict:
        if not self.durations_ms:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
        sorted_vals = sorted(self.durations_ms)
        n = len(sorted_vals)

        def pct(p: float) -> float:
            if n == 1:
                return sorted_vals[0]
            idx = min(n - 1, int(round(p * (n - 1))))
            return sorted_vals[idx]

        avg = self.durations_sum_ms / n if n else 0.0
        return {"avg": avg, "p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "count": n}


METRICS_SCHEMA_VERSION = 1
MAX_LATENCY_SAMPLES = 200


class MetricsTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = _now()
        self._routes: Dict[str, RouteMetrics] = {}
        self._persist_path: Optional[str] = None

    @property
    def start_time(self) -> float:
        return self._start_time

    def configure_persistence(self, path: str) -> None:
        """Enable persistence to a JSON file; loads existing data if compatible."""
        self._persist_path = path
        self._load_from_file()

    def reset(self) -> None:
        with self._lock:
            self._routes = {}
            self._start_time = _now()
            self._persist_locked()

    def record(
        self,
        *,
        route: str,
        model: Optional[str],
        resource: Optional[str],
        user_id: str,
        usage: Dict,
        error: bool = False,
        duration_ms: Optional[float] = None,
    ) -> None:
        with self._lock:
            metrics = self._routes.setdefault(route, RouteMetrics())
            metrics.count += 1
            if error:
                metrics.error_count += 1
            metrics.last_seen = _now()
            metrics.usage.add(usage)
            if duration_ms is not None:
                metrics.durations_ms.append(float(duration_ms))
                metrics.durations_sum_ms += float(duration_ms)
                if len(metrics.durations_ms) > MAX_LATENCY_SAMPLES:
                    removed = metrics.durations_ms.pop(0)
                    metrics.durations_sum_ms -= removed

            model_key = model or "unknown-model"
            resource_key = resource or "unknown-resource"

            metrics.by_model.setdefault(model_key, TokenUsage()).add(usage)
            metrics.by_resource.setdefault(resource_key, TokenUsage()).add(usage)
            metrics.by_user.setdefault(user_id or "unknown", TokenUsage()).add(usage)
            self._persist_locked()

    def snapshot(self) -> Dict:
        with self._lock:
            data = {route: m.to_dict() for route, m in self._routes.items()}
            start = self._start_time
        return {"start_time": start, "routes": deepcopy(data)}

    # ---------- Persistence helpers ----------
    def _persist_locked(self) -> None:
        if not self._persist_path:
            return
        payload = {
            "version": METRICS_SCHEMA_VERSION,
            "start_time": self._start_time,
            "routes": {route: m.to_dict() for route, m in self._routes.items()},
        }
        try:
            os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
            with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(self._persist_path) or ".") as tmp:
                json.dump(payload, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self._persist_path)
        except Exception as e:
            dlog("metrics_persist_error", str(e))

    def _load_from_file(self) -> None:
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            dlog("metrics_load_error", f"Could not read metrics file: {e}")
            return

        if data.get("version") != METRICS_SCHEMA_VERSION:
            dlog("metrics_load_skipped", f"Incompatible metrics version: {data.get('version')}")
            return

        start_time = data.get("start_time") or _now()
        routes_raw = data.get("routes") or {}

        with self._lock:
            self._start_time = float(start_time)
            self._routes = {}
            for route, metrics_dict in routes_raw.items():
                rm = RouteMetrics()
                rm.count = int(metrics_dict.get("count") or 0)
                rm.error_count = int(metrics_dict.get("error_count") or 0)
                rm.last_seen = float(metrics_dict.get("last_seen") or _now())

                def fill_usage(target: TokenUsage, src: Dict) -> None:
                    target.prompt_tokens = int(src.get("prompt_tokens") or 0)
                    target.completion_tokens = int(src.get("completion_tokens") or 0)
                    target.total_tokens = int(src.get("total_tokens") or 0)

                fill_usage(rm.usage, metrics_dict.get("usage") or {})

                for key, val in (metrics_dict.get("by_model") or {}).items():
                    tu = TokenUsage()
                    fill_usage(tu, val or {})
                    rm.by_model[key] = tu
                for key, val in (metrics_dict.get("by_resource") or {}).items():
                    tu = TokenUsage()
                    fill_usage(tu, val or {})
                    rm.by_resource[key] = tu
                for key, val in (metrics_dict.get("by_user") or {}).items():
                    tu = TokenUsage()
                    fill_usage(tu, val or {})
                    rm.by_user[key] = tu

                self._routes[route] = rm


metrics = MetricsTracker()

ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
