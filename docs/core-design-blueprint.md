# Core Design Blueprint

## Overview
Your Engine is structured into three primary layers—API, Core, and UI—that collaborate to deliver creator-focused AI experiences. The architecture emphasizes modular boundaries so each layer can evolve independently while sharing a unified domain model.

```
+-------------------+
|  Creator Clients  |
+---------+---------+
          |
          v
+---------+---------+
|    API Gateway    |  <-- REST & WebSocket interfaces (src/api)
+---------+---------+
          |
          v
+---------+---------+
|   Orchestration   |  <-- Scenario/Workflow engine (src/core)
+---------+---------+
          |
          v
+-------------------+
| Intelligence Mesh |  <-- AI providers, data stores, plugins
+-------------------+
```

## Layer Responsibilities

### API Layer (`src/api/`)
- Hosts REST and real-time endpoints for creator tools and runtime experiences.
- Performs authentication, rate limiting, and request validation.
- Translates HTTP/WebSocket payloads into core commands and queries.
- Uses feature flags to expose experimental capabilities to selected creators.

### Core Layer (`src/core/`)
- Maintains the domain model for projects, assets, workflows, and execution runs.
- Orchestrates AI and human-in-the-loop steps via a scenario runtime.
- Provides a plugin registry for intelligence providers (LLMs, search, analytics).
- Emits domain events that downstream consumers (metrics, auditing) can subscribe to.

### UI Layer (`src/ui/`)
- Offers a creator-facing studio with project dashboards, workflow editors, and testing sandboxes.
- Consumes the API layer via a typed client SDK and supports collaborative editing.
- Surfaces real-time feedback (run status, AI outputs) through WebSocket channels.
- Integrates onboarding checklists and contextual documentation.

## Cross-Cutting Concerns
- **Identity & Access:** Centralized auth service; JWT-based session tokens; roles for admins, creators, collaborators.
- **Observability:** Centralized logging, distributed tracing, and metrics for usage insights.
- **Data Management:** Versioned storage for assets, prompts, configuration, and generated artifacts.
- **Extensibility:** Plugin system for AI providers and UI extensions with sandboxed execution.
- **Compliance:** Audit trails for AI outputs, moderation hooks, and data retention policies.

## Delivery Workflow
1. **Design** → Update architecture diagrams and RFCs in `docs/`.
2. **Prototype** → Build UI experiments under `src/ui/prototypes/` or in design tooling.
3. **Implement** → Develop API and core features guarded by feature flags.
4. **Validate** → Execute automated tests (`npm test`) and manual creator playtesting.
5. **Deploy** → Promote builds via staged environments with observability enabled.

## Next Milestones
- Finalize domain model schemas for projects, assets, and workflows.
- Implement API gateway skeleton with authentication middleware.
- Deliver interactive workflow editor MVP in the creator studio.
- Instrument end-to-end telemetry pipeline across all layers.
