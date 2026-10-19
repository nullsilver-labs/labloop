# Headroom replay (Noul / Score per candidate), 2026-09-16 11:37Z

AUC of each signal against the hindsight label (1 = exhausted: no later descendant beat the candidate; 0 = open). Pooled over (tick, candidate) pairs, and once per candidate at its first eligible tick. 0.5 is chance; a signal that predicts *open* rather than exhausted reads below 0.5.

| | engram-drafts4-w0 | engram-mem2-findings-w0 | engram-mem3-findings-w0 | all three |
|---|---|---|---|---|
| ticks | 15 | 18 | 18 | 51 |
| calls | 15 | 18 | 18 | 51 |
| errors | 0 | 0 | 0 | 0 |
| latency_per_call_median_s | 0.937 | 0.948 | 0.952 | 0.951 |
| state_bytes_max | 45804 | 47492 | 48832 | 48832 |
| input_tokens_total | 134927 | 162855 | 157252 | 455034 |
| labeled_pairs | 67 | 94 | 102 | 263 |
| exhausted_pairs | 22 | 10 | 27 | 59 |
| labeled_candidates | 9 | 10 | 12 | 31 |
| exhausted_candidates | 4 | 2 | 4 | 10 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |
| AUC pooled, jev_noul | 0.756 | 0.812 | 0.702 | 0.743 |
| AUC pooled, jev_score_inverted | 0.682 | 0.786 | 0.449 | 0.614 |
| AUC pooled, rule | 0.68 | 0.23 | 0.56 | 0.513 |
| AUC pooled, children | 0.505 | 0.187 | 0.408 | 0.387 |
| AUC pooled, jobs_in_line | 0.481 | 0.165 | 0.387 | 0.338 |
| AUC pooled, search_score | 0.685 | 1.0 | 0.975 | 0.849 |
| AUC first tick, jev_noul | 0.625 | 0.5 | 0.469 | 0.526 |
| AUC first tick, jev_score_inverted | 0.65 | 0.469 | 0.406 | 0.493 |
| AUC first tick, rule | 0.65 | 0.188 | 0.438 | 0.436 |
| AUC first tick, children | 0.5 | 0.5 | 0.5 | 0.5 |
| AUC first tick, jobs_in_line | 0.5 | 0.5 | 0.5 | 0.5 |
| AUC first tick, search_score | 0.45 | 1.0 | 0.938 | 0.748 |
| mean noul, open / exhausted | 0.261 / 0.381 | 0.267 / 0.475 | 0.253 / 0.343 | 0.26 / 0.38 |
