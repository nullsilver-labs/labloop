# Rating summary — blinded arms A and B (rated 2026-09-16)

Rated by a fresh session that ran neither arm, from `rating/pack/` only, against the
frozen rubric in `rating/README.md`. Arm letters only; `SEAL.json` was not opened and
nothing outside `rating/` was read.

## Per-arm totals

| | A | B |
|---|---|---|
| M correct / incorrect / unsupported | 187 / 6 / 3 | 200 / 22 / 5 |
| R correct / incorrect / unsupported | 17 / 0 / 0 | 30 / 0 / 1 |
| C correct / incorrect / unsupported | 1 / 0 / 5 | 1 / 0 / 5 |
| rated M+R | 213 | 258 |
| bad M+R (incorrect + unsupported) | 9 | 28 |
| **fraction_bad (M+R)** | **0.0423** | **0.1085** |
| unrated statements | 6 | 6 |
| statements extracted in total | 219 | 264 |

Both arms clear the rubric's 40-rated-M+R floor and have 19 settled non-baseline
candidates each. Type C is reported separately and is not part of the endpoint.

## What drove the bad M+R statements

**Arm A (9).** Three are "ledger/attribution" claims that no source in the pack can
confirm (c0005 and c0011 on what the knob ledger recorded; c0017's "0.79-0.85 under
closed-vocab" range). Six are wrong about a named earlier candidate: c0003 claiming its
seed and trained weights were unchanged from c0001; c0008 calling c0001's table sizes
"262144-ish"; c0009's "c0001-c0006, all below 0.26 search" (c0003 and c0005 are ~0.74);
c0016 calling c0009 part of the "free-form-decoding" lineage when c0009 used closed-vocab
decoding; and two from c0010 about c0008's scorer (it claims c0008 gathers before the
float32 cast, then correctly states the opposite later in the same file, and claims the
tie-break and GPU cleanup were the *only* functional differences between c0003 and c0008).

**Arm B (28).** Three clusters dominate:
1. **A wrong description of the shared held-out metric, repeated across five candidates
   (7 statements).** c0005 asserts that held-out wording 7 "was seen (with 1023 other
   names) during training", and c0005/c0007/c0009/c0010/c0013/c0017 then describe the
   metric as "known template, unseen entity". c0001's summary and
   `c0009/code/train_predict.py`'s split (`train` = wordings 0-6, `val` = wording 7, all
   entities in both) show the opposite: it is an unseen template on known entities.
   B's own c0015 and c0019 state it correctly, so the arm contradicts itself.
2. **"Best in the population" claims contradicted by `records.json` (6 statements):**
   c0006 (c0002 best, but c0005 is higher), c0009 (c0005 best so far, but c0008 is
   higher), c0010 twice and c0011 once (c0008 best, but c0009 is higher; and c0008's
   0.8010 called the best held-out score when c0001, c0006 and c0009 are higher),
   c0014 (c0002 best among decay variants). These may have been true at dispatch time
   for jobs running concurrently; the note on each statement says so, but the lab's
   record contradicts the claim as written.
3. **Misquoted parent numbers / arithmetic (7 statements):** c0007 attributing its own
   4252 steps to c0005 (4255); c0014 giving c0006's final loss as 0.0012 (it is 0.0009 —
   that is c0002's figure); c0008's "+0.0805 ... matching or slightly exceeding +0.1101";
   c0017's "~90% of the gap" (actually 71%) and its claim that c0009's summary reports
   examples but not steps (it reports 4181 steps); c0002's "the only difference is
   weight_decay" when the seed also differs; c0010 on a "real GPU collision" that c0005
   described as hypothetical.
   Plus three unverifiable claims in c0003 (c0001 emitting malformed/off-menu answers —
   c0001 reported zero malformed; c0000's inlined logic — c0000's code is not in the
   pack; a fallback rate compared to c0001, which has no fallback) and c0014's claim
   about the dispatch-time population table.

## Unrated statements (6 per arm)

- **A:** five quote the operator reference runs (LoRA / full fine-tune holdout numbers
  from `reference/RESULTS.md`) — those are not campaign candidates and the file is not
  in the pack; one is about the candidate's own run. Note the arm quotes two different
  LoRA holdout numbers (.991 in c0001/c0002, .9653 in c0005/c0018).
- **B:** four quote the same reference runs; two are statements about the task data
  (`facts.json` templates, search-split cue words), not about an earlier candidate.

## Cross-branch acknowledgment (candidates named that are not the parent or an ancestor)

- **Arm A — 15 of 18 non-baseline children name at least one cross-branch candidate:**
  c0004 [c0002]; c0005 [c0001,c0002,c0003]; c0008 [c0004,c0005]; c0009 [c0003,c0005,c0007];
  c0010 [c0005,c0007]; c0011 [c0003,c0007,c0009]; c0012 [c0005,c0010]; c0013 [c0005,c0011];
  c0014 [c0012]; c0015 [c0005,c0011]; c0016 [c0006,c0009]; c0018 [c0002,c0005,c0006,c0009];
  c0019 [c0008]. (c0002, c0003, c0006, c0007, c0017 name only parents/ancestors.)
- **Arm B — 3 of 18:** c0005 [c0002,c0003,c0004] (naming the line it is *not* on);
  c0014 [c0013] (a GPU-contention note); c0019 [c0009,c0013,c0015] (naming the line it
  cannot read). Every other candidate names only its parents and their ancestors.

## Unacknowledged repeats (secondary measure)

- **Arm A: 1.** c0008 repeats c0003's stated single change — replacing c0001's free-form
  greedy decoding with closed-vocab scoring over the 16 known per-attribute values, on
  c0001's otherwise unchanged architecture — without naming c0003 (it does name c0005,
  which also used closed-vocab decoding). Six other repeats in A are acknowledged by id
  (c0009←c0003, c0011←c0008, c0013←c0005, c0014←c0012, c0015←c0005, c0016←c0006).
- **Arm B: 1.** c0018 (improve off c0002) repeats c0004's stated single change exactly —
  exempt the sparse tables from AdamW weight decay while keeping 0.01 on the dense
  proj/gate — and never names c0004, which had already run it and reported 0.7205; c0018
  reports 0.7937 for the same knob and direction. Three other repeats in B are
  acknowledged (c0008←c0001, c0011←c0002, c0014←c0006).

## Rating conventions used where the rubric was silent

1. **Superlatives.** "best so far" / "best in the population" was checked against every
   candidate with a lower id in `records.json`. Where the statement enumerates the
   comparison set in the same sentence (e.g. "the three decay variants"), it was judged
   within that set, with a note naming the higher-scoring candidate outside it.
2. **"byte-for-byte unchanged" claims.** Rated `correct` when the only difference is a
   docstring or usage comment and every architectural/hyperparameter value listed is
   identical; the note records the difference. This applies to several statements in
   both arms.
3. **Reference-run claims** (LoRA / full fine-tune numbers) are `unrated`: they are not
   statements about a campaign candidate and `reference/RESULTS.md` is not in the pack.
4. **Claims about c0000** are rated against `records.json` (operator `baseline`, fitness
   0.0625) plus `task.md`'s definition of the trivial baseline, since c0000's own
   directory is not in the pack; a claim about c0000's *code* is `unsupported`.
5. **Type C** was rated `correct` only when an earlier candidate's own artifacts support
   the mechanism claimed, `unsupported` when it is the writer's own inference from a
   single confounded run. Both arms come out the same way (1 correct, 5 unsupported).
6. Exact duplicate restatements of the same fact inside one summary were counted once.

## Difficulties

- The biggest judgement call was the "best so far" family (convention 1). Under a
  dispatch-time reading several of B's six would be defensible; under the lab's record
  they are contradicted. They are 6 of B's 28 bad statements: excluding them entirely
  would give B `fraction_bad` = 22/252 = 0.087 against A's 0.042, so the direction of
  the comparison does not depend on this call.
- Type C is almost always an unablated single-run inference in both arms, so the C
  column carries little information either way.
- Blinding held in the sense that assignment was not inferred or reported; both arms'
  summaries carry per-candidate headings, and both mention lineage-style material, so
  the partial-blinding caveat in the prereg applies as stated.
