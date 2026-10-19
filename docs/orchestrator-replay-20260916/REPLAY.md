# Orchestrator replay (jev), 2026-09-16 10:50Z

Seed 0; cards clipped to 1500 chars, task to 2500. Read-only replay of recorded ticks; counterfactual children never run.

| measure | engram-drafts4-w0 | engram-mem2-findings-w0 | engram-mem3-findings-w0 |
|---|---|---|---|
| ticks | 15 | 18 | 18 |
| calls | 31 | 37 | 37 |
| errors | 0 | 0 | 0 |
| latency_median_s | 0.736 | 0.713 | 0.718 |
| latency_p95_s | 0.97 | 0.954 | 0.964 |
| state_bytes_median | 19760 | 19271 | 17572 |
| state_bytes_max | 31686 | 33550 | 31284 |
| est_input_tokens_total | 153347 | 178100 | 161517 |
| est_cost_usd | 0.0064 | 0.0075 | 0.0068 |
| parent_agreement_argmax | 0.267 | 0.333 | 0.278 |
| parent_agreement_sampled | 0.067 | 0.278 | 0.333 |
| operator_agreement_argmax | 0.8 | 1.0 | 0.722 |
| full_agreement_argmax | 0.2 | 0.333 | 0.167 |
| argmax_is_best_so_far | 0.933 | 0.778 | 1.0 |
| chance_took_best_so_far | 0.267 | 0.389 | 0.278 |
| mean_p_on_chance_parents | 0.179 | 0.267 | 0.293 |
| mean_p_on_frozen_lineage | 0.46 | 0.628 | 0.369 |
| chance_parent_in_frozen_lineage | 0.533 | 0.611 | 0.222 |
| argmax_in_frozen_lineage | 0.333 | 0.667 | 0.667 |
| crossover_rate_chance | 0.2 | 0.0 | 0.278 |
| crossover_rate_argmax | 0.0 | 0.0 | 0.0 |
| crossover_rate_sampled | 0.067 | 0.056 | 0.056 |
| confidence_median | 0.33 | 0.445 | 0.495 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |

Calibration, engram-drafts4-w0 (parent confidence terciles vs agreement with chance): [0.19, 0.28] n=5 agree=0.4; [0.29, 0.35] n=5 agree=0.4; [0.38, 0.48] n=5 agree=0.0
Calibration, engram-mem2-findings-w0 (parent confidence terciles vs agreement with chance): [0.32, 0.39] n=6 agree=0.333; [0.4, 0.48] n=6 agree=0.167; [0.51, 0.87] n=6 agree=0.5
Calibration, engram-mem3-findings-w0 (parent confidence terciles vs agreement with chance): [0.41, 0.47] n=6 agree=0.167; [0.47, 0.52] n=6 agree=0.0; [0.52, 0.9] n=6 agree=0.667
