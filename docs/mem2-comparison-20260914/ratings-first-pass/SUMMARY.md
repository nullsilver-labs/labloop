# Blinded rating — arms A and B (rated 2026-09-15)

Rated from `rating/pack/` only, against the rubric frozen in `rating/README.md`.
`SEAL.json` was not opened; no campaign directory, `REPORT.md`, `finding.json`,
`job.json`, label file or final-split score was read. Report is per letter; no
guess about which memory each arm used appears anywhere in these files.

The `## Finding` sections present in one arm's summaries were **kept** and their
statements about earlier candidates extracted and rated by the same rules as any
other prose, as the README's rubric requires.

## Arm A

Candidates in pack: c0001–c0020 (20; c0008 left no worker summary — deferred on the
usage limit per `records.json`).

| type | correct | incorrect | unsupported | total |
|---|---|---|---|---|
| M (lab record / config / code) | 151 | 7 | 1 | 159 |
| R (what an earlier summary said) | 17 | 0 | 1 | 18 |
| C (interpretation / causal) | 15 | 1 | 0 | 16 |
| **all** | 183 | 8 | 2 | **193** |

- `rated_MR` = 177, `bad_MR` = 8 + 1 = 9, **`fraction_bad` = 0.0508**.
- C counted separately (1 incorrect, not in `fraction_bad`).

Bad M/R statements (candidate → what was wrong):

- c0004 — "c0004 loss 0.6200 vs the loss level c0003 reported around the same step
  count" (unsupported: c0003's summary reports no mid-training loss at that step).
- c0006 — "`engram_memory.py` … was not touched — same as c0004's relationship to
  c0003" (incorrect: c0004 did change it — dropout default and `attach_memory`
  signature).
- c0009 — "higher than every dropout value in the c0001→c0002→c0003→c0005 lineage"
  (incorrect: c0002's held-out 0.5034 > c0009's 0.4856).
- c0012 — "going past 0.4 was never tested" (incorrect: c0005 ran dropout 0.6).
- c0015 — three: "the smaller table … was only tested up to 0.4 too" (c0005 tested
  0.6); "this 520k-row table" (c0012's table is 500,000 rows); "a larger drop than
  c0002→c0003's 0.503→0.404 in relative terms" (it is a smaller drop, −9.6 % vs
  −19.7 %).
- c0019 — "same caveat c0017 itself noted about seed effects" (unsupported: c0017's
  summary notes no seed-effect caveat).
- c0020 — "c0010 scored 0.632 … versus c0005's 0.325 — a 2.5× gap" (incorrect: 1.94×).
- C-type incorrect (not in `fraction_bad`): c0005 — "the held-out-wording signal …
  tracked hidden-split fitness directionally for c0001→c0002→c0003" (it did not on
  the c0002→c0003 leg).

**Unrated: 4** — reference-run scores from `$LAB_TRAIN/reference/RESULTS.md` (not
candidates, source not in pack); c0008's mechanically copied session-limit text (not
worker prose about a prior attempt); a claim about `task.md`'s 2 M-row remark; a claim
about `facts.json`/`questions.json` name tokenisation (data not in pack).

**Cross-branch acknowledgment** (named candidates that are neither parent nor
ancestor): c0001 → c0000 (the baseline, named but unrelated); c0007 → c0006;
c0013 → c0012. Every other candidate named only its parents and ancestors.
**2 genuine cross-branch references** (3 counting the baseline mention).

**Unacknowledged repeats: 4**

| candidate | repeats | knob and direction |
|---|---|---|
| c0015 | c0005 | dropout 0.4 → 0.6 (raise) |
| c0017 | c0014 | TABLE_ROWS 500,000 → 2,000,000 (4× raise) |
| c0018 | c0005 (and sibling c0015) | dropout 0.4 → 0.6 (raise) |
| c0020 | c0012 | add dropout 0.4 on top of c0010's shared-table architecture |

No intentional, named replications were found in this arm.

## Arm B

Candidates in pack: c0001–c0019 (19, all with summaries).

| type | correct | incorrect | unsupported | total |
|---|---|---|---|---|
| M (lab record / config / code) | 135 | 13 | 1 | 149 |
| R (what an earlier summary said) | 4 | 0 | 2 | 6 |
| C (interpretation / causal) | 3 | 0 | 0 | 3 |
| **all** | 142 | 13 | 3 | **158** |

- `rated_MR` = 155, `bad_MR` = 13 + 3 = 16, **`fraction_bad` = 0.1032**.
- C counted separately (none bad).

Bad M/R statements:

- c0002 — "c0001's summary flagged the gap between its local held-out accuracy and
  its hidden search score as unexplained" (unsupported: c0001's summary contains no
  hidden score); "loss is noisy near convergence as in c0001" (unsupported).
- c0005 — "up from c0003's 14.1M" (c0003 has 15,166,720 trainable params).
- c0006 — "28.2M trainable params, double c0003's 14.1M" (wrong figure, and 1.86×);
  "the highest held-out accuracy seen in this lineage (previous best was c0001's
  0.8562)" (c0002's 0.8723 was higher).
- c0008 — "No candidate in this lineage (c0001–c0007) had ever varied `orders` away
  from its default `[1]`" and "This candidate is the first to pass `--orders 1 2`"
  (c0001 ran [1,2,3]; c0002 ran [1,2] — the exact configuration claimed as new).
- c0009 — "c0003 itself scored best on hidden search" (c0006 0.7443 > c0003 0.6837
  by then); "a bare seed change alone can swing hidden search score by >0.08 (c0006
  vs c0008)" (c0008 differs from c0006 by the `orders` knob, not only the seed).
- c0011 — "still below c0003's 0.8145" (0.8293 is above it).
- c0014 — "every 540s run in the ledger so far also used heads=8" (c0011 ran 540 s
  with heads=4).
- c0015 — "c0009 vs c0003's seed-only delta" (c0009 also added weight_decay 0.01).
- c0017 — "attach_layer 4 … the only other point on the depth axis measured so far"
  (layer 6 was measured by c0007 and c0012); "c0016 … produced the single largest
  jump in the ledger (+0.0668)" (c0005→c0006 was +0.0926, and earlier jumps larger
  still; the "current best score 0.8110" half is right).
- c0019 — "no candidate in the ledger has ever varied `weight_decay`" (c0009 and
  c0014 both ran 0.01); "batch_size … a knob+direction already fully explored in both
  directions" (unsupported — it was only ever raised).

**Unrated: 5** — claims about the task data/tokenizer (name token counts, vocab size,
unique name words) that name no prior candidate and cannot be checked from the pack;
one forward-looking prediction about the candidate's own run; one hardware-utilisation
speculation.

**Cross-branch acknowledgment** (named candidates that are neither parent nor
ancestor), by candidate: c0003 → c0002; c0005 → c0002, c0004; c0006 → c0002, c0004;
c0007 → c0002, c0004; c0008 → c0002, c0004, c0007; c0009 → c0002, c0006, c0008;
c0011 → c0005, c0006, c0007, c0008, c0010; c0012 → c0010; c0013 → c0012;
c0014 → c0005, c0006; c0015 → c0009; c0017 → c0016; c0018 → c0010, c0017.
**13 of 19 candidates make at least one cross-branch reference.**

**Repeats: 5, of which 2 unacknowledged**

| candidate | repeats | knob and direction | acknowledged |
|---|---|---|---|
| c0008 | c0002 | `orders` set to [1,2] (c0002 by dropping order-3, c0008 by adding order-2) | no — and explicitly claimed as never tried |
| c0011 | c0006 | train_seconds 360 → 540 (raise) | yes, with a stated reason |
| c0014 | c0006 | train_seconds 360 → 540 (raise) | yes, with a stated reason |
| c0017 | c0016 | batch_size 32 → 64 (raise) | yes, with a stated reason |
| c0019 | c0009 (also c0014) | weight_decay 0.0 → 0.01 (add) | no — explicitly claimed as a new knob |

(c0018's batch_size raise repeats its own parent c0016's direction, so by the rubric's
"earlier non-ancestor" wording it is not counted; it names c0016 and c0017 anyway.)

## Comparison as numbers only

| | A | B |
|---|---|---|
| statements extracted | 193 | 158 |
| rated M+R | 177 | 155 |
| bad M+R | 9 | 16 |
| **fraction_bad** | **0.0508** | **0.1032** |
| unrated | 4 | 5 |
| cross-branch references | 2 (3 with the baseline mention) | 13 candidates, 26 references |
| unacknowledged repeats | 4 | 2 |
| settled non-baseline candidates with summaries | 19 | 19 |

Both arms clear the rubric's 40-rated-M+R floor. No decision is applied here; the
operator unseals and applies the preregistered rule.

## Difficulties applying the rubric

1. **The M/R/C definitions are not restated in the pack.** The README carries the
   rubric forward "verbatim" but names the types without defining them; the first pack's
   `PREREG.md` is outside the readable directory. I used the definitions implied by the
   README's own "What is in the pack" section: **M** = checkable against the lab's
   record or a candidate's artifacts (`records.json`, `config.json`,
   `memory_config.json`, `code/`); **R** = a claim about what an earlier candidate's
   `summary.md` says; **C** = an interpretation, causal reading or cross-candidate
   inference that no single source settles. A spot-check disagreement here would most
   likely be about M-vs-C on cross-candidate arithmetic (e.g. "X's drop was larger than
   Y's in relative terms"), which I typed **M** whenever it reduces to numbers in the
   sources, and **C** only when it asserts a mechanism or a trend's meaning.

2. **Unit granularity in comparison tables.** Arm A's summaries carry multi-column
   tables of a parent's steps/epochs/examples/loss/accuracy/timings. Counting each cell
   as a unit would have inflated A's count several-fold against B's prose. I counted
   **one statement per prior-candidate column**, rated `correct` only if every cell in
   it matches the source, and this policy is applied identically to both arms. Prose
   restatements of a value already counted in the same summary were not double-counted;
   the same fact repeated in a *different* candidate's summary was counted again.

3. **"This lineage" vs "the ledger".** Several B statements claim a knob was never
   tried. Whether they are false depends on whether "lineage" means the candidate's own
   ancestry or the whole population. Where a sentence said "the ledger" or "any
   candidate", I rated against the whole population; where it said "this lineage" and
   was true of the direct ancestry, I rated it `correct` with a note (c0019's
   weight_decay Finding line is the clearest case — its neighbouring "ledger" sentence
   is rated incorrect while the "lineage" one is rated correct).

4. **Claims a worker could not have known.** Some errors are about candidates the
   worker's read contract may have excluded (A/c0012's "going past 0.4 was never
   tested" — c0005 had tested it; B/c0008's orders claim). The rubric rates accuracy
   against the sources, not culpability, so these are rated incorrect regardless of what
   the worker was allowed to read. This is worth flagging because it can penalise an arm
   whose job cards give it less visibility.

5. **Rounding and transcription.** B/c0010 quotes c0007's fitness as 0.725341875
   against a recorded 0.725341796875 (~1e-7 off, delta correct). I treated
   rounding/transcription at that scale as `correct` with a note, rather than incorrect.

6. **Blinding is partial, as the prereg says.** One arm's summaries carry a `## Finding`
   heading and "ledger"/"knob ledger" language that the other's do not. I made no
   inference from that and recorded no guess; but the asymmetry is visible, and one arm's
   Finding sections are shorter, denser prose, which changes unit density independently
   of accuracy.

7. **Statements about a candidate's own run were excluded** throughout, including the
   Finding sections' "Local observation" lines, which are almost entirely self-reports.
   Where such a line also compared to a parent ("… vs c0006's 0.0914"), the comparison
   half was extracted as a unit.
