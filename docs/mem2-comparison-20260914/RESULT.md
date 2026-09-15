# Legacy vs finding cards, second seed — result (2026-09-15)

Read once, after both arms had written `REPORT.md`, against the rule frozen in
`../../../labloop-mem2-20260914/PREREG.md` before either arm was launched.
`STATUS.md` holds the run facts, the mechanical measures and the procedural defect
found on the way; this file holds the primary endpoint and the decision.

## Decision: **not_supported**

`scripts/mem_decide.py` over the blinded rater's `ratings/A.json` and `B.json`,
`ratings/SEAL.json` (A = legacy, B = findings, drawn with `secrets` by
`scripts/mem_rating_pack.py --keep-finding`) and `mechanical.json`; output
`decision.json` / `decision.md`.

| | findings arm (pack B) | legacy arm (pack A) |
|---|---|---|
| fraction_bad over M+R (bad / rated) | **0.095** (18 / 190) | **0.060** (15 / 252) |
| M: correct / incorrect / unsupported | 165 / 14 / 1 | 212 / 11 / 1 |
| R: correct / incorrect / unsupported | 7 / 0 / 3 | 25 / 0 / 3 |
| C (reported, not the endpoint): correct / incorrect / unsupported | 3 / 0 / 0 | 14 / 0 / 1 |
| unrated (reason listed) | 3 | 2 |
| candidates with a cross-branch acknowledgment | 12 (21 references) | 3 (3 references, 2 excluding the baseline) |
| unacknowledged repeats / named replications | 1 / 4 | 4 / 1 |

fraction_bad findings / legacy = **1.59**; supported needed ≤ 0.50. Both arms have ≥ 40
rated M+R statements, 19 settled non-baseline candidates, ended at their candidate cap
and were served the same models, so no pending clause applies. Every rated statement is
quoted with its source and note in `ratings/*.json`; `ratings/SUMMARY.md` is the rater's
own report, including the difficulties it had applying the rubric.

**The first pass, without the type definitions** (`ratings-first-pass/`, STATUS.md):
findings 0.103 (16 / 155) vs legacy 0.051 (9 / 177), ratio 2.03. Same direction, same
decision; the improvised definitions did not make the result.

## What the bad statements are

All 33 bad M+R statements are listed by `decision.md`'s companion query in the operator
session; five were verified at the source by the operator (findings c0008's two `orders`
claims, findings c0019's `weight_decay` claim, legacy c0015's "520k-row table", legacy
c0006's "c0004 did not touch `engram_memory.py`"): the rater was right in all five.

- **Legacy (15).** Misread trajectories and directions between siblings ("a milder
  understatement", "rising monotonically", "a larger drop in relative terms"), three
  reports attributed to summaries that do not contain them, one table size off by 4 %,
  and two "never tested past 0.4" claims that c0005 (dropout 0.6) contradicts. The
  familiar legacy pattern from the first pair: long narrative comparisons with small
  factual slips.
- **Findings (18).** Eleven of the eighteen are **novelty claims that the population
  contradicts**: "no candidate in this lineage ever varied `orders`" (c0001 and c0002
  did), "every prior `run.sh` hardcoded `--orders 1`", "`weight_decay` has never been
  varied anywhere" (c0009 and c0014 ran 0.01), "every 540 s run also used heads=8"
  (c0011 had 4), "batch_size fully explored in both directions" (only ever raised),
  "the single largest jump in the ledger" (two larger ones exist), plus two param-count
  errors that copy a rounded "14.1M" from an earlier card (the file says 15,166,720) and
  one "seed-only" comparison that was not seed-only. The workers wrote these under an
  explicit "repeat check" against the knob ledger, in the `## Finding` section that this
  preregistration rates.

## Why the findings arm got the novelty claims wrong — a tooling finding

The knob ledger was built to answer exactly "has this knob been varied?", and in these
jobs it could not. Read from the `job.json` snapshots the workers received:

- **c0019** (weight_decay): the ledger held rows for c0011–c0018 only; c0001–c0010 were
  **dropped by the 2 KiB bound** (`ledger.omitted`, 10 of 18). c0009's row, the only one
  where `weight_decay 0→0.01` would have appeared as a diff against its parent, was among
  them; c0014's row (present) shows no `weight_decay` line because c0014 inherited 0.01
  from c0009 unchanged. The worker's context contained the string "decay" nowhere.
- **c0008** (orders): all seven rows were present, but `orders` is a **list**, and
  `sanitize_knobs` carries scalars only ("nothing nested"), so the `c0002 ← c0001` row
  shows `seed` and `trainable_params` and not `orders [1,2,3]→[1,2]`. The worker's context
  mentioned orders only in three cards that said "orders 1".
- In both jobs every row is **truncated at 240 bytes with its keys in alphabetical
  order**, so outcome keys (`epochs_started`, `examples_seen`, `final_loss`,
  `holdout_wording_acc`, `seed`, `steps`) fill the row before knob keys later in the
  alphabet (`table_rows`, `train_seconds`, `weight_decay`) can appear: 12 of the 14 rows
  end in "[truncated]".

So the memory told these workers, in effect, "here is the ledger; a knob and direction
already in it is a repeat", and the ledger did not contain the knobs. A worker that
trusts a ledger which is silent on a knob writes "never varied". The legacy arm's
workers, with no ledger, made fewer such claims and hedged the ones they made. This is
the mechanism the preregistration set out to test, and on this seed it worked against
the arm it was built for, for reasons that are mechanical and fixable: (1) the ledger
should list knob keys only, never outcome keys, (2) list-valued knobs need a compact
rendering, (3) a per-knob index ("`weight_decay`: 0.0 (c0001…c0008, c0010…), 0.01
(c0009, c0014)") answers the question in a fraction of the bytes that per-candidate diff
rows cost, and never drops old candidates. None of that is a change to this read.

## What this does and does not show

- On this seed, this order and this selector, workers given finding cards and the knob
  ledger made **more** incorrect or unsupported statements about earlier attempts than
  workers given the first-parent lineage, not fewer. The preregistered claim is not
  supported at a second seed; the first pair's `supported` (0.017 vs 0.047, one seed,
  `## Finding` stripped) stands as it was, and the two together are a description of two
  seeds that disagree, not a pooled test.
- The rubric changed between the pairs, as preregistered: the `## Finding` section is
  rated here. The rater's SUMMARY says that section supplies a large share of the
  findings arm's units, cross-branch references *and* errors. Under the first pair's
  rubric (section stripped) most of the eleven novelty claims would not have been units;
  the asymmetry was declared in PREREG and cuts against the findings arm by design.
- Cross-branch acknowledgment moved the way the cards intend: 12 findings candidates
  named a candidate outside their lineage against 3 legacy ones, and the findings arm
  named 4 intentional replications with a reason against 1 unacknowledged-repeat count
  of 1 vs 4. The cards make workers talk about the population; the ledger, as built,
  made some of what they said wrong.
- Prompt cost 1.85 × legacy, within the 2.2 bound. Search and final scores (.811 / .873
  vs .795 / .699) are not read as memory evidence (PREREG; the drafts differ).
- Coverage was 18 of 19 under findings-v2: the miss is the single-draft opening, not the
  selector (STATUS.md); the drafts pair, run after this one, had full coverage.

## Procedure as executed, and the deviations

1. 2026-09-14: both `REPORT.md` present, watchers done. 2026-09-15 morning: mechanical
   pass re-run after fixing `mem_mechanical.py` to set aside the legacy arm's deferred
   session that never ran (pending reasons: none).
2. Pack built by `scripts/mem_rating_pack.py --keep-finding` at
   `../labloop-mem2-20260914/rating/` (manifest `rating-MANIFEST.sha256`, README
   `rating-README.md`).
3. **Deviation.** The README carried the unit, types and ratings by reference only (the
   PREREG says "carried forward verbatim"; the builder copied that sentence, not the
   paragraphs). A first fresh Opus rater rated the whole pack with improvised definitions
   and said so. That pass was set aside as evidence (`ratings-first-pass/`), the builder
   fixed, the README completed in place with the verbatim 2026-09-13 paragraphs (same
   `pack/`, same `SEAL.json`, manifest regenerated), and a second fresh Opus rater rated
   from the completed README. The decision is on the second rating; the first is reported
   above. Neither rater opened the seal or the arm directories; a slight leak of the
   assignment exists in the pack itself (pack A carries the deferred c0008 record, 20
   records vs 19), which a rater who knew which arm had the deferral could read; neither
   rater's report mentions it.
4. Unsealed and decided by `scripts/mem_decide.py`; totals recomputed from the statement
   lists and found equal to the rater's.
5. Blind second-rater check of 10 seeded statements per arm (`spot-check.md`, seed
   20260915): see `spot-check-second-rater.md`. Human spot-check: still open, as it is
   for the first pair.

Nothing in either arm's directory was modified.
