# Legacy vs finding cards — result (2026-09-14)

Read once, after both arms had written `REPORT.md`, against the rule frozen in
`PREREG.md` before either arm was launched. `STATUS.md` holds the run facts, the
bug and leakage checks and the mechanical secondary measures; this file holds the
primary endpoint and the decision.

## Decision: **supported** (feasibility, one seed)

`scripts/mem_decide.py` over the blinded rater's `ratings/A.json` and `B.json`,
`ratings/SEAL.json` (A = legacy, B = findings, drawn with `secrets` by
`scripts/mem_rating_pack.py`) and `mechanical.json`; output `decision.json`.

| | findings arm (pack B) | legacy arm (pack A) |
|---|---|---|
| fraction_bad over M+R (bad / rated) | **0.017** (2 / 115) | **0.047** (9 / 191) |
| M: correct / incorrect / unsupported | 112 / 0 / 1 | 147 / 4 / 0 |
| R: correct / incorrect / unsupported | 1 / 0 / 1 | 35 / 1 / 4 |
| C (reported, not the endpoint): correct / incorrect / unsupported | 0 / 0 / 0 | 3 / 0 / 3 |
| unrated (reason listed) | 1 | 1 |
| candidates with a cross-branch acknowledgment | 1 | 2 |
| unacknowledged repeats / acknowledged replications | 3 / 0 | 6 / 1 |

fraction_bad findings / legacy = **0.37 ≤ 0.50**; both arms have ≥ 40 rated M+R
statements, ≥ 10 settled non-baseline candidates, ended at their candidate cap and
were served the same model, so no pending clause applies. Every rated statement is
quoted with its source and note in `ratings/*.json`; `ratings/SUMMARY.md` is the
rater's own report, including the difficulties it had applying the rubric.

The eleven statements not rated correct, verified at the source by the operator
for two of them:

- Legacy c0013: "only the 38,045,696 memory parameters were ever in the optimizer,
  same as all prior candidates in this arm" — c0011's `memory_config.json` records
  37,849,088 (incorrect, verified).
- Legacy c0018: "steps/epochs were similar to c0011's" — 2550 / 6 vs 2757 / 7
  (incorrect). Legacy c0012 and c0019 misstate an earlier candidate's trajectory
  (incorrect). Five legacy R statements attribute loss trajectories or plateaus to
  candidates whose summaries report only final values (unsupported); one legacy M
  statement mis-orders three siblings' proxy accuracies (incorrect).
- Findings c0014: the parent's initial gate scale is in no artifact (unsupported).
- Findings c0019: "c0018's own Limitations named 16384 as an untested intermediate
  value" — rated unsupported because the rubric strips the `## Finding` section and
  the claim lives there. c0018's Finding section does say it (verified). Under the
  frozen rubric the rating stands; counting it correct would give 1 / 115 = 0.009.

## What this does and does not show

- Workers given finding cards made fewer incorrect or unsupported statements about
  earlier attempts than workers given the first-parent lineage of clipped summaries,
  on this task, seed, world and order. That is the preregistered feasibility
  question, and the answer is yes at the preregistered margin.
- Both base rates are low (one in twenty vs one in sixty statements). The difference
  is nine statements against two; a second seed could move it. Superiority needs
  several seeds (PREREG "What is not claimed").
- The statement mixes differ. Legacy summaries are two to three times longer and
  carry 40 type-R statements; findings summaries carry 2, because their reports about
  others sit in the stripped `## Finding` section and their prose restates card
  numbers (type M, almost all correct). The endpoint therefore compares a
  fact-restating style against a narrative style as much as two memories. The rater
  counted a restated fact once per summary; counting every restatement would inflate
  the legacy denominator more.
- Cross-branch acknowledgment is **not** in the cards' favour under the frozen rule
  (1 vs 2 candidates). A non-preregistered mechanical count over the findings arm's
  raw summaries finds 5 out-of-lineage references, 4 of them inside the stripped
  `## Finding` section (c0007 → c0004, c0008 → c0003 and c0004, c0018 → c0010; c0014
  → c0010 in prose). The stripping rule therefore de-powers this measure against the
  arm the cards were built for; it stays as preregistered here and changes in the
  next preregistration.
- Coverage was not full (STATUS.md): 8 of 16 eligible findings-arm jobs saw fewer
  than two out-of-lineage cards. `opus-review.md` traces it to the selector's
  eviction order and the topical pass consuming every card before the
  "strongest outside this lineage" slot, which then only ever showed the baseline.
  The measured advantage was obtained with a selector that hid 8 of 20 cards from
  everyone; it is a lower bound on what a corrected selector could do, not a
  ceiling.
- Search and final scores (0.885 / 0.811 vs 0.578 / 0.644) are reported in
  STATUS.md because PREREG lists them and are not read as evidence about memory: the
  two drafts differed sharply (`opus-review.md` §5) and the findings arm ran first.

## Procedure as executed

1. 2026-09-14: both `REPORT.md` present, watchers done, checks in STATUS.md.
2. Pack built by `scripts/mem_rating_pack.py` (manifest `rating-MANIFEST.sha256`,
   README `rating-README.md`); verified unchanged after rating.
3. Rater: a fresh Claude session (Fable 5.1, same family as the Sonnet 5 workers)
   given only the pack's README; it did not open `SEAL.json` and reported per letter.
   265 k tokens, 24 min.
4. Unsealed and decided by `scripts/mem_decide.py`; totals recomputed from the
   statement lists and found equal to the rater's.
5. Human spot-check of 10 statements per arm: sample drawn in `spot-check.md`
   (seed 20260914), **not yet done**; disagreements are to be appended here.

Nothing in either arm's directory was modified; the arms' results are still
untracked in their own git repositories.
