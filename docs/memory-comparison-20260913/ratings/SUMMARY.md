# Rating summary — arms A and B (blinded)

Rater: a fresh operator session that ran neither arm. Sources: `pack/<arm>/records.json`
for search fitness, status, parents and operators; the earlier candidate's own
`summary.md`, `config.json`, `memory_config.json` and `code/` for local numbers, code
and what it reported. `SEAL.json` was not opened; nothing outside `rating/` was read.
Every candidate c0001..c0019 of both arms was processed in id order; every non-verbatim
statement about a prior attempt was extracted (all `verbatim.json` lists were empty).
Totals below were computed mechanically from the statement lists in `A.json` / `B.json`
and re-validated after writing.

## Totals

| arm | type | correct | incorrect | unsupported |
|-----|------|--------:|----------:|------------:|
| A | M | 147 | 4 | 0 |
| A | R | 35 | 1 | 4 |
| A | C | 3 | 0 | 3 |
| B | M | 112 | 0 | 1 |
| B | R | 1 | 0 | 1 |
| B | C | 0 | 0 | 0 |

| arm | rated M+R | bad M+R | fraction_bad | unrated |
|-----|----------:|--------:|-------------:|--------:|
| A | 191 | 9 | 0.0471 | 1 |
| B | 115 | 2 | 0.0174 | 1 |

Both arms have ≥ 40 rated M+R statements. Type C is reported separately and is not the
endpoint.

### Bad statements, arm A (9 in M+R, 3 in C)

- c0002 R unsupported — "c0001/c0002 both hit near-zero train loss well before the budget was spent": c0001's artifacts give only its final loss.
- c0006 R incorrect — "c0001, c0002 and c0005 all reached near-zero training loss within roughly the first third of the 420s budget": c0005 reports near-zero by ~244–274 s (~60 %); c0001/c0002 report no trajectory.
- c0007 R unsupported — c0005's quick-held-out-acc "plateaued around 0.55-0.56 well before its budget ran out": c0005 lists only its step-150, peak and final values.
- c0008 R unsupported — c0001/c0002 "trained well past the point of near-zero train loss": no timing in either candidate's artifacts.
- c0009 R unsupported — "nearly all of the learning happens [in the first 80 %] per every prior candidate's loss trajectories": c0001–c0004 report only final losses; c0007 reports loss still falling at cutoff.
- c0012 M incorrect — proxy accuracy and loss "move in the opposite direction" to fitness across c0005/c0009/c0006: c0006 is lowest on both; only the c0005/c0009 pair inverts.
- c0013 M incorrect — 38,045,696 parameters "same as all prior candidates in this arm": c0011 had 37,849,088.
- c0018 M incorrect — steps/epochs "similar to c0011's, so this is not fewer optimizer updates": 2550 vs 2757 steps, 6 vs 7 epochs.
- c0019 M incorrect — c0009's accuracy "kept climbing smoothly through and past its own decay onset with no such drop": c0009 reports a dip (0.6445 → 0.6250 → 0.6191) around decay onset.
- C unsupported: c0012 (template-family overfitting reading of c0005/c0009/c0006), c0014 (fitness "presumably from a different, later evaluation pass"), c0017 (c0010's instability was "the price of a constant lr large enough to keep finding better basins").

### Bad statements, arm B (2 in M+R)

- c0014 M unsupported — the parent's freshly-initialised gate "starts near output 0 … giving sigmoid(0) ≈ 0.5": no artifact records the parent's initial gate value.
- c0019 R unsupported — "B's own Limitations named 16384 as an untested intermediate value": c0018's pack summary contains no such section or number (the stripped `## Finding` section is not a rating source).

### Unrated

- A: 1 — c0001's mention of the LoRA/full-FT reference runs (operator references, not candidates).
- B: 1 — c0001's mention of the LoRA reference script (same reason).

## Cross-branch acknowledgment

Named earlier candidates that are neither the parent nor an ancestor:

- A: 2 candidates — c0001 names c0000 (the trivial baseline, for its score); c0004 refers to c0002 and c0003 without ids as "the two other `improve` attempts on this parent" (fitness only; it states it did not read their summaries). No other A candidate names any non-ancestor; every one of A's other 17 candidates names only its own line.
- B: 1 candidate — c0014 names c0010 (a non-ancestor sibling line) and refers to c0004 without id as the "scalar gate" regression.

Full per-candidate lists are in the `acknowledgment` arrays.

## Unacknowledged repeats (same knob and direction as an earlier non-ancestor, not named)

- A: 6 clear — c0003 (weight decay; repeats c0002), c0008 (best-held-out checkpoint; repeats c0005), c0013 (full-budget cosine decay; repeats c0006), c0017 (full-budget cosine decay; repeats c0006 and c0013), c0018 (TABLE_SIZE ×4; repeats c0015), c0016 (hash-key canonicalisation; repeats c0014 with a different mechanism — flagged, judgement call). Plus c0004, which repeats c0002's weight-decay knob but acknowledged the siblings without ids (listed as acknowledged).
- B: 2 clear — c0016 (second gate-logit bias at non-name positions; repeats c0015 exactly, same parent), c0017 (dropout 0.1 on the memory path; repeats c0011). One partial, flagged: c0014 (constant per-channel sigmoid gate parameter; c0006 had introduced the same parameter combined with a hidden-dependent scalar gate).

No intentional (named, reasoned) replications of a non-ancestor were found in either arm; B/c0019 re-runs c0018's table-size knob at a new value but c0018 is its named parent.

## Difficulties applying the rubric

1. Repeated restatements. Workers often restate the same fact about a parent several times in one summary (e.g. "c0005's 0.5886" in the results, again in the assessment). Each distinct claim was counted once per summary; verbatim restatements were not double-counted. Counting every restatement would inflate A's totals more than B's (A's summaries are 2–3× longer).
2. Hypotheses vs. causal claims. Pre-run hypotheses about why an earlier result happened ("that inversion is consistent with…", "two readings are possible…") were not extracted as C statements; only causal claims asserted as the worker's reading were. A handful of A's C-type units are therefore judgement calls; none affect the endpoint.
3. Stripped `## Finding` sections. B/c0019 attributes a "Limitations" note to c0018 that exists only in the stripped section, so it is unsupported by rule even though it may well be true; B/c0001's own local numbers are likewise absent from the pack (its `memory_config.json` is a reload), which made B/c0010's "best … in the lineage" verifiable only against c0002 and c0009.
4. "Lineage" is used loosely in both arms (sometimes ancestors, sometimes the whole campaign). Where a claim is true under the narrow reading and only arguably false under the broad one (B/c0010, B/c0014), it was rated correct with a note.
5. Split units. Two A sentences mixing correct numbers with an unverifiable timing clause (c0008) or a fitness gloss with a report of a diagnosis (c0019) were split into an M unit and an R unit so that neither the number nor the report was rated on the other's merits.
6. Mechanical count checks across "every prior candidate" (A/c0006, c0007, c0010, c0013) were verified against every earlier `memory_config.json`, which is how the c0013 error surfaced; the human spot-check may want to include one of these.
