# Contributing Guidelines

Thank you for your interest in improving Your Engine! This document outlines how to collaborate effectively while the project is in its formative stages.

## Development Workflow
1. **Plan**
   - Review the [Core Design Blueprint](docs/core-design-blueprint.md) and related docs before proposing changes.
   - Create an issue or RFC for significant architectural updates.
2. **Develop**
   - Branch from `main` using a descriptive name (`feature/workflow-editor-mvp`).
   - Keep commits focused and reference relevant issues.
3. **Validate**
   - Run the project scripts before opening a PR:
     ```bash
     npm run lint
     npm run format
     npm test
     npm run build
     ```
   - Document any limitations or follow-up work in the PR description.
4. **Review**
   - Request feedback from at least one maintainer.
   - Address comments via follow-up commits instead of force-pushing when possible.
5. **Document**
   - Update `docs/` and `README.md` when behavior, APIs, or UI flows change.

## Code Standards
- Maintain clear separation between `src/api`, `src/core`, and `src/ui`.
- Prefer TypeScript for new implementation files to enable static typing.
- Write unit tests alongside features once the testing framework is introduced.
- Favor modular, composable components and avoid duplicating logic across layers.

## Communication
- Use the issue tracker for design discussions and roadmap planning.
- Capture meeting notes and decisions in the `docs/` directory.
- Celebrate wins and share learnings in project updates to keep creators motivated!

We appreciate your contributions and creativity—let's build empowering experiences together.
