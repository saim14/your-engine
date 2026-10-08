from __future__ import annotations

import hashlib
import hmac
import os
import secrets
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
    """Production gateway for ThinkGate pilots.

    Customer authentication supports persistent provisioned keys plus the
    legacy THINKGATE_CUSTOMER_KEYS environment variable. Metering is persisted
    to SQLite when THINKGATE_USAGE_DB_PATH is configured; otherwise tests and
    local development use in-memory counters.
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

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    estimated_avoided_cost REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_usage_events_customer_time
                ON usage_events(customer_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    api_key_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def revoke_customer(self, customer_id: str) -> dict:
        customer_id = customer_id.strip()
        if not customer_id:
            raise ValueError("customer_id is required")
        db_path = self._db_path()
        if not db_path:
            raise RuntimeError("persistent database is required for revocation")

        self._ensure_db(db_path)
        with self._lock:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                result = conn.execute(
                    """
                    UPDATE customers
                    SET status = 'revoked'
                    WHERE customer_id = ? AND status = 'active'
                    """,
                    (customer_id,),
                )
                conn.commit()
        if result.rowcount == 0:
            raise ValueError("active customer_id not found")
        return {"customer_id": customer_id, "status": "revoked"}

    def provision_customer(self, customer_id: str) -> dict:
        customer_id = customer_id.strip()
        if not customer_id:
            raise ValueError("customer_id is required")
        if len(customer_id) > 80:
            raise ValueError("customer_id must be <= 80 characters")
        db_path = self._db_path()
        if not db_path:
            raise RuntimeError("persistent database is required for provisioning")

        self._ensure_db(db_path)
        api_key = "tg_" + secrets.token_urlsafe(32)
        key_hash = self._hash_key(api_key)
        now = int(time.time())
        with self._lock:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                existing = conn.execute(
                    "SELECT 1 FROM customers WHERE customer_id = ?",
                    (customer_id,),
                ).fetchone()
                if existing:
                    raise ValueError("customer_id already exists")
                conn.execute(
                    """
                    INSERT INTO customers(customer_id, api_key_hash, status, created_at)
                    VALUES (?, ?, 'active', ?)
                    """,
                    (customer_id, key_hash, now),
                )
                conn.commit()
        return {
            "customer_id": customer_id,
            "api_key": api_key,
            "created_at": now,
        }

    def _persistent_customer_for_key(self, supplied_key: str) -> str | None:
        db_path = self._db_path()
        if not db_path:
            return None
        self._ensure_db(db_path)
        key_hash = self._hash_key(supplied_key)
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            row = conn.execute(
                """
                SELECT customer_id
                FROM customers
                WHERE api_key_hash = ? AND status = 'active'
                """,
                (key_hash,),
            ).fetchone()
        return str(row[0]) if row else None

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
        now = int(time.time())
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
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO usage_events(
                        customer_id,
                        created_at,
                        decision,
                        estimated_avoided_cost
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (customer_id, now, decision, estimated_avoided_cost),
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
        db_path = self._db_path()
        allow_anonymous_sandbox = os.environ.get(
            "THINKGATE_ALLOW_ANONYMOUS_SANDBOX",
            "1",
        ).strip().lower() in {"1", "true", "yes", "on"}

        if not supplied_key:
            if allow_anonymous_sandbox and not configured:
                return AuthContext(customer_id="sandbox", sandbox=True)
            raise PermissionError("missing X-ThinkGate-Key")

        persistent_customer = self._persistent_customer_for_key(supplied_key)
        if persistent_customer:
            return AuthContext(customer_id=persistent_customer, sandbox=False)

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

    def billing_summary(
        self,
        customer_id: str,
        *,
        start_ts: int,
        end_ts: int,
    ) -> dict:
        if start_ts < 0 or end_ts <= start_ts:
            raise ValueError("end_ts must be greater than start_ts")
        db_path = self._db_path()
        if not db_path:
            raise RuntimeError("persistent database is required for billing summaries")

        self._ensure_db(db_path)
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN decision = 'CONTINUE' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN decision = 'STOP' THEN 1 ELSE 0 END),
                    COALESCE(SUM(estimated_avoided_cost), 0.0)
                FROM usage_events
                WHERE customer_id = ?
                  AND created_at >= ?
                  AND created_at < ?
                """,
                (customer_id, start_ts, end_ts),
            ).fetchone()

        requests = int(row[0] or 0)
        continue_count = int(row[1] or 0)
        stop_count = int(row[2] or 0)
        avoided = float(row[3] or 0.0)
        price_per_1000 = max(
            0.0,
            float(os.environ.get("THINKGATE_PRICE_PER_1000_DECISIONS", "0")),
        )
        estimated_charge = requests * price_per_1000 / 1000.0
        return {
            "customer_id": customer_id,
            "period_start": start_ts,
            "period_end": end_ts,
            "requests": requests,
            "billable_decisions": requests,
            "continue": continue_count,
            "stop": stop_count,
            "stop_rate": round(stop_count / requests, 6) if requests else 0.0,
            "estimated_avoided_cost": round(avoided, 8),
            "price_per_1000_decisions_usd": round(price_per_1000, 6),
            "estimated_charge_usd": round(estimated_charge, 6),
            "metering_source": "sqlite_usage_events",
        }


gateway = PilotGateway()
