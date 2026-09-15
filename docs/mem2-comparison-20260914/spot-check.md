# Human spot-check sample (10 rated statements per arm, seed 20260915)

Drawn by `random.Random(20260915).sample` over each arm's rated statement list, in file order (`ratings/<letter>.json`). For each: open the source in `../labloop-mem2-20260914/rating/pack/<letter>/...` and mark agree / disagree; disagreements are reported with the result (PREREG). The second-rater check is `spot-check-second-rater.md`; the human check is still open.

## Arm A = legacy (267 rated statements)

| # | candidate | about | type | rating | quote | source | note | human |
|---|---|---|---|---|---|---|---|---|
| 8 | c0002 | c0001 | M | correct | the true hidden-split fitness ... came back lower still at 0.217 | pack/A/records.json |  | |
| 52 | c0005 | c0001,c0002 | M | correct | the held-out-wording signal, which tracked hidden-split fitness directionally for c0001->c0002 | pack/A/records.json + memory_config.json | c0001->c0002: both proxy and fitness rose | |
| 53 | c0005 | c0002,c0003 | M | incorrect | the held-out-wording signal, which tracked hidden-split fitness directionally for ... c0002->c0003 | pack/A/records.json + memory_config.json | c0002->c0003 the proxy fell (0.503->0.404) while fitness rose (0.314->0.358) | |
| 66 | c0006 | c0004 | M | correct | [table column c0004] 3127 steps \| 200,128 examples \| loss@1382 0.6200 \| final 0.2230 \| dropout_p 0.39998 \| held-out 0.5088 \| 480.1 s | pack/A/c0004/memory_config.json + summary.md |  | |
| 81 | c0007 | c0006 | M | correct | and that scored worse still (fitness 0.248) | pack/A/records.json |  | |
| 105 | c0009 | c0001 | C | correct | the memory was overfitting to literal training phrasing rather than generalizing the entity+attribute addressing | pack/A/c0001/summary.md |  | |
| 150 | c0012 | c0003 | M | correct | c0003 dropout=0.4 -> fitness 0.358 | pack/A/records.json |  | |
| 170 | c0014 | c0012 | M | correct | Backbone frozen params: 596,049,920, unchanged from c0012 | pack/A/c0012/summary.md |  | |
| 206 | c0017 | c0012 | M | correct | Parent: c0012 (fitness 0.7840576171875) | pack/A/records.json |  | |
| 229 | c0018 | c0012 | M | correct | the loss curve also converged to a higher final value (0.033 vs c0012's 0.013) | pack/A/c0012/memory_config.json |  | |

## Arm B = findings (193 rated statements)

| # | candidate | about | type | rating | quote | source | note | human |
|---|---|---|---|---|---|---|---|---|
| 4 | c0002 | c0001 | R | correct | both slightly higher than c0001's 0.8562/0.0003, on the same kind of same-pool holdout | pack/B/c0001/summary.md |  | |
| 26 | c0004 | c0003 | M | correct | Built directly on c0003's code (engram.py unchanged, train_and_predict.py unchanged) | pack/B/c0003/code/ | diff confirms only run.sh differs | |
| 52 | c0006 | c0005 | M | correct | Every other knob is identical to c0005 (and to c0003 except heads): orders=[1], heads=8, table_size=50021, d_mem=64, attach_layer=2, lr_embed=1e-2, lr_head=1e-3, batch_size=32 | pack/B/c0005/memory_config.json |  | |
| 85 | c0010 | c0007 | M | correct | from parent c0007, moved the memory attach point from decoder layer 6 to decoder layer 4; orders [1], heads 8, table 50021, d_mem 64, train-seconds 540, lr schedule, batch size, prompt format all identical to c0007 | pack/B/c0007/memory_config.json |  | |
| 103 | c0011 | c0006 | M | correct | and c0006's 0.9658 | pack/B/c0006/memory_config.json |  | |
| 147 | c0015 | c0010 | M | correct | roughly double c0010's 112,937,984 bytes | pack/B/c0010/summary.md |  | |
| 164 | c0017 | c0010 | M | correct | changed --seed from c0010's own seed (517708568) | pack/B/records.json |  | |
| 179 | c0018 | c0016 | M | correct | c0006->c0016: 32->64 at attach_layer 2, delta search +0.0668 | pack/B/records.json |  | |
| 184 | c0019 | c0018 | M | correct | c0018 (batch_size 128, same attach_layer 2) drove training loss to near zero (0.0018) | pack/B/c0018/summary.md |  | |
| 187 | c0019 | c0016,c0017,c0018 | M | incorrect | without touching batch_size itself (a knob+direction already fully explored in both directions) | pack/B/memory_config.json of c0016/c0017/c0018 | batch_size was only ever raised (32->64 twice, 64->128); no candidate lowered it | |
