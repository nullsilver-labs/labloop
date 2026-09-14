# Selector replay — findings-v1 vs findings-v2 · campaign engram-mem-findings-w0 (labloop-engram-mem-findings-20260913)

- memory policy as run: **findings-v1**; jobs replayed: 19 (baseline excluded); settled cards: 20
- knobs file: `out/memory_config.json` — present for 19 of 20 settled candidates
- limits: max_cards 8, max_bytes 12288, ledger_max_bytes 2048 (the ledger is additional to the card budget)
- rebuilt v1 selection equals the snapshot stored in each job.json: **yes, for every job** (v1 is unchanged)

| job | parents | cards avail | v1 cards | v2 cards | off-lineage v1 | off-lineage v2 | v1 bytes | v2 bytes (cards+ledger) | ledger bytes |
|---|---|---|---|---|---|---|---|---|---|
| c0001 | — | 1 | c0000 |  | 1 | 0 | 818 | 809 | 0 |
| c0002 | c0001 | 2 | c0001 c0000 | c0001 | 1 | 0 | 2787 | 2993 | 284 |
| c0003 | c0002 | 3 | c0002 c0001 c0000 | c0002 c0001 | 1 | 0 | 4815 | 5262 | 525 |
| c0004 | c0002 | 4 | c0002 c0001 c0003 c0000 | c0002 c0001 c0003 | 2 | 1 | 7164 | 7791 | 766 |
| c0005 | c0002 | 5 | c0002 c0001 c0003 c0004 c0000 | c0002 c0001 c0004 c0003 | 3 | 2 | 10066 | 10894 | 1007 |
| c0006 | c0004 | 6 | c0004 c0002 c0001 c0005 | c0004 c0002 c0005 c0003 | 1 | 2 | 10001 | 11891 | 1266 |
| c0007 | c0002 | 7 | c0002 c0001 c0003 c0004 | c0002 c0001 c0005 c0004 | 2 | 2 | 9823 | 11613 | 1489 |
| c0008 | c0002 | 8 | c0002 c0001 c0003 c0004 | c0002 c0001 c0005 c0007 | 2 | 2 | 9830 | 11477 | 1730 |
| c0009 | c0002 | 9 | c0002 c0001 c0008 c0003 | c0002 c0001 c0005 c0008 c0007 | 2 | 3 | 9485 | 14216 | 1970 |
| c0010 | c0009, c0002 | 10 | c0002 c0009 c0001 c0008 c0003 | c0002 c0009 c0005 c0008 | 2 | 2 | 12089 | 12416 | 1916 |
| c0011 | c0007 | 11 | c0007 c0002 c0001 c0004 | c0007 c0002 c0009 c0010 | 1 | 2 | 10055 | 12372 | 1916 |
| c0012 | c0007 | 12 | c0007 c0002 c0001 c0004 | c0007 c0002 c0009 c0011 | 1 | 2 | 10055 | 12558 | 1916 |
| c0013 | c0009 | 13 | c0009 c0002 c0001 c0008 c0010 | c0009 c0002 c0010 c0008 | 2 | 2 | 12139 | 12377 | 1916 |
| c0014 | c0009 | 14 | c0009 c0002 c0001 c0008 c0010 | c0009 c0002 c0001 c0013 c0010 | 2 | 2 | 12139 | 14111 | 1916 |
| c0015 | c0010 | 15 | c0010 c0002 c0009 c0008 | c0010 c0002 c0013 c0014 | 1 | 2 | 10231 | 12398 | 1916 |
| c0016 | c0010 | 16 | c0010 c0002 c0009 c0008 | c0010 c0002 c0013 c0015 | 1 | 2 | 10231 | 11815 | 1917 |
| c0017 | c0013 | 17 | c0013 c0009 c0002 c0008 | c0013 c0009 c0014 c0016 | 1 | 2 | 10423 | 13177 | 1917 |
| c0018 | c0009 | 18 | c0009 c0002 c0001 c0008 c0010 | c0009 c0002 c0013 c0014 | 2 | 2 | 12139 | 12680 | 1913 |
| c0019 | c0009, c0018 | 19 | c0009 c0018 c0002 c0001 c0008 | c0009 c0018 c0013 c0014 | 1 | 2 | 11796 | 12622 | 1913 |

## Totals

- jobs with ≥ 4 cards available: 16
- of those, jobs seeing ≥ 2 cards from outside their lineage: **v1 9 (56%) → v2 15 (94%)**
- cards shown to nobody: **v1 8 → v2 5** (v1: c0006, c0011, c0012, c0014, c0015, c0016, c0017, c0019; v2: c0000, c0006, c0012, c0017, c0019)
- cards neither shown nor named in any job's knob ledger, under v2: 2 (c0000, c0019)
- ledger size: mean 1484 B, median 1913 B, max 1970 B of 2048
- rendered memory per job: v1 mean 9268 B, v2 mean 10709 B (1.16×)

## Known repeated ideas — was the earlier candidate visible to the later job?

| later | earlier | card under v1 | card under v2 | ledger row under v2 |
|---|---|---|---|---|
| c0016 | c0015 | no | yes | yes |
| c0017 | c0011 | no | no | yes |
| c0019 | c0017 | no | no | yes |
