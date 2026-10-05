# Synthetic Patient-Level Split demo

This metadata-only dataset is generated for student exercises. Every sample ID, patient ID, grouping, and empty-mask flag is synthetic. It contains no image or mask paths and cannot be loaded for model training.

| Split | Images | Synthetic patients | Synthetic empty masks | Image share | Empty-mask share |
|---|---:|---:|---:|---:|---:|
| Train | 215 | 130 | 25 | 70.03% | 11.63% |
| Val | 46 | 27 | 5 | 14.98% | 10.87% |
| Test | 46 | 28 | 5 | 14.98% | 10.87% |

The counts reproduce the cited report for simulation only. They do not validate the report's underlying Vinmec data or patient-level independence.
