# Preregistration — legacy vs finding cards, engram world w0 (2026-09-13)

Written 2026-09-13T16:30Z, before either arm was launched, from the proposals in
labloop `docs/finding-cards-pilot.md` ("Inputs for the preregistration") and the plan
`docs/finding-cards-plan.md` §7. Nothing here changes after the first launch; a
change is a new comparison. The human's one decision on the pilot's open choice:
**keep `max_bytes` 12288 and `max_cards` 8** as implemented (labloop `21d40df`,
constants in `tools/lab_findings.py`); a larger cap is a later comparison if this one
shows the cap as the limitation.

## The question

Does the finding-card memory (`[memory] mode = "findings-v1"`) make workers more
accurate about earlier attempts than the legacy memory (first-parent lineage of
clipped summaries, plus the population table), at the same task, scheduler, model and
budgets? This first comparison establishes **feasibility, not superiority**: one
campaign seed, one world, one order. Superiority needs several seeds.

## The two arms

| | findings arm | legacy arm |
|---|---|---|
| project | `../labloop-engram-mem-findings-20260913` | `../labloop-engram-mem-legacy-20260913` |
| campaign id | `engram-mem-findings-w0` | `engram-mem-legacy-w0` |
| `[memory].mode` | `findings-v1` | `legacy` |

Everything else is byte-identical between the two `campaign.toml`s (`diff` shows the
id line, the mode line and the header comment) and identical to `engram-pilot-w0`
except: `max_candidates` 8 → **20**, `gpu_hours_total` 3 → 8, `[stop].wall_clock`
6h → 9h. `task.md`, `data/`, `eval/`, the world (w0) and the labels
(`/srv/labloop-private/engram-pilot-w0/{search,final}`, read by `labeval`) are those
of `engram-pilot-w0`. Tools: labloop `21d40df` in both arms (`selection.draft_p`
exists at that revision and stays at its default 0). Worker model `claude-sonnet-5`,
`worker_max_turns` 40, `[selection]` seed 1, temperature 0.3, crossover 0.15, one GPU
(the RTX 3090, id 0), `[usage]` unchanged, governor detection-only as in w0.

Why engram, not the pilot's proposed M2 CIFAR-10 configuration: a candidate costs
~12 min and $0.5, an arm fits one usage window, and `engram-pilot-w0` produced a
concrete instance of the failure the cards target (c0003 and c0004 both tried weight
decay on the proj/gate heads from the same parent, neither aware of the other). This
choice and the candidate count were fixed after reading w0's report and before
launching either arm; w0's candidates are not visible to either arm's workers, and no
worker in any campaign sees labels.

## Order and running

`ORDER.json`: one `secrets.randbits(1)` draw at 2026-09-13T16:25:49Z, bit **1**:
**findings first, legacy second**, sequential on GPU 0 under `gpu0.lock`. No redraw,
no swap. Each arm runs under its own `--op campaign` watcher (LAUNCH.md).

Stopping rule: `max_candidates` 20 in both files, no early stop, no rubric work before
both arms have written `REPORT.md`. A job deferred by the usage window is re-dispatched
by the loop as usual. If an arm ends early (watcher budget, `campaign stop`, a card
error), it is reported as it ended; the comparison is then **pending**, not a result.

## Primary endpoint — factual accuracy about prior attempts

**Unit.** A *statement about a prior attempt* is one sentence or clause in a
candidate's `summary.md` that asserts something about a specific earlier candidate of
the same campaign (named by id, or unambiguously as "my parent" / "the sibling that
tried X") or about the campaign's earlier attempts collectively ("every prior run
reached loss ~1e-3"). Statements about the candidate's own run are not units.
Statements copied verbatim from the job card are not units. The `## Finding` section
of a findings-arm summary is stripped before extraction (it is the worker's card,
not prose about others).

**Types.** Each statement is labelled once:
- **M — measured fact**: a number or outcome that exists in the earlier candidate's
  artifacts (`summary.md` local numbers, `config.json`, `out/memory_config.json`,
  `code/`) or in the lab's records (`population.json` search fitness, exec status,
  parents, operator).
- **R — worker report**: what the earlier summary said it changed, hypothesised,
  observed or concluded.
- **C — causal claim**: why the earlier result happened, or what it implies.

**Ratings.** Against the sources above (never `finding.json`, never labels, never the
final split): **correct** (the source says it), **incorrect** (the source contradicts
it), **unsupported** (no source can confirm it, including attributing to a candidate
something none of its artifacts contain). A statement giving a hidden search score is
rated against `population.json`; a statement giving a local number against that
candidate's own summary or `out/`.

**Endpoint.** Per arm, over types M and R only:
`fraction_bad = (incorrect + unsupported) / rated`. Type C is counted and reported
separately (correct / incorrect / unsupported by the same rule, but its accuracy is
not the endpoint). Omissions and cross-branch acknowledgment are reported separately
(below), so silence cannot win on accuracy.

**Decision.** Read once, after both arms finish:
- **supported** if `fraction_bad(findings) ≤ 0.5 × fraction_bad(legacy)` with at
  least 40 rated M+R statements in each arm;
- **pending** if either arm has fewer than 40 rated M+R statements, or fewer than 10
  settled non-baseline candidates, or ended early;
- **not_supported** otherwise. A smaller reduction is reported as a number, not as a
  claim either way.

**Rating procedure and blinding.** Extraction and rating are done after both reports
exist, by a fresh operator session that did not run either arm, on a pack built by a
script from both projects: per candidate, `summary.md` with the `## Finding` section
removed, and the source artifacts of every earlier candidate it names. Arm labels are
replaced by `A`/`B` (assignment recorded in a sealed file read only after rating) and
`finding.json` files are excluded from the pack. Blinding is partial: prose may
mention "cards". The rater is a language model of the same family as the workers; the
human spot-checks 10 rated statements per arm, and any disagreement is reported with
the rating. The rubric above is frozen; a statement it does not cover is listed as
unrated with the reason, never rated ad hoc.

## Secondary measures (reported, no threshold)

- **Unacknowledged repeats**: candidates whose stated single change is the same knob
  and direction as an earlier non-ancestor candidate's, without naming it. Intentional
  replications (named, with a reason) are counted separately.
- **Prompt cost**: mean job-card tokens per arm, `tiktoken` `cl100k_base` over
  `lab job card <dir>` output (labloop `scripts/pilot_prompt_size.py` method).
  Acceptance bound from the pilot: findings mean ≤ **2.0 ×** legacy mean.
- **Coverage (findings arm)**: from `job.json`, every job's context contains its
  direct parent(s) and, once at least four cards exist, at least two cards from outside
  its lineage. Violations are counted; below full coverage the cross-branch reading is
  weakened and said so.
- **Valid candidates per GPU-hour** and **completed / invalid / failed / killed /
  deferred** counts per arm.
- **Search progress**: best search fitness after candidates 8 and 20 per arm, and the
  final-split score of each arm's frozen candidate (read once by `lab run`, as always).
  Each arm's task claim reads against the same fixed 0.50 as w0. A higher final score
  is not evidence of better memory and is not read as such.
- **Served model** per session from `config.json`; if the two arms were served
  different models, the comparison is pending.

## What is not claimed

One seed, one world, one order, partial blinding, a same-family rater. This can show
that the cards are usable at this cost and whether accuracy moves in the expected
direction; it cannot show that better memory yields better science.
