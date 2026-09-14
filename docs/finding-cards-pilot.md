# Finding cards — the prompt-size pilot (2026-09-12)

The synthetic pilot that `docs/finding-cards-plan.md` §7 requires before any live
legacy-vs-findings comparison. It measures prompt size only; it says nothing about
whether cards help research. Nothing here was run on a GPU or with a model.

## Method

`scripts/pilot_prompt_size.py <project>` (read-only, no LLM) renders, for every job a
finished campaign dispatched, the prompt the worker actually received — from the
`job.json` snapshot, through the same `render_job_card` that `lab job card` uses — and
counts its tokens and bytes. For a legacy campaign it then builds the finding cards
that `lab run` would have published from the same recorded artifacts (population entry,
`config.json`, `fitness.json`'s search record, `summary.md`), restricted for each job to
the candidates that had settled when that job was dispatched, selects the context with
the same deterministic policy (`select_context`, `max_cards` 8, `max_bytes` 12288), and
renders the prompt the same job would have received under `[memory] mode =
"findings-v1"`: parents' summaries and the lineage replaced by the findings section,
plus the `## summary.md format` section the worker is asked to follow. Two findings
figures bracket the real thing:

- **facts-only**: the cards as they would be built from this campaign's summaries.
  Legacy workers were never asked for a `## Finding` section, so every card carries
  the measured facts and a "worker report: missing" line. A lower bound.
- **filled**: every card's five prose fields at their byte limits (512 bytes each) and
  five shared topics, so the selector admits as many cards as it can and the byte cap
  does the trimming. An upper bound.

Tokenizer: **tiktoken 0.14.0, encoding `cl100k_base`**. This is a proxy; Claude's
tokenizer is not public and its counts differ. Bytes are reported next to every token
figure so the numbers can be re-read under any tokenizer. The prompt measured is the
job card only (task statement, contract, memory, population table); the CLI's own
system prompt and the tool results the session accumulates are not part of it.

Run as:

```
python3 -m venv .venv && .venv/bin/pip install tiktoken
LAB_PRIVATE=~/.local/share/labloop-private .venv/bin/python scripts/pilot_prompt_size.py ../labloop-m2
```

(`LAB_PRIVATE` is needed only so `campaign.toml` expands; no label is read.)

On a campaign that ran with `findings-v1` the script also checks that the context it
rebuilds equals, byte for byte, the snapshot each `job.json` stores; see "Validation".

## Results — M2 (`../labloop-m2`, CIFAR-10, 39 dispatched jobs, legacy memory)

Tokens per job prompt (cl100k_base). "memory part" is what the parents' summaries and
lineage (legacy) or the findings section plus summary-format instructions (findings)
add to the prompt; "population table" is the one-line-per-candidate table, identical
under both policies.

| prompt | per job | memory part per job | population table per job |
|---|---|---|---|
| as dispatched (legacy) | mean 2034, median 2106, max 2641, total 79313 | mean 843, median 912, max 1317, total 32893 | mean 291, median 290, max 568, total 11348 |
| findings, facts-only cards | mean 2563, median 2763, max 2956, total 99958 | mean 1373, median 1502, max 1650, total 53538 | same |
| findings, cards filled to their limits | mean 3642, median 3758, max 4029, total 142029 | mean 2452, median 2567, max 2626, total 95609 | same |

Overhead of the findings prompt over the prompt as dispatched, summed over the 39 jobs:
**facts-only +26.0 %, filled +79.1 %** (about +530 and +1610 tokens per job). The
per-job table is in the script's output; the shape of it:

| job | op | pop | legacy tok (bytes) | findings facts-only tok (cards) | findings filled tok (cards / omitted) |
|---|---|---|---|---|---|
| c0001 | draft | 1 | 858 (3369) | 1242 (1) | 1636 (1 / 0) |
| c0006 | crossover | 6 | 1943 (7130) | 2051 (6) | 3469 (4 / 2) |
| c0013 | improve | 13 | 1686 (6145) | 2550 (8) | 3549 (4 / 4) |
| c0021 | crossover | 21 | 2539 (8655) | 2872 (8) | 3841 (4 / 4) |
| c0032 | improve | 32 | 2292 (7824) | 2955 (8) | 3984 (4 / 4) |
| c0039 | debug | 39 | 2096 (7148) | 2929 (8) | 4002 (4 / 4) |

## Results — M1 (`../labloop-m1`, MNIST, 4 dispatched jobs, legacy memory)

| prompt | per job | memory part per job |
|---|---|---|
| as dispatched (legacy) | mean 1023, median 1119, max 1142, total 4093 | mean 249, max 332 |
| findings, facts-only cards | mean 1333, median 1335, max 1563, total 5331 | mean 558, max 753 |
| findings, cards filled to their limits | mean 2344, median 2350, max 3187, total 9378 | mean 1570, max 2377 |

Overhead: facts-only +30.2 %, filled +129.1 %. Four jobs; the M2 figures are the ones
to plan with.

## What the numbers say

- **The findings prompt is bounded and small in absolute terms.** With cards at their
  limits the memory part plateaus at about 2.6 k tokens (the 12288-byte cap plus the
  ~250-token format instructions) and the whole job card stays under 4.1 k tokens.
  Legacy memory plateaus too (one parent summary clipped to 1200 characters, two for a
  crossover, lineage entries clipped to 400), at about 0.9–1.3 k tokens.
- **The byte cap, not `max_cards`, decides coverage once workers write full-length
  fields.** Facts-only cards are short, so eight cards fit from c0013 on. Filled cards
  are ~2.7 KB each, so the cap admits **four**: the direct parent(s), the nearest
  ancestors, and at most one or two cross-branch cards, with four omitted (listed by id
  in the prompt). If the comparison wants eight cards of cross-branch context, the cap
  must rise to ~24 KB (≈ 5 k tokens of memory) or the field limits must shrink; that is
  a design decision to fix before the comparison, not after.
- **The population table grows linearly, ~14.5 tokens per candidate, under both
  policies.** It is 568 tokens at 39 candidates and would be ~2.9 k at 200. It is not a
  memory-policy effect and should be held identical across arms.
- **Cost of the overhead in session terms.** M2 sessions had a median of 18 turns; the
  job card is re-read on every turn, mostly as cache reads. +530 to +1610 tokens per
  turn is ≈ 10–30 k extra input tokens per session, a few percent of what an 18-turn
  session with tool output consumes. The Max window is budgeted by `[usage]`, not by
  tokens, so this is a small, bounded cost to record, not a blocker.

## Validation of the counterfactual builder

On a campaign that ran under `findings-v1` the script compares the context it rebuilds
with the `findings.rendered` snapshot that `lab run` stored in each `job.json`. Result
on the acceptance suite's findings fixture (`scripts/acceptance_findings.sh`, kept with
`KEEP=1`): see the line "rebuilt findings context equals the stored snapshot" in the
script's output for that project. Result, 2026-09-12, on the fixture campaign
`acc-findings` (9 dispatched jobs, `findings-v1`): **rebuilt findings context equals the
stored snapshot: yes, for every job**, and the facts-only rebuild reproduces the
as-dispatched prompt exactly (+0.0 %). The filled upper bound there is +54 %.

## Inputs for the preregistration (proposed, to be fixed by the human before the comparison)

The plan says these numbers "remain pending until the pilot" and must not be picked or
revised after seeing comparative outcomes. From the figures above, a proposal:

| decision | proposed value | why |
|---|---|---|
| acceptable prompt overhead | findings mean job-card tokens ≤ 2.0 × legacy mean, per campaign, cl100k_base | the filled upper bound is +79 % on M2; real cards will land between +26 % and +79 % |
| memory context cap | keep `max_bytes` 12288 and `max_cards` 8 as implemented, **or** raise `max_bytes` to 24576 to make eight full cards reachable — choose one now | the pilot shows the cap admits four full-length cards; either is defensible, mixing them mid-comparison is not |
| minimum coverage | every job's context contains its direct parent(s) and at least two cards from outside its lineage when at least four cards exist | what the cap leaves at four cards; below this the "cross-branch" claim is empty |
| primary endpoint | fraction of incorrect or unsupported factual statements about prior attempts (fixed rubric, condition-blinded), findings vs legacy | plan §7 |
| improvement threshold | relative reduction of at least one half in that fraction, with at least 40 rated statements per arm | large enough to see in a small campaign; smaller effects are "pending", not "no" |
| sample budget | one legacy and one findings campaign, same task (the M2 CIFAR-10 configuration), same `[selection]` seed, `max_candidates` 20 each, one GPU, sequential | feasibility, not superiority; superiority needs multiple campaign seeds |
| stopping rule | `max_candidates` fixed in both `campaign.toml`s; no early stop, no peeking at the rubric before both finish | the threshold is read once |
| what stays fixed | scheduler, worker model, budgets, task, evaluator, `[usage]` | plan §7: no scheduler or model change rides along |

These are proposals. The comparison starts only after the human writes the chosen
values into the two `campaign.toml`s and this document, in that order.

## Fixed values (2026-09-13)

The human fixed the open choice on 2026-09-13: **keep `max_bytes` 12288 and
`max_cards` 8**; a larger cap is a later comparison if this one shows the cap as the
limitation. The other proposals above were adopted as proposed, with one substitution:
the testbed is the engram world w0 (`../labloop-engram`, ~12 min and ~$0.5 per
candidate) instead of the M2 CIFAR-10 configuration, `max_candidates` 20 per arm.
The frozen preregistration, rubric and order are `docs/memory-comparison-20260913/`
(copies of `../labloop-engram-mem-20260913/{PREREG.md,ORDER.json}`); the arms are
`../labloop-engram-mem-findings-20260913` (first) and
`../labloop-engram-mem-legacy-20260913` (second), neither launched at the time of
writing.
