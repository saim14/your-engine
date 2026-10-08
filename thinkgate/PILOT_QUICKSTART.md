# ThinkGate Pilot Quickstart

ThinkGate is an adaptive reasoning controller for production AI. A pilot customer receives a single API key and uses it to ask ThinkGate whether another reasoning step is worth its expected cost.

Base URL:

`https://thinkgate-production.up.railway.app`

## Authentication

Every production request must include:

```
X-ThinkGate-Key: <your-pilot-api-key>
```

Keep the key secret. ThinkGate stores only a SHA-256 hash of provisioned customer keys.

## 1. Make a decision

```bash
curl -X POST "https://thinkgate-production.up.railway.app/api/v1/decision" \
  -H "Content-Type: application/json" \
  -H "X-ThinkGate-Key: $THINKGATE_KEY" \
  -d '{
    "predicted_gain": 0.04,
    "next_step_cost": 0.10,
    "margin": 0.0,
    "current_quality": 0.82,
    "step_index": 1,
    "max_steps": 4,
    "trace_id": "example-001"
  }'
```

Typical response:

```json
{
  "api_version": "v1",
  "customer_mode": "pilot",
  "decision": "STOP",
  "reason": "expected_gain_not_worth_cost",
  "policy": "gain_minus_cost_v1"
}
```

The controller returns `CONTINUE` only when expected gain exceeds the next-step cost plus the configured margin. At `max_steps`, ThinkGate always returns `STOP`.

## 2. Read cumulative usage

```bash
curl "https://thinkgate-production.up.railway.app/api/v1/usage" \
  -H "X-ThinkGate-Key: $THINKGATE_KEY"
```

This returns cumulative request count, STOP/CONTINUE counts, stop rate, and estimated avoided normalized cost.

## 3. Read a billing-period summary

Use Unix timestamps for a half-open interval `[start_ts, end_ts)`.

```bash
curl "https://thinkgate-production.up.railway.app/api/v1/billing-summary?start_ts=1760000000&end_ts=1760086400" \
  -H "X-ThinkGate-Key: $THINKGATE_KEY"
```

The response includes billable decisions, STOP/CONTINUE counts, stop rate, estimated avoided cost, configured price per 1,000 decisions, and estimated charge.

For the initial design-partner pilot, pricing is intentionally configured at USD 0 per 1,000 decisions. Usage is still fully metered so a later paid plan can be evaluated from real data rather than estimates.

## Integration contract

ThinkGate does not execute the customer's LLM call. The customer's application measures or predicts the expected value of one more reasoning step, supplies its normalized next-step cost, and follows ThinkGate's `STOP` or `CONTINUE` response.

The current production API is intentionally narrow:

- `POST /api/v1/decision`
- `GET /api/v1/usage`
- `GET /api/v1/billing-summary`

## Pilot safety

- Customer API keys can be revoked immediately.
- Provisioned keys are returned in plaintext only once and are stored only as hashes.
- Usage events are persisted on the production Railway volume.
- Anonymous production decision access is disabled.
- The pilot is not yet a general claim that ThinkGate improves every reasoning workload; scientific validation on harder tasks remains a separate track.
