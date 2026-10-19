| measure | findings arm | legacy arm |
|---|---|---|
| campaign | engram-mem3-findings-w0 | engram-mem3-legacy-w0 |
| stop reason | max_candidates 20 reached | max_candidates 20 reached |
| settled (non-baseline) | 19 | 19 |
| exec counts | completed 20 | completed 20 |
| deferred jobs | 0 | 0 |
| GPU-hours | 4.676 | 4.451 |
| wall clock (h) | 2.546 | 2.534 |
| valid candidates per GPU-hour | 4.28 | 4.49 |
| served models (sessions) | claude-haiku-4-5-20251001|claude-sonnet-5: 19 | claude-haiku-4-5-20251001|claude-sonnet-5: 19 |
| sessions that never ran (deferred before start) | none | none |
| turns median / max | 21 / 32 | 24 / 47 |
| best search fitness after 8 settled | 0.7498779296875 | 0.5987548828125 |
| best search fitness after 20 settled | 0.7498779296875 | 0.771240234375 |
| frozen candidate | c0005 | c0009 |
| final-split score (lab's one read) | 0.7503662109375 | 0.861083984375 |
| task claim vs fixed 0.50 | supported | supported |
| job-card tokens, mean (median, max) | 5354.3 (5949, 6440) | 2778 (2859, 3310) |
| prompt ratio findings / legacy | 1.93 (bound ≤ 2.2: within) | |

Coverage (findings arm, 19 jobs with cards): parent violations 0 ; jobs with fewer than two out-of-lineage cards once ≥ 4 existed: 1 ['c0004'] (baseline card not counted), 1 ['c0004'] (baseline counted).

Mechanical pending reasons: none.
