# Independent read-only product audit

Scope: current dirty worktree; no remediation, dependency changes, migrations, production data access, commits or PRs.

1. Inventory source files, frontend routes and controls, API decorators, ORM entities, AI and reporting boundaries. Record source SHA-256 before execution.
2. Launch only the inspected isolated-server harness, with a new database and data directory inside this audit directory, empty DATABASE_URL, test credentials and bytecode disabled. Use synthetic images only. Capture desktop/responsive screens, DOM controls/text, browser errors and API traces.
3. Probe selected cross-layer flows, authorization, persistence, AI fail-closed behavior and report provenance. Record actual operation counts/time; never infer clinical accuracy from synthetic images.
4. Consolidate evidence-backed findings, limitations, coverage matrix and recommendations. Verify source hashes unchanged. Unexecuted areas remain NOT TESTED/BLOCKED.

Skill context launcher omitted because downloading/executing an opaque binary or writing skill state exceeds read-only authorization. Existing PRODUCT.md and DESIGN.md read directly. User severity definitions take precedence over skill severity labels. No numerical UX score without adequate measurement.
