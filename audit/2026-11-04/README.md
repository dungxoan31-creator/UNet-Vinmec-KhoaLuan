# Audit deliverables — read-only — 2026-11-04

The files `REPORT.md`, baseline screenshots and source captures describe the read-only audit as of 04/11. Remediation performed on 05/11 is documented separately in [REMEDIATION_REPORT.md](REMEDIATION_REPORT.md), with current issue dispositions appended to the register.

- [Báo cáo đầy đủ và executive summary](REPORT.md)
- [Issue register: 25 baseline findings plus current disposition](ISSUE_REGISTER.md) · [CSV with remediation columns](issues.csv) · [JSON baseline snapshot](issues.json)
- [UI/UX friction](FRICTION_REPORT.md)
- [Data and business logic](DATA_BUSINESS_REPORT.md)
- [AI and clinical safety](AI_SAFETY_REPORT.md)
- [Measured user flows](USER_FLOW_REPORT.md)
- [Screen coverage](SCREEN_COVERAGE.csv) · [Feature coverage](FEATURE_COVERAGE.csv) · [API coverage](api-coverage.csv) · [Module coverage](MODULE_COVERAGE.csv)
- [Coverage counts](coverage-summary.json) · [Repository inventory](inventory.json) · [Repository file discovery](repository-files.txt)
- [Rendered fields](field-inventory.json) · [Source input inventory](input-source-inventory.json)
- [Source excerpts](source-evidence.md) · [Clinical references](clinical-sources.md) · [Unchanged source hashes](source-integrity.json)
- [Browser results](browser-results.json) · [Deep browser results](deep-browser-results.json) · [API probes](probe-results.json) · [Corrected tenant probes](tenant-results.json)
- [Store regression reproductions](store-probe-results.json) · [23 passing selected unit tests](node-tests.log)
- [Actual print-handler PDF](actual-print.pdf) · [Print text](actual-print-text.json) · [Final browser/print results](final-browser-results.json)
- [CUA observation](cua-state.json) · [CUA screenshot](cua-login.png) · [CUA action verification](cua-dismiss.json)

Screenshots are named by screen and viewport. Contact sheets sheet-1.jpg to sheet-10.jpg help navigation; detailed judgments should use original resolution captures.

**Evidence caution:** report-reviewed-print.pdf and print-page-1.png came from an invalid initial media-only print capture and are NOT evidence of a product printing defect. Use actual-print.pdf. Early seeded-user 401 responses in probe-results.json are not authorization evidence; use corrected tenant-results.json. Synthetic runtime databases are retained only for reproducibility. No production records were accessed.

During the 04/11 audit itself, no source changes, fixes, deployments, commits or PRs were made. Remediation was performed later in the already-dirty working tree; it has not been committed or deployed. NO-GO applies to clinical multi-facility deployment, not a claim that every research-only function fails. Both reports explicitly record untested and blocked areas.
