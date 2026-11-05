# Clinical source verification — 2026-11-04

- [VERIFIED] Primary ACR O-RADS US v2022 assessment categories: https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf . The official search result explicitly states follicle ≤3 cm and risk bands 1–<10% / 10–<50%. Used only to assess terminology consistency in AUD-020. No complete rule-engine validation is claimed.
- [VERIFIED] Primary ACR lexicon, January 2023 revision: https://www.acr.org/-/media/ACR/Files/RADS/O-RADS/O-RADS-US-v2022-Lexicon-Terms-Table-2023.pdf . Follicle definition includes a simple cyst ≤3 cm in the premenopausal group. Size alone does not establish physiologic status.
- [PARTIALLY VERIFIED] IOTA/ADNEX source references and coefficients are present in backend/services/cdss_engine.py. Independent formula transcription, all clinical branches, and appropriate-population validation were NOT TESTED in this audit.
- [PARTIALLY VERIFIED] MMOTU manifest declarations were inspected locally. Image/mask redistribution rights, upstream labels, physical dataset hashes and independent clinical validation were not re-established here. Do not treat repository assertions or synthetic inference as clinical evidence.

An initial outdated ACR landing URL failed to open. The official PDFs above were located through web search; no third-party source was used for the clinical terminology finding.
