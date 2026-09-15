| measure | findings arm | legacy arm |
|---|---|---|
| campaign | engram-mem2-findings-w0 | engram-mem2-legacy-w0 |
| stop reason | max_candidates 20 reached | max_candidates 20 reached |
| settled (non-baseline) | 19 | 19 |
| exec counts | completed 20 | completed 20, deferred 1 |
| deferred jobs | 0 | 1 |
| GPU-hours | 3.667 | 4.234 |
| wall clock (h) | 3.698 | 4.794 |
| valid candidates per GPU-hour | 5.45 | 4.72 |
| served models (sessions) | claude-haiku-4-5-20251001|claude-sonnet-5: 19 | claude-haiku-4-5-20251001|claude-sonnet-5: 19 |
| sessions that never ran (deferred before start) | none | c0008 |
| turns median / max | 16 / 23 | 22.0 / 32 |
| best search fitness after 8 settled | 0.7442626953125 | 0.3577880859375 |
| best search fitness after 20 settled | 0.81103515625 | 0.795166015625 |
| frozen candidate | c0016 | c0014 |
| final-split score (lab's one read) | 0.8729248046875 | 0.699462890625 |
| task claim vs fixed 0.50 | supported | supported |
| job-card tokens, mean (median, max) | 5229.4 (5809, 6208) | 2824.7 (2871.0, 3409) |
| prompt ratio findings / legacy | 1.85 (bound ≤ 2.2: within) | |

Coverage (findings arm, 19 jobs with cards): parent violations 0 ; jobs with fewer than two out-of-lineage cards once ≥ 4 existed: 1 ['c0004'] (baseline card not counted), 1 ['c0004'] (baseline counted).

Mechanical pending reasons: none.
