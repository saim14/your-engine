# API Surface & Data Flow Plan

## Guiding Principles
- **Consistency:** All endpoints follow REST conventions with predictable resource URLs.
- **Extensibility:** Versioned API namespaces (`/v1`) allow additive changes without breaking clients.
- **Observability:** Correlate every request with trace IDs propagated to the core orchestration layer.
- **Security:** JWT-authenticated requests, scoped API keys for automation, and rate limiting per workspace.

## Primary Resources
| Resource | Description | Key Fields |
|----------|-------------|------------|
| `projects` | Creator workspaces containing workflows, assets, and deployment settings. | `id`, `name`, `status`, `team`, `created_at`, `updated_at` |
| `workflows` | Directed graphs representing AI + human collaboration steps. | `id`, `project_id`, `nodes`, `edges`, `version`, `last_run_id` |
| `assets` | Reusable prompts, datasets, or UI snippets tied to a project. | `id`, `project_id`, `type`, `label`, `metadata` |
| `runs` | Execution records capturing input/output and telemetry for workflows. | `id`, `workflow_id`, `status`, `inputs`, `outputs`, `metrics` |
| `insights` | Aggregated analytics summarizing performance across runs. | `id`, `project_id`, `time_window`, `metrics`, `recommendations` |

## Endpoint Sketch
```
GET    /v1/projects
POST   /v1/projects
GET    /v1/projects/{projectId}
PATCH  /v1/projects/{projectId}

GET    /v1/projects/{projectId}/workflows
POST   /v1/projects/{projectId}/workflows
GET    /v1/workflows/{workflowId}
PATCH  /v1/workflows/{workflowId}
POST   /v1/workflows/{workflowId}:duplicate

GET    /v1/projects/{projectId}/assets
POST   /v1/projects/{projectId}/assets
GET    /v1/assets/{assetId}
PATCH  /v1/assets/{assetId}

POST   /v1/workflows/{workflowId}:run
GET    /v1/runs/{runId}
GET    /v1/runs/{runId}/events

GET    /v1/projects/{projectId}/insights
```

## Data Flow
1. **Client Request:** Creator studio issues an authenticated request to the API gateway.
2. **Request Enrichment:** Middleware validates identity, injects trace IDs, and applies feature flags.
3. **Command Dispatch:** Gateway translates requests into core commands (`CreateProject`, `StartRun`).
4. **Core Orchestration:** Scenario engine resolves workflow graphs, invokes AI providers, and records state changes.
5. **Event Emission:** Domain events (e.g., `RunCompleted`) are published to the event bus for analytics and notifications.
6. **Response Assembly:** Gateway transforms domain results into API-friendly DTOs and returns them to the client.

## Real-Time Channel
- WebSocket endpoint `/v1/streams` multiplexes channels for run updates, collaborator presence, and system announcements.
- Messages use a JSON envelope: `{ "channel": "runs", "event": "run.updated", "payload": { ... } }`.

## SDK Considerations
- Generate a TypeScript client from OpenAPI specs to ensure type safety in the UI layer.
- Provide helper utilities for handling optimistic updates and offline caching in the creator studio.

## Next Steps
- Draft OpenAPI specification capturing resources, schemas, and error models.
- Define event payload contracts shared between the API and real-time channels.
- Implement authentication middleware prototypes within `src/api/`.
