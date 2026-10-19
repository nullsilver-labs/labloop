# Orchestrator replay (jev, scores hidden), 2026-09-16 10:53Z

Seed 0; cards clipped to 1500 chars, task to 2500. Read-only replay of recorded ticks; counterfactual children never run.

| measure | engram-drafts4-w0 | engram-mem2-findings-w0 | engram-mem3-findings-w0 |
|---|---|---|---|
| ticks | 15 | 18 | 18 |
| calls | 35 | 37 | 37 |
| errors | 0 | 0 | 0 |
| latency_median_s | 0.726 | 0.718 | 0.711 |
| latency_p95_s | 0.947 | 0.981 | 0.96 |
| state_bytes_median | 19242 | 18774 | 17122 |
| state_bytes_max | 30854 | 32673 | 30453 |
| est_input_tokens_total | 168599 | 173512 | 157332 |
| est_cost_usd | 0.0071 | 0.0073 | 0.0066 |
| parent_agreement_argmax | 0.133 | 0.222 | 0.278 |
| parent_agreement_sampled | 0.267 | 0.222 | 0.222 |
| operator_agreement_argmax | 0.8 | 1.0 | 0.722 |
| full_agreement_argmax | 0.133 | 0.222 | 0.167 |
| argmax_is_best_so_far | 0.533 | 0.222 | 1.0 |
| chance_took_best_so_far | 0.267 | 0.389 | 0.278 |
| mean_p_on_chance_parents | 0.164 | 0.207 | 0.276 |
| mean_p_on_frozen_lineage | 0.487 | 0.699 | 0.477 |
| chance_parent_in_frozen_lineage | 0.533 | 0.611 | 0.222 |
| argmax_in_frozen_lineage | 0.733 | 1.0 | 0.667 |
| crossover_rate_chance | 0.2 | 0.0 | 0.278 |
| crossover_rate_argmax | 0.0 | 0.0 | 0.0 |
| crossover_rate_sampled | 0.333 | 0.056 | 0.056 |
| confidence_median | 0.23 | 0.325 | 0.64 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |

Calibration, engram-drafts4-w0 (parent confidence terciles vs agreement with chance): [0.14, 0.2] n=5 agree=0.0; [0.21, 0.27] n=5 agree=0.0; [0.27, 0.53] n=5 agree=0.4
Calibration, engram-mem2-findings-w0 (parent confidence terciles vs agreement with chance): [0.22, 0.26] n=6 agree=0.167; [0.31, 0.41] n=6 agree=0.167; [0.44, 0.75] n=6 agree=0.333
Calibration, engram-mem3-findings-w0 (parent confidence terciles vs agreement with chance): [0.53, 0.59] n=6 agree=0.0; [0.61, 0.69] n=6 agree=0.167; [0.69, 0.81] n=6 agree=0.667
