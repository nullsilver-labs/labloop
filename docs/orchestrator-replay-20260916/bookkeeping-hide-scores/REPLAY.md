# Orchestrator replay (jev, scores hidden, bookkeeping explicit), 2026-09-16 11:14Z

Seed 0; cards clipped to 1500 chars, task to 2500. Read-only replay of recorded ticks; counterfactual children never run.

| measure | engram-drafts4-w0 | engram-mem2-findings-w0 | engram-mem3-findings-w0 |
|---|---|---|---|
| ticks | 15 | 18 | 18 |
| calls | 34 | 36 | 39 |
| errors | 0 | 0 | 0 |
| latency_median_s | 0.731 | 0.712 | 0.723 |
| latency_p95_s | 0.962 | 0.962 | 1.008 |
| state_bytes_median | 21772 | 21131 | 20956 |
| state_bytes_max | 35497 | 36883 | 37486 |
| est_input_tokens_total | 185770 | 190013 | 201257 |
| est_cost_usd | 0.0078 | 0.008 | 0.0085 |
| parent_agreement_argmax | 0.2 | 0.222 | 0.278 |
| parent_agreement_sampled | 0.133 | 0.0 | 0.222 |
| operator_agreement_argmax | 0.8 | 1.0 | 0.722 |
| full_agreement_argmax | 0.133 | 0.222 | 0.167 |
| argmax_is_best_so_far | 0.267 | 0.222 | 1.0 |
| chance_took_best_so_far | 0.267 | 0.389 | 0.278 |
| mean_p_on_chance_parents | 0.153 | 0.16 | 0.262 |
| mean_p_on_frozen_lineage | 0.507 | 0.737 | 0.463 |
| chance_parent_in_frozen_lineage | 0.533 | 0.611 | 0.222 |
| argmax_in_frozen_lineage | 0.933 | 1.0 | 0.667 |
| crossover_rate_chance | 0.2 | 0.0 | 0.278 |
| crossover_rate_argmax | 0.0 | 0.0 | 0.0 |
| crossover_rate_sampled | 0.267 | 0.0 | 0.167 |
| confidence_median | 0.29 | 0.305 | 0.495 |
| model | jev-1.13.0 | jev-1.13.0 | jev-1.13.0 |

Calibration, engram-drafts4-w0 (parent confidence terciles vs agreement with chance): [0.16, 0.26] n=5 agree=0.2; [0.28, 0.3] n=5 agree=0.2; [0.31, 0.48] n=5 agree=0.2
Calibration, engram-mem2-findings-w0 (parent confidence terciles vs agreement with chance): [0.19, 0.26] n=6 agree=0.167; [0.27, 0.35] n=6 agree=0.333; [0.38, 0.49] n=6 agree=0.167
Calibration, engram-mem3-findings-w0 (parent confidence terciles vs agreement with chance): [0.31, 0.44] n=6 agree=0.333; [0.46, 0.52] n=6 agree=0.167; [0.52, 0.63] n=6 agree=0.333
