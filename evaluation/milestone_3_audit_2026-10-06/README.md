# Evidence package — 2026-10-06

Authoritative closure report: `docs/reports/Kiem_Toan_Moc_3_2026-10-06.md` and its Word export.

- `evidence_inventory.csv`, `inventory_summary.json`: initial inventory, after plan/audit script creation, based on Git HEAD `383def17…`; terminal inspection before those additions showed a clean tree.
- `committed_deletions.csv`: all 469 deletions from the preceding commit, with surviving byte-identical copies where found.
- `selective_recovery.json`: exact recovery of eight unique historical JSON/CSV files from Git. No wholesale reset or restore.
- `verified_data/`: authoritative current data/provenance audit. The root-level `dataset_audit.json`/`mask_provenance.csv` are retained diagnostic output of the first audit pass; that pass classified missing source files together with target disagreements. The corrected pass distinguishes absent source references from actual pixel disagreements. **Use `verified_data/`, not the root diagnostic pass, for conclusions.**
- `active_two_source_index.csv`, `two_source_inventory.json`: current owner-requested scope, only `Vinmec_2d` and `Vinmec_3d`; all frozen canonical samples already belong to those folders. One scoped binary annotation serves as the label/mask. Source clinical approval and patient identity remain unverified.
- `validation_lock/`: research model lock, Validation replay for two configurations, predictions, error panels, component/API benchmark, browser smoke, and the latest full pytest log. No new selected-model Test inference was run.
- `document_backups/`: exact working-tree documents before edits and Git snapshots of index/M2 files which disappeared during this audit. These are backups, not current clinical/experimental results.
- `m2_report_reviewed.md` and `BaoCaoTienDoMoc2_NguyenHuuDung_11235559_reviewed_2026-10-06.docx`: reviewed historical report with a dated audit addendum; not a backdated replacement for an originally submitted document.
- `final_checks.json`, `git_status_final.txt`, `git_diff_stat.txt`: closure hash and Git checks. A successful preservation check does not mean the full test suite passed.

Historical test evidence: 61 passed in the 04/10 log, original command not recorded. Earlier documentation claimed 74 or 75 passed without a timestamped raw log located by this inventory. Current full-suite run: **67 passed, 8 failed**, because declared M1 files are absent. Browser smoke U-Net++: PASS, technical UI scope only. No professional HITL participant results were created.

Seeds in Validation/benchmark provenance refer to the checkpoint training seed (42); evaluation has no randomized sampling. The full pytest suite has no supplied global seed. Model selection among existing runs is retrospective and single-seed.

Patient IDs and expert-approved ground truth cannot be inferred from hashes, anonymous group names, fallback masks, software fixtures or viewer confirmation. Test 402 was used before; current historical results must be described as evaluation on previously used Test set.
