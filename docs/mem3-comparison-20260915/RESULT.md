# Legacy vs finding cards (v3), third seed — result (2026-09-16)

Read once, after both arms had written `REPORT.md`, against the rule frozen in
`../../../labloop-mem3-20260915/PREREG.md` before either arm was launched. `STATUS.md`
holds the run facts, the mechanical measures and the two procedural notes of this read
(the tool version used for the mechanical pass, the file the rubric was inlined from); this
file holds the primary endpoint and the decision.

## Decision: **supported**

`scripts/mem_decide.py` over the blinded rater's `ratings/A.json` and `B.json`,
`ratings/SEAL.json` (A = findings, B = legacy, drawn with `secrets` by
`scripts/mem_rating_pack.py --keep-finding`) and `mechanical.json`; output `decision.json`
/ `decision.md`.

| | findings arm (pack A) | legacy arm (pack B) |
|---|---|---|
| fraction_bad over M+R (bad / rated) | **0.042** (9 / 213) | **0.109** (28 / 258) |
| M: correct / incorrect / unsupported | 187 / 6 / 3 | 200 / 22 / 5 |
| R: correct / incorrect / unsupported | 17 / 0 / 0 | 30 / 0 / 1 |
| C (reported, not the endpoint): correct / incorrect / unsupported | 1 / 0 / 5 | 1 / 0 / 5 |
| unrated (reason listed) | 6 | 6 |
| candidates with a cross-branch acknowledgment | 13 | 3 |
| unacknowledged repeats / acknowledged repeats | 1 / 6 | 1 / 3 |

fraction_bad findings / legacy = **0.39**; supported needed ≤ 0.50. Both arms have ≥ 40
rated M+R statements, 19 settled non-baseline candidates, ended at their candidate cap and
were served the same models, so no pending clause applies. Every rated statement is quoted
with its source and note in `ratings/*.json`; `ratings/SUMMARY.md` is the rater's own
report, including the conventions it adopted where the rubric was silent.

**Verified at the source by a second, independent session** (Sonnet, given only the pack
and five statements): findings c0009's "c0001–c0006, all below 0.26 search" (c0003 .7427,
c0005 .7499), findings c0016's placing c0009 in the free-form-decoding lineage (c0009 is
the candidate that moved it to closed-vocab scoring), legacy c0005's "wording 7 was seen
during training" (the split withholds wording 7 for every entity), legacy c0017's "~90 % of
the gap" (71 % from the recorded held-out numbers), legacy c0014's loss attributed to
c0002 (it is c0006's). The rater was right in all five.

**The rater's own sensitivity check**, reported in `SUMMARY.md`: six of the legacy arm's
28 bad statements are time-relative superlatives ("best so far") for which the rubric
names no dispatch-time source; the rater checked them against every lower-id candidate and
flagged the concurrency caveat. Dropping all six leaves legacy at 22 / 252 = 0.087 against
findings 0.042, ratio 0.48, still under the bar.

## What the bad statements are

- **Legacy (28).** Seven repeat one wrong description of the shared held-out metric (a
  "known template, unseen entity" split, when the code withholds one template for every
  entity; two legacy candidates, c0015 and c0019, state it correctly, so the arm contradicts
  itself across the lineage). Six "best in the population / best so far" claims that
  `records.json` contradicts. Seven misquoted parent numbers or arithmetic slips (a step
  count attributed to the parent, a loss attributed to the wrong sibling, "matching or
  exceeding" for +0.0805 against +0.1101, "~90 %" for 71 %). Four unsupported claims. The
  legacy pattern of the first two pairs: long narrative comparisons with small slips, and
  here one inherited misreading copied down the lineage.
- **Findings (9).** Three unverifiable range claims about the knob index (the index the
  worker saw is not in the pack, so the rater could not confirm them), one "seed and
  weights unchanged from the parent" claim, one wrong table-size attribution, one "all
  below 0.26" that two candidates at .74 contradict, one lineage mis-assignment, and two
  claims about a sibling's scorer, one of which the same summary later corrects. **No
  "never varied" claim about a knob was rated bad in this arm.** At seed 2, eleven of the
  findings arm's eighteen bad statements were exactly that, and the v3 index was built to
  carry the contradicting fact; at this seed the index saturated from the 13th candidate
  (`STATUS.md`) and elided the oldest values of nine knobs, and the workers still made no
  rated "never varied" error. The three unverifiable range claims are the closest thing,
  and they are rated unsupported, not incorrect.

## Three seeds, side by side, never pooled

| pair | seed | order | selector / ledger | findings | legacy | ratio | read |
|---|---|---|---|---|---|---|---|
| memory (2026-09-13) | 1 | findings first | v1, no ledger | .017 (2 / 115) | .047 (9 / 191) | .37 | supported |
| mem2 (2026-09-14) | 2 | legacy first | v2, per-candidate ledger, 2 KiB | .095 (18 / 190) | .060 (15 / 252) | 1.59 | not_supported |
| mem3 (2026-09-15) | 4 | findings first (drawn) | v3, per-knob index, measured line | .042 (9 / 213) | .109 (28 / 258) | .39 | supported |

Two of three single-seed pairs read supported under the same rule; the one that did not is
the one whose ledger provably lacked the facts (`docs/mem2-comparison-20260914/RESULT.md`).
The preregistration fixed the consequence of a second not_supported (accuracy claim
dropped, no fourth seed); it did not fix a consequence of a second supported, and none is
claimed here beyond the row. Across the three pairs the cards moved cross-branch
acknowledgment every time (12 / 3, 12 / 3, 13 / 3 candidates) and named replications in
the two pairs that counted them.

## What is not claimed

One world, one drawn order per pair, partial blinding (the `## Finding` heading), a
same-family rater held constant across the pairs (Opus), a rubric applied by one rater per
pair, and no pooled test. The final scores (findings .750, legacy .861 at this seed) are
not memory evidence. This pair cannot show that better memory yields better science; it
shows that at a third seed, with a ledger that carries the facts, workers under finding
cards made fewer wrong statements about earlier work than workers under the legacy
lineage, by the preregistered margin.

## Open

- The spot check: 10 statements per arm drawn with seed 20260916 before unsealing
  (`spot-check-sample.json`, sheet in `spot-check.md`). On 2026-09-17 the human decided to
  have a second blinded Opus rater do it in place of the human check the PREREG names (a
  deviation, stated as one): 20 of 20 ratings agree, 19 of 20 types
  (`spot-check-second-rater.md`). The decision is unchanged.
- The index saturation is the reason for `docs/experiment-index-plan.md`; this result does
  not change that plan's order, it removes the urgency of a fourth memory seed.
