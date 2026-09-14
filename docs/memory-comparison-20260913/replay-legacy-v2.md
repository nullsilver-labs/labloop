# Selector replay — findings-v1 vs findings-v2 · campaign engram-mem-legacy-w0 (labloop-engram-mem-legacy-20260913)

- memory policy as run: **legacy**; jobs replayed: 19 (baseline excluded); settled cards: 20
- knobs file: `out/memory_config.json` — present for 19 of 20 settled candidates
- limits: max_cards 8, max_bytes 12288, ledger_max_bytes 2048 (the ledger is additional to the card budget)
- this campaign stored no findings snapshot (legacy): both columns are counterfactual

| job | parents | cards avail | v1 cards | v2 cards | off-lineage v1 | off-lineage v2 | v1 bytes | v2 bytes (cards+ledger) | ledger bytes |
|---|---|---|---|---|---|---|---|---|---|
| c0001 | — | 1 | c0000 |  | 1 | 0 | 818 | 809 | 0 |
| c0002 | c0001 | 2 | c0001 c0000 | c0001 | 1 | 0 | 1125 | 1331 | 284 |
| c0003 | c0001 | 3 | c0001 c0002 c0000 | c0001 c0002 | 2 | 1 | 1612 | 2102 | 525 |
| c0004 | c0001 | 4 | c0001 c0002 c0003 c0000 | c0001 c0002 c0003 | 3 | 2 | 2100 | 2860 | 766 |
| c0005 | c0002 | 5 | c0002 c0001 c0003 c0004 c0000 | c0002 c0001 c0003 c0004 | 3 | 2 | 2645 | 3617 | 1007 |
| c0006 | c0005 | 6 | c0005 c0002 c0001 c0003 c0004 c0000 | c0005 c0002 c0001 c0003 c0004 | 3 | 2 | 3191 | 4404 | 1248 |
| c0007 | c0005 | 7 | c0005 c0002 c0001 c0003 c0006 c0004 c0000 | c0005 c0002 c0001 c0003 c0006 c0004 | 4 | 3 | 3679 | 5161 | 1488 |
| c0008 | c0002 | 8 | c0002 c0001 c0005 c0007 c0006 c0004 c0003 c0000 | c0002 c0001 c0005 c0007 c0006 c0004 c0003 | 6 | 5 | 4107 | 5801 | 1729 |
| c0009 | c0006 | 9 | c0006 c0005 c0002 c0007 c0008 c0004 c0003 c0000 | c0006 c0005 c0002 c0007 c0008 c0004 c0003 | 5 | 4 | 4374 | 6327 | 1988 |
| c0010 | c0005 | 10 | c0005 c0002 c0001 c0009 c0008 c0007 c0006 c0004 | c0005 c0002 c0001 c0009 c0007 c0006 c0008 c0004 | 5 | 5 | 4374 | 6593 | 1916 |
| c0011 | c0001 | 11 | c0001 c0005 c0010 c0009 c0008 c0007 c0006 c0004 | c0001 c0005 c0004 c0003 c0010 c0009 c0008 c0007 | 7 | 7 | 4259 | 6477 | 1915 |
| c0012 | c0009 | 12 | c0009 c0006 c0005 c0011 c0010 c0008 c0007 c0004 | c0009 c0006 c0005 c0011 c0010 c0008 c0007 c0004 | 5 | 5 | 4583 | 6743 | 1915 |
| c0013 | c0010 | 13 | c0010 c0005 c0002 c0011 c0012 c0009 c0008 c0007 | c0010 c0005 c0002 c0011 c0012 c0009 c0008 c0007 | 5 | 5 | 4582 | 6641 | 1814 |
| c0014 | c0001 | 14 | c0001 c0011 c0013 c0012 c0010 c0009 c0008 c0007 | c0001 c0011 c0004 c0003 c0013 c0012 c0010 c0009 | 7 | 7 | 4257 | 6376 | 1815 |
| c0015 | c0005 | 15 | c0005 c0002 c0001 c0011 c0014 c0013 c0012 c0010 | c0005 c0002 c0001 c0011 c0010 c0007 c0014 c0013 | 5 | 5 | 4371 | 6506 | 1833 |
| c0016 | c0001 | 16 | c0001 c0011 c0015 c0014 c0013 c0012 c0010 c0009 | c0001 c0011 c0014 c0004 c0015 c0013 c0012 c0010 | 7 | 7 | 4254 | 6370 | 1815 |
| c0017 | c0010 | 17 | c0010 c0005 c0002 c0011 c0016 c0015 c0014 c0013 | c0010 c0005 c0002 c0011 c0013 c0016 c0015 c0014 | 5 | 5 | 4577 | 6684 | 1833 |
| c0018 | c0011 | 18 | c0011 c0001 c0005 c0017 c0016 c0015 c0014 c0013 | c0011 c0001 c0005 c0017 c0016 c0015 c0014 c0013 | 6 | 6 | 4311 | 6390 | 1834 |
| c0019 | c0007, c0009 | 19 | c0007 c0009 c0005 c0006 c0018 c0017 c0016 c0015 | c0007 c0009 c0005 c0006 c0018 c0012 c0017 c0016 | 4 | 4 | 4589 | 6681 | 1816 |

## Totals

- jobs with ≥ 4 cards available: 16
- of those, jobs seeing ≥ 2 cards from outside their lineage: **v1 16 (100%) → v2 16 (100%)**
- cards shown to nobody: **v1 1 → v2 2** (v1: c0019; v2: c0000, c0019)
- cards neither shown nor named in any job's knob ledger, under v2: 2 (c0000, c0019)
- ledger size: mean 1450 B, median 1815 B, max 1988 B of 2048
- rendered memory per job: v1 mean 3569 B, v2 mean 5151 B (1.44×)

## Known repeated ideas — was the earlier candidate visible to the later job?

| later | earlier | card under v1 | card under v2 | ledger row under v2 |
|---|---|---|---|---|
| c0003 | c0002 | yes | yes | yes |
| c0004 | c0002 | yes | yes | yes |
| c0008 | c0005 | yes | yes | yes |
| c0013 | c0006 | no | no | yes |
| c0016 | c0014 | yes | yes | yes |
| c0017 | c0006 | no | no | no |
| c0017 | c0013 | yes | yes | yes |
| c0018 | c0015 | yes | yes | yes |
