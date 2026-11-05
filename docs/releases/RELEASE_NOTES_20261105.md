# Engineering Readiness Notes — 2026-11-05

> This is an engineering status record, not approval for clinical deployment or a production release. The system remains **NO-GO** for patient-care use and multi-facility pilot.

## Changes in this follow-up

| Commit | Change | Evidence boundary |
|---|---|---|
| `9f03c95` | Restored the global Research Use Only banner and compact statusbar notice. | Synthetic browser/layout checks; no clinical approval implied. |
| `f6620d6` | Added the AUD-020 boundary dossier and synthetic 29.9/30.0/30.1 mm comparison report. | No clinician/supervisor sign-off; CDSS retains `<30 mm`. |
| `082b615` | Added a guarded image-level validation harness with SHA-256 checks and unsigned-output safeguards. | Real held-out evaluation is blocked because the source images and sufficient split provenance are unavailable. |
| This follow-up | Added a unified regression runner, `npm run test:all`, updated the stale RUO banner assertion, and recorded readiness evidence. | No merge or deployment approval. |

## Current audit disposition

The 2026-11-05 remediation report tracks 28 technical findings: 27 VERIFIED and 1 PARTIAL (AUD-020). These statuses are bounded to the evidence described in that report; they do not establish clinical validity or deployment readiness.

- The RUO banner is visible before login and on the workstation statusbar.
- ACR O-RADS US v2022 describes a premenopausal physiologic follicle at `≤3 cm` as O-RADS 1/normal ovary with no management. This does not justify assigning all other cysts to O-RADS 3 or a fixed follow-up interval. The project keeps `<30 mm` until documented clinical sign-off. [ACR O-RADS US v2022 Assessment Categories](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf)
- The selected ComboLoss model remains a research candidate. Patient-level independence and clinical performance are unverified; no benchmark from the new harness was produced because 1,604 manifest image paths are missing in this checkout.
- Native PostgreSQL 16, migrations, multi-worker behavior, and facility isolation remain unverified because the Docker server is unavailable.
- No merge to `main` was performed. Clinical sign-off, independent validation, native PostgreSQL verification, and review/approval of the branch remain open.

## Regression evidence

The unified runner completed **6/6 steps**:

- JavaScript syntax check: 60 modules passed with `node --check` (this is not static type analysis).
- Node suite: **170 passed, 0 failed**.
- Clinical-safety browser E2E: **30 checks passed**, no page errors; CTA natural position at 1366×768 was y=577.8–621.8.
- Responsive product-brand browser E2E: passed.
- Python suite: **1,620 passed, 0 failed**, with two warnings (SQLite date-adapter deprecation and the intentional oversized-image safety fixture).
- `git diff --check HEAD`: passed.

Run log: `artifacts/all-verifications-20261105-212931-590733.log` (ignored by Git).
The existing `.gitignore` rules already exclude `artifacts/`, logs, and test caches, so no duplicate ignore patterns were added.

Previously completed focused evidence remains bounded to the synthetic/local fixtures recorded in `audit/2026-11-04/REMEDIATION_REPORT.md` and the task commits above. Passing software tests do not validate diagnosis, patient-level independence, or clinical safety.
