| arm | # | by | the error | queries | verdict | bytes returned |
|---|---|---|---|---|---|---|
| mem2L | 153 | c0012 | dropout past 0.4 never tested | knob dropout_p | reachable | 212 |
| mem2L | 184 | c0015 | small table only tested up to 0.4 | knob dropout_p | reachable | 266 |
| mem2L | 187 | c0015 | this 520k-row table (it is 500,000) | open c0012 | reachable | 698 |
| mem2L | 120 | c0009 | higher than every held-out value in the lineage | lineage c0009 ; open c0002 | reachable | 703 |
| mem2F | 33 | c0005 | c0003 has 14.1M trainable params | open c0003 | reachable | 1990 |
| mem2F | 45 | c0006 | double c0003's 14.1M | open c0003 | reachable | 2008 |
| mem2F | 54 | c0006 | previous best held-out was c0001's | open c0002 | reachable | 2180 |
| mem2F | 67 | c0008 | orders never varied from [1] | knob orders ; search n-gram orders | reachable | 2381 |
| mem2F | 69 | c0008 | first to pass --orders 1 2 | knob orders ; search orders 1 2 bigram | reachable | 2602 |
| mem2F | 133 | c0014 | every 540 s run used heads=8 | knob train_seconds ; knob heads | reachable | 677 |
| mem2F | 148 | c0015 | c0009 vs c0003 is seed-only | open c0009 | reachable | 2567 |
| mem2F | 160 | c0017 | layer 4 the only other depth point | knob attach_layer | reachable | 405 |
| mem2F | 186 | c0019 | weight_decay never varied | knob weight_decay | reachable | 151 |
| mem2F | 187 | c0019 | batch_size explored in both directions | knob batch_size | reachable | 443 |
| mem3F | 43 | c0005 | previous table sizes were not recorded | knob table_rows | reachable | 200 |
| mem3F | 76 | c0008 | same 262144-ish tables as c0001 | open c0001 ; knob table_rows | reachable | 2040 |
| mem3F | 99 | c0009 | c0001-c0006 all below 0.26 search | best | reachable | 316 |
| mem3F | 133 | c0011 | table_rows only recorded for c0005 | knob table_rows | reachable | 346 |
| mem3F | 178 | c0016 | c0009 was on free-form decoding | open c0009 ; knob decoding | reachable | 2458 |
| mem3F | 190 | c0017 | closed-vocab held-out runs 0.79-0.85 | knob decoding holdout_wording_acc | reachable | 763 |
| mem3L | 53 | c0006 | c0002 is the best in the population | best | not settled at launch | 255 |
| mem3L | 94 | c0009 | parent c0005 best so far | best | not settled at launch | 316 |
| mem3L | 109 | c0010 | c0008 best in the population | best | not settled at launch | 320 |
| mem3L | 128 | c0011 | c0008 best in the population | best | not settled at launch | 328 |
| mem3L | 123 | c0010 | best held-out with the entity channel | search entity channel held-out accuracy | not settled at launch | 2643 |
| mem3L | 186 | c0014 | c0002 best among decay variants | knob weight_decay ; knob table_weight_decay | reachable | 480 |
| mem3L | 229 | c0017 | c0009's steps not available | open c0009 | reachable | 703 |
| mem3L | 73 | c0007 | c0005 ran 4252 steps (4255) | open c0005 | reachable | 676 |
| mem3L | 181 | c0014 | c0006 final loss 0.0012 (0.00094) | open c0006 | reachable | 783 |

reachable 24 of 29; 5 could not have been known at launch; 0 not reachable by the asked query
