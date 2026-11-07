# Clinical validation preparation — DRAFT, not approved

**Use restriction:** This document is a readiness worksheet for expert review. It is not an approved clinical investigation protocol, does not authorize patient enrollment, and must not be used to justify clinical use.

**Current canonical preparation worksheet:** [docs/evaluation/clinical-validation-preparation.md](../../docs/evaluation/clinical-validation-preparation.md). Use that version for the consolidated cohort, independent-reader, adjudication, discrepancy, acceptance, and approvals checklist; this audit snapshot is retained as supporting evidence and may not include later form updates.

## Questions to approve before a study starts

| Gate | Required decision/evidence | Status |
|---|---|---|
| Intended use and users | Named clinical indication, user group, care setting, and exclusions approved by the clinical owner | BLOCKED — not supplied |
| Ethics and governance | Institutional/ethics determination, consent or waiver basis, privacy review, retention and access plan | BLOCKED — not supplied |
| Regulatory and safety | Device/software classification, hazard analysis, risk controls, incident escalation, and change control approved by the responsible institution | BLOCKED — not supplied |
| Dataset authority | Data rights, permitted use, source provenance, annotation rights, and de-identification review | BLOCKED — not supplied |
| Independence | Patient-grouped development/evaluation split using an authorized source linkage; never fabricate patient IDs | BLOCKED — patient-level independence is unverified |
| Reference standard | Named qualified readers, independent reads, adjudication method, and reference-data version | BLOCKED — expert panel not appointed |
| Acceptance criteria | Numeric limits, confidence intervals, subgroup coverage, and stop rules approved before unblinding | BLOCKED — no thresholds invented |
| Operational readiness | Site IT, PostgreSQL deployment, backup/restore, monitoring, downtime, and rollback evidence | BLOCKED — PostgreSQL target unavailable |

## Separate evaluation tracks

1. **Segmentation:** freeze the model/checkpoint and preprocessing version; compare against an expert-adjudicated pixel mask; predefine boundary and overlap metrics, failure categories, and subgroup reporting. Do not interpret image-level split results as patient-independent evidence.
2. **Caliper:** use traceable physical phantoms or a separately approved reference set with known geometry and scale; document source dimensions, calibration source, endpoint placement, and repeatability. Predefine acceptable absolute/relative error and operator variability with the clinical/metrology owners.
3. **Region assignment:** measure wrong-region selection, missed regions, split/merge handling, and stale-snapshot prevention. Human confirmation remains mandatory.
4. **CDSS:** test deterministic rule outputs against a clinician-approved, versioned case set with expected descriptors, missing-data cases, unsupported patterns, boundary cases, and expected output. This tests rule implementation consistency; it does not validate diagnostic performance.
5. **Workflow and safety:** measure task time, correction burden, wrong-side/wrong-image events, network/database failures, duplicate writes, recovery, and report/print disclosures under the intended site workflow.

## Case selection and accountability worksheet

The clinical owner and statistician must complete and approve these fields before selecting any clinical or retrospective evaluation cases. No thresholds or cohort composition are inferred here.

| Selection item | Required specification | Status |
|---|---|---|
| Intended-use population and indication | Target population, symptoms/indication, care setting, and intended users | TBD — clinical owner approval required |
| Inclusion criteria | Explicit age/population range, exam type, laterality, lesion presentation, and required source-image views | TBD — do not infer from the software demo |
| Exclusion criteria | Image quality limits, unsupported acquisition/modality, missing required views, prior intervention, and other exclusions with reason codes | TBD — clinical owner approval required |
| Spectrum and coverage | How physiologic follicles, multiple lesions, multilocular lesions, solid components, uncertain laterality, and incomplete studies will be represented | TBD — expert/statistical approval required |
| Missing data handling | Required clinical descriptors, unknown/not-visualized semantics, and rules for unusable or incomplete cases | TBD — CDSS owner approval required |
| Sampling and case-flow | Source population, consecutive/random/stratified selection method, screening counts, exclusion counts, replacements, and final analysis set | TBD — statistician approval required |
| Independence and deduplication | Authorized patient-group linkage if available; SHA-256 duplicate-image handling; related studies kept in one patient group for patient-level evaluation | BLOCKED — no authorized patient linkage supplied; do not fabricate identifiers |
| Image-level limitation | Current development split is image-level with exact-file SHA-256 deduplication. Patient-level independence remains unverified; image-level metrics must not be described as patient-independent. | Required disclosure |
| Reference standard | Reader qualifications, blinded independent reads, adjudication and reference-version rules | BLOCKED — expert panel not appointed |

Maintain a case-flow ledger using study-issued non-identifying codes only when authorized. Do not store direct identifiers in the analysis export or logs.

| Screening code | Eligibility | Exclusion reason | Images/views expected and received | Laterality coverage | Reference status | Split/partition | Reviewer/adjudication status |
|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Copyable discrepancy and deviation record

Record every reader disagreement, software deviation, protocol deviation, and safety-relevant failure before adjudication. Preserve original ratings; do not overwrite them with the consensus value.

| Field | Entry |
|---|---|
| Study-issued code / image / region | TBD |
| Date and protocol/build/model/rule versions | TBD |
| Deviation or discrepancy category | TBD |
| Independent reader A result | TBD |
| Independent reader B result | TBD |
| AI / measurement / CDSS output shown to each reader | TBD; blinded-reader phase must state “not shown” |
| Reference/adjudicated result and adjudicator | TBD |
| Clinical or workflow impact / severity | TBD |
| Immediate containment and report impact | TBD |
| Root cause and corrective action | TBD |
| Re-test evidence and closure approver | TBD |

The clinical owner, safety owner, and statistician must approve the case-selection plan, discrepancy workflow, analysis plan, numeric acceptance limits, and stopping rules before any clinical evaluation. All numeric criteria remain **TBD** until signed; no synthetic software test satisfies these approvals.

## Reader and discrepancy procedure

- Readers review independently and blinded to the AI/CDSS output when creating the reference standard.
- Record disagreements before adjudication; retain the original independent ratings and adjudicated result separately.
- Use a study-issued, non-identifying case code only when authorized. Do not put names, record numbers, dates of birth, or free-text PHI in test logs.
- Capture discrepancy type, affected image/region, software/model/rule version, source calibration, severity, immediate containment, adjudication, and corrective action.
- Freeze and hash the dataset manifest, software build, model checkpoint, preprocessing, and rule-engine version before evaluation. Any change requires a documented re-evaluation decision.

## Acceptance and stopping rules to be completed by the clinical owner

- Primary endpoint(s): **TBD; expert approval required**.
- Secondary endpoint(s) and subgroup analysis: **TBD; expert approval required**.
- Required sample size and confidence-interval method: **TBD; statistical review required**.
- Maximum acceptable measurement error and repeatability: **TBD; metrology/clinical approval required**.
- Maximum acceptable critical failure rate and escalation threshold: **TBD; safety approval required**.
- Conditions for pause, rollback, and report correction: **TBD; site approval required**.

Until every applicable gate has signed evidence, the clinical validation status remains **BLOCKED**. Synthetic software tests do not satisfy these gates.
