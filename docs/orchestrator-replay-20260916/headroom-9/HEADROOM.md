# Headroom replay (Noul / Score per candidate), 2026-09-16 11:37Z

AUC of each signal against the hindsight label (1 = exhausted: no later descendant beat the candidate; 0 = open). Pooled over (tick, candidate) pairs, and once per candidate at its first eligible tick. 0.5 is chance; a signal that predicts *open* rather than exhausted reads below 0.5.

| | engram-mem-findings-w0 | engram-mem-legacy-w0 | engram-mem2-findings-w0 | engram-mem2-legacy-w0 | engram-mem3-findings-w0 | engram-mem3-legacy-w0 | engram-drafts1-w0 | engram-drafts4-w0 | engram-mixed-w0 | all three |
|---|---|---|---|---|---|---|---|---|---|---|
| ticks | 18 | 18 | 18 | 18 | 18 | 18 | 19 | 15 | 15 | 157 |
| calls | 18 | 18 | 18 | 18 | 18 | 18 | 19 | 15 | 15 | 157 |
| errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| latency_per_call_median_s | 0.956 | 1.155 | 0.949 | 0.966 | 0.954 | 0.949 | 0.942 | 0.956 | 0.937 | 0.955 |
| state_bytes_max | 45463 | 94291 | 47492 | 50713 | 48832 | 48975 | 48588 | 45804 | 50595 | 94291 |
| input_tokens_total | 143370 | 280925 | 162855 | 174224 | 157252 | 159627 | 168860 | 134927 | 163599 | 1545639 |
| labeled_pairs | 63 | 98 | 94 | 111 | 102 | 83 | 126 | 67 | 83 | 827 |
| exhausted_pairs | 23 | 60 | 10 | 10 | 27 | 36 | 25 | 22 | 20 | 233 |
| labeled_candidates | 8 | 8 | 10 | 11 | 12 | 10 | 10 | 9 | 9 | 87 |
| exhausted_candidates | 5 | 4 | 2 | 2 | 4 | 4 | 2 | 4 | 3 | 30 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |
| AUC pooled, jev_noul | 0.852 | 0.715 | 0.811 | 0.667 | 0.703 | 0.674 | 0.759 | 0.739 | 0.86 | 0.73 |
| AUC pooled, jev_score_inverted | 0.487 | 0.805 | 0.78 | 0.691 | 0.457 | 0.761 | 0.826 | 0.676 | 0.701 | 0.674 |
| AUC pooled, rule | 0.816 | 0.636 | 0.23 | 0.569 | 0.56 | 0.691 | 0.713 | 0.68 | 0.29 | 0.623 |
| AUC pooled, children | 0.286 | 0.456 | 0.187 | 0.471 | 0.408 | 0.389 | 0.415 | 0.505 | 0.188 | 0.403 |
| AUC pooled, jobs_in_line | 0.173 | 0.475 | 0.165 | 0.312 | 0.387 | 0.477 | 0.401 | 0.481 | 0.179 | 0.374 |
| AUC pooled, search_score | 0.952 | 0.512 | 1.0 | 0.894 | 0.975 | 0.715 | 0.796 | 0.685 | 0.683 | 0.697 |
| AUC first tick, jev_noul | 0.6 | 0.5 | 0.5 | 0.556 | 0.469 | 0.958 | 0.656 | 0.6 | 0.833 | 0.621 |
| AUC first tick, jev_score_inverted | 0.667 | 0.625 | 0.375 | 0.778 | 0.438 | 0.958 | 0.625 | 0.65 | 0.722 | 0.612 |
| AUC first tick, rule | 0.733 | 0.5 | 0.188 | 0.639 | 0.438 | 0.583 | 0.938 | 0.65 | 0.583 | 0.592 |
| AUC first tick, children | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| AUC first tick, jobs_in_line | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| AUC first tick, search_score | 0.867 | 0.625 | 1.0 | 0.722 | 0.938 | 0.792 | 0.625 | 0.45 | 0.556 | 0.678 |
| mean noul, open / exhausted | 0.195 / 0.337 | 0.26 / 0.388 | 0.265 / 0.463 | 0.246 / 0.327 | 0.249 / 0.342 | 0.231 / 0.333 | 0.284 / 0.504 | 0.268 / 0.387 | 0.252 / 0.442 | 0.254 / 0.386 |
