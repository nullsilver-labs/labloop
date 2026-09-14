| measure | findings arm | legacy arm |
|---|---|---|
| campaign | engram-mem-findings-w0 | engram-mem-legacy-w0 |
| stop reason | max_candidates 20 reached | max_candidates 20 reached |
| settled (non-baseline) | 19 | 19 |
| exec counts | completed 20 | completed 20 |
| deferred jobs | 0 | 0 |
| GPU-hours | 3.695 | 3.921 |
| wall clock (h) | 3.731 | 3.972 |
| valid candidates per GPU-hour | 5.41 | 5.1 |
| served models (sessions) | claude-haiku-4-5-20251001|claude-sonnet-5: 19 | claude-haiku-4-5-20251001|claude-sonnet-5: 19 |
| turns median / max | 18 / 23 | 19 / 24 |
| best search fitness after 8 settled | 0.7337646484375 | 0.4774169921875 |
| best search fitness after 20 settled | 0.8853759765625 | 0.577880859375 |
| frozen candidate | c0009 | c0018 |
| final-split score (lab's one read) | 0.8114013671875 | 0.6439208984375 |
| task claim vs fixed 0.50 | supported | supported |
| job-card tokens, mean (median, max) | 4639.5 (4859, 5467) | 2666.8 (2644, 3425) |
| prompt ratio findings / legacy | 1.74 (bound ≤ 2.0: within) | |

Coverage (findings arm, 19 jobs with cards): parent violations 0 ; jobs with fewer than two out-of-lineage cards once ≥ 4 existed: 8 ['c0004', 'c0006', 'c0011', 'c0012', 'c0015', 'c0016', 'c0017', 'c0019'] (baseline card not counted), 7 ['c0006', 'c0011', 'c0012', 'c0015', 'c0016', 'c0017', 'c0019'] (baseline counted).

Mechanical pending reasons: none.
