from __future__ import annotations

import hmac
import os
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from thinkgate.controller import decide


@dataclass(frozen=True)
class AuthContext:
    customer_id: str
    sandbox: bool = False


class PilotGateway:
    """Small production gateway for ThinkGate pilots.

    Authentication and rate limiting remain in-process. Usage metering is
    persisted to SQLite when THINKGATE_USAGE_DB_PATH is configured; otherwise
    it falls back to in-memory counters for local development and tests.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._usage: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "requests": 0,
                "continue": 0,
                "stop": 0,
                "estimated_avoided_cost": 0.0,
            }
        )
        self._request_times: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _configured_keys() -> dict[str, str]:
        raw = os.environ.get("THINKGATE_CUSTOMER_KEYS", "").strip()
        if not raw:
            return {}
        result: dict[str, str] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            customer_id, key = entry.split(":", 1)
            customer_id = customer_id.strip()
            key = key.strip()
            if customer_id and key:
                result[customer_id] = key
        return result

    @staticmethod
    def _db_path() -> str | None:
        value = os.environ.get("THINKGATE_USAGE_DB_PATH", "").strip()
        return value or None

    def _ensure_db(self, db_path: str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage (
                    customer_id TEXT PRIMARY KEY,
                    requests INTEGER NOT NULL DEFAULT 0,
                    continue_count INTEGER NOT NULL DEFAULT 0,
                    stop_count INTEGER NOT NULL DEFAULT 0,
                    estimated_avoided_cost REAL NOT NULL DEFAULT 0.0,
                    updated_at INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def _record_usage(
        self,
        *,
        customer_id: str,
        decision: str,
        estimated_avoided_cost: float,
    ) -> None:
        db_path = self._db_path()
        if not db_path:
            with self._lock:
                row = self._usage[customer_id]
                row["requests"] += 1
                row["continue" if decision == "CONTINUE" else "stop"] += 1
                row["estimated_avoided_cost"] += estimated_avoided_cost
            return

        self._ensure_db(db_path)
        continue_inc = 1 if decision == "CONTINUE" else 0
        stop_inc = 1 if decision == "STOP" else 0
        with self._lock:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                conn.execute(
                    """
                    INSERT INTO usage (
                        customer_id,
                        requests,
                        continue_count,
                        stop_count,
                        estimated_avoided_cost,
                        updated_at
                    )
                    VALUES (?, 1, ?, ?, ?, ?)
                    ON CONFLICT(customer_id) DO UPDATE SET
                        requests = requests + 1,
                        continue_count = continue_count + excluded.continue_count,
                        stop_count = stop_count + excluded.stop_count,
                        estimated_avoided_cost = (
                            estimated_avoided_cost + excluded.estimated_avoided_cost
                        ),
                        updated_at = excluded.updated_at
                    """,
                    (
                        customer_id,
                        continue_inc,
                        stop_inc,
                        estimated_avoided_cost,
                        int(time.time()),
                    ),
                )
                conn.commit()

    def _read_usage(self, customer_id: str) -> tuple[dict[str, float], str]:
        db_path = self._db_path()
        if not db_path:
            with self._lock:
                return dict(self._usage[customer_id]), "in_memory_pilot_only"

        self._ensure_db(db_path)
        with self._lock:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                row = conn.execute(
                    """
                    SELECT requests, continue_count, stop_count, estimated_avoided_cost
                    FROM usage
                    WHERE customer_id = ?
                    """,
                    (customer_id,),
                ).fetchone()

        if row is None:
            return {
                "requests": 0,
                "continue": 0,
                "stop": 0,
                "estimated_avoided_cost": 0.0,
            }, "sqlite_persistent"

        return {
            "requests": int(row[0]),
            "continue": int(row[1]),
            "stop": int(row[2]),
            "estimated_avoided_cost": float(row[3]),
        }, "sqlite_persistent"

    def authenticate(self, supplied_key: str | None) -> AuthContext:
        configured = self._configured_keys()
        if not configured:
            return AuthContext(customer_id="sandbox", sandbox=True)
        if not supplied_key:
            raise PermissionError("missing X-ThinkGate-Key")
        for customer_id, expected in configured.items():
            if hmac.compare_digest(supplied_key, expected):
                return AuthContext(customer_id=customer_id, sandbox=False)
        raise PermissionError("invalid X-ThinkGate-Key")

    def enforce_rate_limit(self, customer_id: str) -> None:
        limit = max(1, int(os.environ.get("THINKGATE_RATE_LIMIT_PER_MINUTE", "120")))
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            bucket = self._request_times[customer_id]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise RuntimeError("rate limit exceeded")
            bucket.append(now)

    def make_decision(
        self,
        *,
        customer_id: str,
        predicted_gain: float,
        next_step_cost: float,
        margin: float,
        step_index: int,
        max_steps: int,
    ) -> dict:
        if step_index < 1:
            raise ValueError("step_index must be >= 1")
        if max_steps < step_index:
            raise ValueError("max_steps must be >= step_index")

        if step_index >= max_steps:
            decision = "STOP"
            reason = "max_steps_reached"
            net_value = predicted_gain - next_step_cost - margin
        else:
            decision = decide(predicted_gain, next_step_cost, margin)
            net_value = predicted_gain - next_step_cost - margin
            reason = (
                "expected_gain_exceeds_cost"
                if decision == "CONTINUE"
                else "expected_gain_not_worth_cost"
            )

        remaining_after_current = max(0, max_steps - step_index)
        estimated_avoided_cost = (
            next_step_cost * remaining_after_current if decision == "STOP" else 0.0
        )

        self._record_usage(
            customer_id=customer_id,
            decision=decision,
            estimated_avoided_cost=estimated_avoided_cost,
        )

        return {
            "decision": decision,
            "reason": reason,
            "net_value": round(net_value, 8),
            "estimated_avoided_cost": round(estimated_avoided_cost, 8),
            "policy": "gain_minus_cost_v1",
        }

    def usage(self, customer_id: str) -> dict:
        row, persistence = self._read_usage(customer_id)
        requests = int(row["requests"])
        stop = int(row["stop"])
        return {
            "customer_id": customer_id,
            "requests": requests,
            "continue": int(row["continue"]),
            "stop": stop,
            "stop_rate": round(stop / requests, 6) if requests else 0.0,
            "estimated_avoided_cost": round(float(row["estimated_avoided_cost"]), 8),
            "persistence": persistence,
        }


gateway = PilotGateway()
