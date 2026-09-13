# Resource-matched comparison

cap 43200 s; A (search) 34746 s; G (greedy) 26334 s; **B = 26334 s** (7.315 h)
tie band ±0.004

## search: m2-cifar10-matched-search-20260912 [finished]
- best eligible: c0024 (improve) 0.9528 at cum 20510 s
- last eligible scored completion: c0030 (crossover) 0.9478 at cum 26112 s; unused gap B − cum = 222 s
- excluded crossing candidate: c0031 2026-09-12T22:50:25Z→2026-09-12T23:07:41Z (1036 s, cum 27148 s) fitness 0.9508
- beyond B: c0032=0.9514, c0033=0.9504, c0034=0.9518, c0035=0.9542, c0036=0.9472, c0037=0.9496, c0038=0.9484, c0039=0.9484
- candidate lease total 34746 s (population gpu_seconds 34746.0); rows 40; missing intervals none; still running none
- circuit: max learned failures in a row 0, max deferrals 0
- served models seen: claude-haiku-4-5-20251001, claude-sonnet-5; sessions without sonnet-5: none
- final (separate, not part of B): c0035 score 0.9464 n 10000, lease 21 s; claim supported
- wall 9.73 h; stop reason: max_candidates 40 reached

## greedy: m2-cifar10-matched-greedy-20260912 [finished]
- best eligible: c0029 (improve) 0.9484 at cum 16830 s
- last eligible scored completion: c0039 (improve) 0.9454 at cum 26334 s; unused gap B − cum = 0 s
- candidate lease total 26334 s (population gpu_seconds 26334.0); rows 40; missing intervals none; still running none
- circuit: max learned failures in a row 0, max deferrals 0
- served models seen: claude-haiku-4-5-20251001, claude-sonnet-5; sessions without sonnet-5: none
- final (separate, not part of B): c0029 score 0.9406 n 10000, lease 21 s; claim supported
- wall 7.40 h; stop reason: max_candidates 40 reached

## D = search_best(B) − greedy_best(B) = 0.0044  →  **search advantage**
