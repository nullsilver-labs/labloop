# Orchestrator replay (jev, bookkeeping explicit), 2026-09-16 11:12Z

Seed 0; cards clipped to 1500 chars, task to 2500. Read-only replay of recorded ticks; counterfactual children never run.

| measure | engram-drafts4-w0 | engram-mem2-findings-w0 | engram-mem3-findings-w0 |
|---|---|---|---|
| ticks | 15 | 18 | 18 |
| calls | 33 | 39 | 42 |
| errors | 0 | 0 | 0 |
| latency_median_s | 0.732 | 0.734 | 0.733 |
| latency_p95_s | 0.969 | 0.966 | 0.985 |
| state_bytes_median | 22290 | 21627 | 21406 |
| state_bytes_max | 36329 | 37760 | 38317 |
| est_input_tokens_total | 184582 | 210684 | 221490 |
| est_cost_usd | 0.0078 | 0.0088 | 0.0093 |
| parent_agreement_argmax | 0.2 | 0.278 | 0.278 |
| parent_agreement_sampled | 0.133 | 0.167 | 0.333 |
| operator_agreement_argmax | 0.8 | 1.0 | 0.722 |
| full_agreement_argmax | 0.133 | 0.278 | 0.167 |
| argmax_is_best_so_far | 0.867 | 0.722 | 0.944 |
| chance_took_best_so_far | 0.267 | 0.389 | 0.278 |
| mean_p_on_chance_parents | 0.155 | 0.208 | 0.283 |
| mean_p_on_frozen_lineage | 0.461 | 0.686 | 0.339 |
| chance_parent_in_frozen_lineage | 0.533 | 0.611 | 0.222 |
| argmax_in_frozen_lineage | 0.267 | 0.722 | 0.667 |
| crossover_rate_chance | 0.2 | 0.0 | 0.278 |
| crossover_rate_argmax | 0.0 | 0.0 | 0.0 |
| crossover_rate_sampled | 0.2 | 0.167 | 0.333 |
| confidence_median | 0.23 | 0.285 | 0.41 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |

Calibration, engram-drafts4-w0 (parent confidence terciles vs agreement with chance): [0.14, 0.22] n=5 agree=0.4; [0.22, 0.27] n=5 agree=0.2; [0.27, 0.58] n=5 agree=0.0
Calibration, engram-mem2-findings-w0 (parent confidence terciles vs agreement with chance): [0.18, 0.24] n=6 agree=0.167; [0.25, 0.31] n=6 agree=0.333; [0.32, 0.6] n=6 agree=0.333
Calibration, engram-mem3-findings-w0 (parent confidence terciles vs agreement with chance): [0.28, 0.37] n=6 agree=0.167; [0.39, 0.43] n=6 agree=0.0; [0.44, 0.82] n=6 agree=0.667
