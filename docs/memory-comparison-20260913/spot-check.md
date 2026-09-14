# Human spot-check sample (10 rated statements per arm, seed 20260914)

Drawn by `random.Random(20260914).sample` over each arm's rated statement list, in file order. For each: open the source in `../labloop-engram-mem-20260913/rating/pack/<letter>/...` and mark agree / disagree; disagreements are reported with the result (PREREG).


## Arm A = legacy (197 rated statements)

| # | candidate | about | type | rating | quote | source | note | human |
|---|---|---|---|---|---|---|---|---|
| 0 | c0001 | c0000 | M | correct | Population held only the trivial baseline (c0000, .0625) | pack/A/records.json |  | |
| 88 | c0009 | c0005 | M | correct | c0005's own wobble appeared very late (step 2400/2560, ~94% elapsed) | pack/A/c0005/summary.md |  | |
| 105 | c0010 | c0001,c0002,c0003,c0004,c0005,c0006,c0007,c0008,c0009 | M | correct | only the 38,045,696 memory parameters were ever in the optimizer, same as all prior candidates in this arm | pack/A/c0001..c0009/memory_config.json |  | |
| 119 | c0012 | c0005,c0009,c0006 | M | incorrect | True fitness falls monotonically as more of the budget is spent decaying (c0005 > c0009 > c0006), while the held-out-wording proxy accuracy and training loss both move in the *opposite* direction (c0009 has the highest proxy accuracy and lowest loss of the three, yet the second-lowest true fitness) | pack/A/records.json; pack/A/c0005/summary.md; pack/A/c0009/summary.md; pack/A/c0006/memory_config.json | fitness ordering holds, but proxy (c0009 .6304 > c0005 .5886 > c0006 .4878) and loss do not move opposite to fitness: c0006 is lowest on both; only the c0005/c0009 pair inverts | |
| 146 | c0014 | c0001 | M | correct | This is **worse than c0001's 0.5532** | pack/A/c0001/memory_config.json |  | |
| 159 | c0016 | c0001 | M | correct | final train loss **0.0020** — matching c0001's near-perfect training fit | pack/A/c0001/memory_config.json |  | |
| 170 | c0017 | c0010,c0005 | M | correct | its full held-out-wording accuracy (0.5789) came in *below* c0005's (0.5886) despite reaching a higher quick-eval peak | pack/A/c0010/memory_config.json; pack/A/c0005/summary.md |  | |
| 188 | c0019 | c0009 | M | correct | below c0009's own 0.4177 fitness | pack/A/records.json |  | |
| 189 | c0019 | c0007,c0009 | M | correct | This is close to c0007's own step count (2252) and noticeably fewer than c0009's (2558) | pack/A/c0007/memory_config.json; pack/A/c0009/summary.md |  | |
| 190 | c0019 | c0007 | R | correct | exactly as c0007's own summary predicted | pack/A/c0007/summary.md | c0007 concluded eval overhead eats gradient-step budget | |

## Arm B = findings (115 rated statements)

| # | candidate | about | type | rating | quote | source | note | human |
|---|---|---|---|---|---|---|---|---|
| 24 | c0005 | c0002 | M | correct | no malformed predictions this run, unlike c0002's one empty answer | pack/B/c0002/summary.md |  | |
| 36 | c0008 | c0002 | M | correct | instead of the parent's `g = torch.sigmoid(self.gate(hidden))` | pack/B/c0002/code/train_predict.py |  | |
| 44 | c0010 | c0009 | M | correct | c0009's `Engram.compute` used a hard structural mask: `hidden + fire * g * mem` where `fire` is a 0/1 flag for whether a token's canonicalised id is a known entity-name (sub)token, and `g = sigmoid(gate(hidden))` | pack/B/c0009/code/train_predict.py |  | |
| 67 | c0014 | c0004 | M | correct | unlike the "scalar gate" mentioned as a regression for an earlier, unmasked candidate in this lineage | pack/B/c0004/code/train_predict.py; pack/B/records.json | c0004 (unnamed): gate nn.Linear(hidden_size, 1), no mask, fitness 0.6687 < parent c0002's 0.7338; c0004 is not in c0014's ancestry, so 'in this lineage' is loose | |
| 80 | c0015 | c0009 | M | correct | c0009 (hard multiplicative mask, zeroing the memory entirely away from name tokens): search 0.885 | pack/B/records.json |  | |
| 87 | c0016 | c0010,c0002 | M | correct | At initialisation (`name_bias = non_name_bias = 0`) this is identical to the parent (and to c0002) — no positions are biased | pack/B/c0010/code/train_predict.py; pack/B/c0002/code/train_predict.py |  | |
| 94 | c0017 | c0013 | M | correct | `run.sh` asserts `requires_grad_(False)` on every model parameter before training and asserts none of the trainable (engram) parameter ids appear among the model's parameters, unchanged from the parent | pack/B/c0013/summary.md |  | |
| 95 | c0017 | c0013 | M | correct | differs from c0013's seed 1609282576, so training runs are not matched | pack/B/c0013/config.json |  | |
| 104 | c0019 | c0009 | M | correct | From parent A (c0009, ..., search 0.885376, this lineage's best) | pack/B/records.json | 0.8853759765625, the population maximum | |
| 108 | c0019 | c0018 | R | unsupported | B's own Limitations named 16384 as an untested intermediate value | pack/B/c0018/summary.md | c0018's summary in the pack has no Limitations section and does not mention 16384; the stripped Finding section is not a rating source | |
