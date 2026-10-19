# Spot check — mem3 pair (human, 10 rated statements per arm)

Sample drawn with seed 20260916 before unsealing (`spot-check-sample.json`). For each statement: open the source
named, decide correct / incorrect / unsupported yourself, and mark agree or disagree with the rater.
Report any disagreement with the rating in RESULT.md. Pack: `../labloop-mem3-20260915/rating/`.

## Pack A

- [ ] **#10 c0002** about c0001, type M, rated **correct**, source `pack/A/c0001/memory_config.json`  
  > a smaller step/epoch count than c0001's 4,024 steps / 9 epochs in the same 480s  
- [ ] **#27 c0004** about c0001, type M, rated **correct**, source `pack/A/c0001/memory_config.json`  
  > removing a third of table capacity (51.7M vs 58.4M trainable params)  
- [ ] **#40 c0005** about c0001, c0003, type M, rated **correct**, source `pack/A/c0001/memory_config.json + pack/A/c0003/memory_config.json`  
  > this is well above the lineage's prior held-out numbers (c0001 0.365, c0003 0.746 on the same kind of holdout)  
- [ ] **#61 c0007** about c0003, type M, rated **correct**, source `pack/A/c0003/code/run.py`  
  > in c0003's closed-vocab scorer, normalize each candidate's summed teacher-forced log-likelihood by its token count before the argmax.  
- [ ] **#94 c0009** about c0001, c0002, c0006, type M, rated **correct**, source `pack/A/c0001/memory_config.json, pack/A/c0002/memory_config.json, pack/A/c0006/memory_config.json`  
  > this lineage's own held-out numbers under greedy decoding (0.20-0.37)  
- [ ] **#97 c0009** about c0005, type M, rated **correct**, source `pack/A/c0005/memory_config.json`  
  > c0005's own weight-decay setting is 0 per the knob ledger  
- [ ] **#129 c0011** about c0005, type M, rated **correct**, source `pack/A/c0005/code/engram.py + pack/A/c0005/memory_config.json`  
  > the right-aligned chunked `score_closed_vocab` teacher-forced scorer (predict-batch-size 256), `attribute_majority_vote` tie-break, gate bias init -2.0 (near-closed at start), AdamW lr 3e-3 / weight_decay 0.0 / batch_size 64, ngram orders {1,2,3}, heads=4, dim_small=32, attach_layer=2  
- [ ] **#164 c0015** about c0005, c0010, c0013, type M, rated **correct**, source `pack/A/c0013/memory_config.json, pack/A/c0010/memory_config.json, pack/A/c0005/memory_config.json`  
  > 0.8154 is above c0013's own 0.7876 (same structure, smaller capacity) but still below c0010's 0.8296 and c0005's 0.8506 on the same kind of holdout  
- [ ] **#169 c0015** about c0005, c0011, type M, rated **correct**, source `pack/A/c0011/memory_config.json + pack/A/c0005/memory_config.json`  
  > c0011 already tested raising capacity within the *separate*- table structure and that did not help either (0.7578 local, below c0005)  
- [ ] **#174 c0016** about c0012, type M, rated **correct**, source `pack/A/c0012/memory_config.json`  
  > c0012 drove training loss to 0.00071 (near-perfect memorization) while held-out-wording accuracy was only 0.7944  

## Pack B

- [ ] **#88 c0008** about c0002, c0004, type M, rated **incorrect**, source `pack/B/c0002/memory_config.json + pack/B/c0004/memory_config.json`  
  > bought a further +0.0805 over c0004, roughly   matching or slightly exceeding the table-decay fix's own contribution (+0.1101 over   c0002)  
  note: Both deltas are right, but +0.0805 is smaller than +0.1101, so it neither matches nor exceeds it.
- [ ] **#124 c0010** about c0001, c0002, c0005, type M, rated **correct**, source `pack/B/records.json`  
  > c0002's held-out regression coincided with a hidden-fitness improvement over c0001; c0005's held-out regression coincided with a hidden-fitness improvement over c0001 too  
- [ ] **#127 c0011** about c0005, c0008, c0010, type M, rated **correct**, source `pack/B/c0010/memory_config.json + pack/B/c0008/memory_config.json`  
  > c0010 combined c0008's zero-weight-decay-everywhere (`weight_decay=0.0`, `table_weight_decay=0.0`  
- [ ] **#137 c0011** about c0005, c0010, type M, rated **correct**, source `pack/B/c0005/memory_config.json + pack/B/c0010/memory_config.json`  
  > Entity index: 1024 entities, 1 tail-bigram collision — identical to c0005/c0010  
- [ ] **#210 c0016** about c0008, type M, rated **correct**, source `pack/B/records.json + pack/B/c0008/code/run.sh`  
  > The only change is in `run.sh`: `--holdout-wordings 1` → `--holdout-wordings 0`, and this candidate's own job-card seed `1939969160` in place of c0008's `1962037190`  
- [ ] **#213 c0016** about c0001, c0002, c0004, c0008, type M, rated **correct**, source `pack/B/c0008/memory_config.json, pack/B/c0001/memory_config.json, pack/B/c0002/memory_config.json, pack/B/c0004/memory_config.json`  
  > higher than c0008's 0.0026 (and c0001/c0002/c0004's 0.0007–0.0012)  
- [ ] **#223 c0017** about c0013, type M, rated **correct**, source `pack/B/c0013/memory_config.json`  
  > Trainable params: **21,176,448** — identical to c0013  
- [ ] **#224 c0017** about c0013, type M, rated **correct**, source `pack/B/c0013/memory_config.json`  
  > up from c0013's 1,774 steps / 113,536 examples in the   same 480.1s budget (≈2.4x more steps)  
- [ ] **#232 c0017** about c0013, type M, rated **correct**, source `pack/B/c0013/summary.md`  
  > **0 malformed answers** (empty, multi-word, or >40 chars) — down from c0013's 4  
- [ ] **#256 c0019** about c0001, type R, rated **correct**, source `pack/B/c0005/summary.md + pack/B/c0001/code/run.sh`  
  > the same class of fix c0005 made to c0001's hardcoded `CUDA_VISIBLE_DEVICES`  

