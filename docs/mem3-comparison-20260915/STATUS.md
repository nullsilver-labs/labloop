# mem3 comparison — status (2026-09-15, evening)

Bundle `../labloop-mem3-20260915` (`PREREG.md`, `ORDER.json`: findings first, drawn;
`LAUNCH.md`). Arms `../labloop-mem3-findings-20260915` and `../labloop-mem3-legacy-20260915`,
clones of `labloop-engram` c31d39b with tools from labloop `7243bcb`, seed 4, two GPUs,
Sonnet only.

**Update 2026-09-16: both arms have finished; the mechanical read of the pair and the rating pack are below, the decision is in `RESULT.md`.** (Written 2026-09-15 evening:) **The findings arm ran and finished; the legacy arm has not been launched.** The
comparison is **pending** by the preregistration's own rule (both `REPORT.md` files must
exist before any rubric work). Nothing below reads a summary for rating; it is the
mechanical part of the read, done on the one arm that exists, so that the second arm is
launched knowing the first is usable.

## Arm 1 — findings-v3 (`engram-mem3-findings-w0`)

Ran 2026-09-15 12:20–14:53Z under its `--op campaign` watcher (done, 600-min budget,
no kill). Facts from `REPORT.md`, `population.json` and the candidate dirs:

| | |
|---|---|
| settled | 20 of 20, all `completed`; 0 invalid, failed, killed or deferred |
| stop reason | `max_candidates 20 reached` |
| frozen candidate | c0005 (improve of c0000), search 0.7499, **final 0.7504 vs 0.50: supported** |
| best search after 8 / 20 | 0.7499 (c0005) / 0.7499 |
| GPU-hours (lease) | 4.68 of 8; 4.28 settled per lease-hour; wall 2.55 h → 7.8 per wall-hour |
| served model | 19 of 19 sessions `claude-sonnet-5` (+ the CLI's `claude-haiku-4-5-20251001` helper); baseline ran no session |
| sessions | turns median 21, max 32; list-price equivalent $15.46, median $0.75 |
| usage | no pause, no rate-limit message, no deferral |
| labels | `labeval` on; the final split read once by `lab run` |
| GPU as covariate | GPU 0: 11 candidates, best search 0.7227 (c0017); GPU 1: 9 candidates, best 0.7499 (c0005, the frozen one) |
| disguised drafts | c0005 and c0014 are improves of c0000 (both listed as opening approaches, as the earlier reads did) |

**Finding-card coverage: full.** Every job's context held its direct parent(s). From the
first job with four or more cards on (c0005), every job held at least two cards from
outside its own ancestry (2–5). c0004 held one (its parent c0001 and the strongest other
branch, c0003); only three non-baseline candidates had ended when it was dispatched, so
the four-card rule did not yet apply. No selector violation.

**The knob index saturated — reported, as the preregistration says, without a threshold.**

| job | settled non-baseline before it | knob keys in the index | bytes | values elided |
|---|---|---|---|---|
| c0002–c0006 | 1–4 | 9–12 | 907–1593 | 0 |
| c0007–c0012 | 5–10 | 13–19 | 1748–1961 | 0 |
| c0013 | 11 | 19 | 2040 | 3 |
| c0014 / c0015 / c0016 | 12 / 13 / 14 | 19 | 2038 / 2026 / 2026 | 4 / 8 / 11 |
| c0017 / c0018 / c0019 | 15 / 16 / 17 | 19 | 2086 / 2093 / 2130 (`over_budget`) | 11 / 12 / 13 |

The replay over mem2 had predicted 0–1664 bytes and no elision at 20 candidates. It did
not hold because the mem3 workers configured 19 knob keys where mem2's configured 9,
and four of the new keys are not knobs: `last_logged_loss`, `last_logged_step`,
`last_logged_epoch`, `last_logged_elapsed_s`, the training log's last line copied into
`out/memory_config.json`. The outcome filter (`OUTCOME_KEYS`, `OUTCOME_PREFIXES`) did not
know that family, so they took index bytes and, being different in every candidate,
were the first values elided — followed by real knobs (`weight_decay` lost 3 values by
the last job, `train_seconds` 2, `attach_layer`, `decoding`, `ngram_orders`,
`table_rows`, `table_structure`, `tie_break`, `weight_decay_scope` 1 each). Whole knobs
were never elided and every candidate stayed named in the index, so the failure mode is
"the oldest value of a knob is missing", the softest one v3 was designed to fall to.
Whether a late worker then made a wrong "never varied" claim is a rating question, for
after arm 2.

Fixed on main the same evening, outside the pair (the legacy arm does not render an
index and keeps its `7243bcb` tools): `last_logged_*` and `logged_*` join the outcome
prefixes, with the acceptance case extended. The general problem — a byte-bounded index
over worker-chosen keys saturates at a dozen candidates — is not fixable by a prefix and
is the subject of `docs/experiment-index-plan.md`.

## Arm 2 — legacy (`engram-mem3-legacy-w0`): ready, not launched

Checked 2026-09-15 evening: `SHA256SUMS` of the bundle verify (55 files, all OK), the two
`campaign.toml` files differ only in the header comment, `[campaign].id` and `[memory]`
(`diff`), `LAB_PRIVATE=/srv/labloop-private tools/lab campaign check` passes with only the
accepted no-`window_budget` warning, no watcher runs in any sibling project, both GPUs
idle, no LLM server on either card. The launch is the arm-2 block of `LAUNCH.md`, by hand.

Two things compete for the same cards after arm 2: the next campaign on a local model
needs GPU 0 for the model server and GPU 1 for training (`../labloop-pi-engram-20260915`),
so it cannot overlap with an arm that holds both locks. Arm 2 first (≈ 2.5 h on two
slots), then the local-model campaign.

## After both reports exist

As `PREREG.md`: `scripts/mem_mechanical.py --findings ../labloop-mem3-findings-20260915
--legacy ../labloop-mem3-legacy-20260915 --prompt-bound 2.2` with the prompt-size JSONs,
then the rating pack (`scripts/mem_rating_pack.py --keep-finding --rubric-from
../labloop-mem2-20260914/PREREG.md`), a fresh rater session, the sealed letters, the
human's 10-per-arm spot check, `mem_decide.py`, `RESULT.md` here. The decision rule
(ratio ≤ .50 at ≥ 40 rated M+R per arm) and the consequence of a second `not_supported`
(accuracy claim dropped for this task, cards kept for acknowledgment and replications, no
fourth seed) were fixed before arm 1 ran and do not move. The three-seed description is
reported beside it, never pooled.

## Arm 2 — legacy (`engram-mem3-legacy-w0`): ran 2026-09-15 18:52–21:25Z

Under its `--op campaign` watcher (done, 600-min budget, no kill). Facts from `REPORT.md`,
`population.json` and the candidate dirs:

| | |
|---|---|
| settled | 20 of 20, all `completed`; 0 invalid, failed, killed or deferred |
| stop reason | `max_candidates 20 reached` |
| frozen candidate | c0009 (improve of c0005), search 0.7712, **final 0.8611 vs 0.50: supported** |
| best search after 8 / 20 | 0.5988 (c0005) / 0.7712 (c0009) |
| GPU-hours (lease) | 4.45 of 8; 4.49 settled per lease-hour; wall 2.53 h → 7.9 per wall-hour |
| served model | 19 of 19 sessions `claude-sonnet-5` (+ the CLI's `claude-haiku-4-5-20251001` helper); baseline ran no session |
| sessions | turns median 24, max 47; list-price equivalent $14.58, median $0.69 |
| usage | no pause, no rate-limit message, no deferral |
| labels | `labeval` on; the final split read once by `lab run` |
| GPU as covariate | GPU 0: 10 non-baseline candidates, best search 0.7150 (c0015); GPU 1: 9, best 0.7712 (c0009, the frozen one) |
| disguised drafts | c0003 (crossover c0001 × c0000) |

The two arms' finals (F .750, L .861) are not memory evidence: one seed, one draft each,
and the drafts pair showed a single draft roll moving the final by .15.

## Mechanical read of the pair (2026-09-16)

`mechanical.md` / `mechanical.json` from `scripts/mem_mechanical.py --prompt-bound 2.2`
with `prompt-size-{findings,legacy}.json` from `scripts/pilot_prompt_size.py` (tiktoken
0.14.0 `cl100k_base`, a proxy). **Both scripts were run from a checkout of labloop
`7243bcb`, the commit the arms' tools were synced from**: main's tools refuse to render the
findings arm's job cards because the `last_logged_`/`logged_` outcome prefixes added on
2026-09-15 evening differ from the prefixes frozen in that arm's `population.json`, which is
the intended guard ("a tooling update must not change a running campaign's memory"). The
scripts themselves are unchanged between `7243bcb` and main (`git log`).

| measure | findings (F) | legacy (L) |
|---|---|---|
| settled non-baseline / exec | 19 / completed 20 | 19 / completed 20 |
| stop reason | max_candidates 20 | max_candidates 20 |
| served models, sessions that ran | Sonnet 5 (+ Haiku helper): 19 | same: 19 |
| sessions that never ran | none | none |
| GPU-hours / wall h | 4.68 / 2.55 | 4.45 / 2.53 |
| settled per lease-hour / per wall-hour | 4.28 / 7.8 | 4.49 / 7.9 |
| lease s − recorded training s, median (19 jobs) | 346 | 346 |
| best search after 8 / after 20 | .7499 / .7499 | .5988 / .7712 |
| frozen → final (one read, vs .50) | c0005 → .7504 supported | c0009 → .8611 supported |
| job-card tokens mean (median, max) | 5354 (5949, 6440) | 2778 (2859, 3310) |
| prompt ratio F / L | **1.93 ≤ 2.2**: within the bound | |
| coverage (F) | parent violations 0; out-of-lineage rule: 1 miss, c0004, the single-draft opening (predicted) | — |
| deferrals, pauses | 0, 0 | 0, 0 |

Mechanical pending reasons: **none**. Both arms ≥ 10 settled non-baseline, neither ended
early, served models identical. Coverage under v3 is full apart from the c0004 opening
miss the preregistration names. Throughput, the M4 look: two slots, and the lease overhead
over training is the same 346 s median in both arms, so the memory policy did not change
what a slot costs; the mem2 single-GPU figures (4.72 / 5.45 per lease-hour) stand beside
these for the record.

The prompt ratio at the third seed (1.93) is above the second's (1.85) and the first's
(1.74): the v3 index at its 2 KiB bound plus the measured lines. Facts-only cards would
have been 4723 tokens mean under this arm's own summaries (the pilot's counterfactual),
so the v3 card is 13 % over its facts-only lower bound.

## Rating pack (built 2026-09-16 10:29Z)

`scripts/mem_rating_pack.py --keep-finding`, run from the same `7243bcb` checkout, at
`../labloop-mem3-20260915/rating/` (copies here: `rating-README.md`,
`rating-MANIFEST.sha256`, 272 files). Pack A and pack B: 19 candidate records each; 5 and
1 verbatim job-card sentences flagged. Letters drawn with `secrets`, `SEAL.json` mode 600,
read only after both `ratings/*.json` exist.

**One deviation from the line in this file's first version, recorded:** `--rubric-from`
was given `docs/memory-comparison-20260913/PREREG.md`, not the mem2 PREREG. The mem2 file
carries the unit, types and ratings forward *by reference* to the 2026-09-13 file (it has
no `**Unit.**` paragraph of its own), and the builder inlines only a file that defines
them; the mem2 pack was completed from the same 2026-09-13 paragraphs (mem2 STATUS.md).
The rubric text the rater sees is therefore the one every pair has used. A first build
attempt with the mem2 file failed at the README step after writing `pack/`; that partial
directory was removed and the pack built once, cleanly, into the same path.

Rater: a fresh Opus session given only the pack README, as in mem2 (the preregistration
asks for a model of the workers' family; Opus is what the two earlier pairs used, so the
rater is held constant across the three seeds).

**Rated 2026-09-16 10:33–10:55Z; decision in `RESULT.md`: supported** (findings .042 vs
legacy .109, ratio .39). Five rated-bad statements verified at the source by a second
session, all five upheld. Human spot check open (`spot-check.md`).
