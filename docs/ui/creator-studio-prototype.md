# Creator Studio Prototype

## Experience Goals
- **Empower creators** to assemble AI-driven experiences without touching code.
- **Reveal system intelligence** by surfacing model decisions, data lineage, and moderation events.
- **Encourage iteration** through quick publish/test cycles and actionable analytics.

## Navigation Map
```
+-----------------------+
|  Global Navigation    |
|-----------------------|
| Projects              |
| Templates             |
| Insights              |
| Settings              |
+-----------------------+
        |
        v
+-----------------------+      +-----------------------+
| Project Dashboard     | ---> | Workflow Editor       |
| - Activity timeline   |      | - Canvas & nodes      |
| - Experiment results  |      | - Node inspector      |
| - Team presence       |      | - Asset library       |
+-----------------------+      +-----------------------+
        |
        v
+-----------------------+
| Test Lab              |
| - Scenario simulator  |
| - AI response diffing |
| - Feedback capture    |
+-----------------------+
```

## Key Screens
1. **Project Dashboard**
   - Highlights project status, recent runs, and collaborator comments.
   - Provides quick actions to create workflows, manage assets, or invite teammates.
2. **Workflow Editor**
   - Node-based canvas with drag-and-drop AI, tool, and human review steps.
   - Inspector panel allows editing prompts, parameters, and branching logic.
   - Asset library lists reusable prompts, datasets, and UI components.
3. **Test Lab**
   - Simulates end-user interactions with configurable inputs.
   - Shows streaming AI responses with moderation and latency indicators.
   - Allows capturing qualitative feedback and turning it into backlog items.

## Interaction Patterns
- **Collaborative Presence:** Avatars and cursors indicate teammates editing the same workflow.
- **Contextual Docs:** Inline guidance cards link to `docs/getting-started.md` and tutorials.
- **Version Snapshots:** Creators can snapshot a workflow state and compare outputs.
- **Accessibility:** Keyboard shortcuts for node creation, screen-reader friendly labels, and high-contrast themes.

## Prototype Roadmap
1. Build low-fidelity wireframes covering dashboard, editor, and test lab states.
2. Conduct creator interviews to validate navigation and terminology.
3. Iterate toward high-fidelity mockups aligned with the design system.
4. Validate flows with usability tests before implementing in `src/ui/`.
