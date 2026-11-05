# System-Wide Audit Remediation Design

**Intent:** Address the 25 findings in `audit/2026-11-04/ISSUE_REGISTER.md` and build bounded, isolated evidence for the five untested workflow groups named in `SDLC_REMEDIATION_MASTER_PROMPT.md`.

**Users and purpose:** Facility administrators, sonographers, reviewing physicians, and operators working with synthetic or properly authorized data. The work should reduce patient-matching risk, protect facility boundaries, preserve physician control, and make saved findings and reports consistent.

## Goals

- Scope patient identity, settings, and backup authorization to facilities or an explicitly global operator.
- Make the patient directory's persistence, lifetime, and clinical purpose explicit; prevent stale writes and demo records outside demo mode.
- Preserve saved clinical context and accurately distinguish absent, unobserved, zero, AI-suggested, and physician-confirmed information.
- Resolve the documented report, responsive-layout, accessibility, and wording defects.
- Verify blocked workflows only with synthetic data in temporary databases and bounded test storage.

## Non-goals and anti-goals

- No production database access, migrations, backups, network publishing, or deployments.
- No clinical-readiness or model-accuracy claim from software tests, synthetic images, or image-level validation metrics.
- No patient IDs fabricated for AI training; no changes to the image-level SHA-256 deduplication split, Letterbox 512x512 preprocessing, or Dice+BCE training scope.
- No changes to model weights or retraining without provenance, authorized data, and separate evaluation.
- No automatic O-RADS classification from diameter alone; unsupported or incomplete descriptors remain unclassified.

## Approaches considered

1. **Patch each route and screen independently.** Small local changes, but duplicates authorization and validation behavior and risks inconsistent tenant boundaries. Rejected for shared identity, settings, patient-directory, and error-handling contracts.
2. **Reuse existing FastAPI/SQLAlchemy and vanilla-JS boundaries, adding only missing scoped fields and shared helpers.** Keeps the current stack, enables one source of truth for access checks and data contracts, and avoids new dependencies. **Selected.**
3. **Introduce a separate identity service, migration framework, or client state library.** Could support future scale, but adds deployment and operational dependencies not needed to address the verified findings. Rejected unless the existing stack cannot safely express a specific requirement.

## Design decisions

- Use the existing facility authorization model and fail closed when a clinical account lacks a facility. Scope source-ID HMACs with both facility ID and source ID. Preserve existing case records; any legacy patient already linked across facilities must be isolated in a tested migration without deleting or silently conflating records. Never run that migration against production here.
- Keep raw source identifiers out of persistent patient records. The patient directory may retain only fields required for the examined workflow and must enforce facility scope. Local-only mode must say that information is stored on this browser and clear it on logout. The UI must distinguish the source/local identifier from the server research pseudonym.
- Use existing database backup APIs and temporary paths for tests; authorize whole-database backup only to global administrators. Restore tests must use disposable SQLite databases and reject path traversal or cross-facility exposure.
- Keep RUO labels and physician confirmation boundaries. If a rule's clinical reference or model provenance cannot be verified, retain a clear blocked/unsupported state instead of inventing a clinical rule or closing an issue by documentation alone.
- No commit is planned because the supplied checkout already contains extensive unrelated and related uncommitted work. Preserve its contents and record exact verification evidence.

## Success criteria

- Each issue has an explicit status tied to a regression test or direct evidence; blocked external validation remains open.
- Tenant and identity regressions pass against isolated SQLite fixtures; the patient store preserves concurrent updates and a legitimately empty list.
- UI and report tests confirm the observed issues are corrected at the relevant viewport or output boundary.
- Full repository test output, failures, unavailable services, and clinical-validation limitations are reported without claiming staging or patient-care readiness unsupported by evidence.
