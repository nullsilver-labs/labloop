# labbench-haiku: harness effects on a weak worker (rules v1, 2026-10-18)

**Status:** adopted 2026-10-18, before any instance of this programme was scored. Fable 5.1 reviewed the draft adversarially, and its edits are folded in (changelog at the end). Any change after the first probe instance is scored is a new programme name (the lesson of `meta-loop-plan.md` §4, v0.3 item 7).

## 0. Why this programme exists, and what it can claim

labbench under v0.3 admits tasks for a Sonnet 5.5 worker. Across five families, a frontier session either solved the planted structure in one search or found it by lottery (`meta-loop-plan.md` §4, "Decisions 2026-10-18").

The user's question was different: use a deliberately weak worker so the harness has room to show what it adds. A weak worker needs selection, operators and memory to accumulate what it cannot do in one session. It is also cheap, so arms can be repeated.

The Haiku gate (`../labloop-haiku-gate-20261018/READ.md`) opened on three preregistered lines:
- contract met, 5 of 5;
- median session search g .066 on hrw probe/0;
- one session found two planted rules that no Sonnet session on that instance had found.

Sessions cost about $0.04 at list price, against $0.29 for Sonnet.

**What this programme can claim:** a policy change moves Haiku's campaign-level score on the families admitted here. **The default claim is "on Haiku only".**

**What it cannot claim:** that the change helps Sonnet (that is the transfer read of §6, with its own line), or anything about models in general.

## 1. Fixed for the whole programme

- **Worker:** `claude-haiku-5-5` for every operator, 40 turns, a 45-min job wall. If any candidate's served model differs from the requested one, that arm is invalid.
- **Labloop tools:** pinned per experiment, by commit, in its PREREG. Arms that are pooled across experiments (a probe's frozen arms reused as a pair's default) must be byte-identical in card text and tools commit; otherwise they do not pool.
- **Family:** hrw-v0, with its gauge frozen at f7034b3. Only fresh instances are scored for any line: `probe` purpose, index ≥ 5 (0–4 are burned by labbench v0.2/v0.3 and the gate).
- **Burned instance probe/0** may hold disclosed pre-runs that inform a prediction (§2a). Pre-runs are never scored for any line.
- **Attribution** (`families/hrw/attribute.py`) runs on the public dev split. A hidden split is read once per arm, by `lab run`, for its best candidate. If a candidate's dev g and search g differ by more than 2×, as the gate's c0003 did (.312 against .154), its dev attribution is flagged and is not used alone for a single-discovery label.
- **Integrity:** as labbench v0.3 K7, with trusted dirs, `../labbench` locked during runs, no web, and blind arms' scoreboard reads refused.
- **Usage window:** every PREREG sets `usage.window_budget`, calibrated from the previous Haiku run's `lab campaign usage`. Every deferral is reported. If one experiment spends more than one full 5-h window waiting on deferrals, the programme pauses for the human. List-price dollars say nothing about the Max window, and the gate did not measure it.

## 2. Admission of hrw for a Haiku worker (the first experiment)

### 2a. Pre-run on burned probe/0: about $0.30, disclosed and not scored

The K6 direction for Haiku cannot be predicted honestly yet.
- **The case for frozen:** the Sonnet prediction rests on improves adding forms one per job.
- **The case for blind:** frozen's breadth is a single draft (`draft_p` = 0). At Haiku, 3 of 5 gate drafts found nothing, so a frozen chain usually starts from a generic learner. Blind best-of-19, drawn from a distribution where 2 of 5 sessions reach search g ≥ .15, lands around .25–.35 almost surely.
- **What would settle it:** whether a Haiku improve job adds a form. The gate has no Haiku improve data.

**The pre-run:** a frozen Haiku campaign on probe/0, 8 candidates (c0000, one draft, six improves), with tools as in the probe. The READ of it says, per improve, whether a form was added (dev attribution, flagged under the 2× rule). The probe's PREREG discloses it and only then fixes the direction.

### 2b. The probe: fresh instances 5 and 6, all arms at once

**Arms, per instance:**

| arm | runs | candidates |
|---|---|---|
| frozen (labloop defaults) | 2 replicates, seeds differ | 20 each |
| blind (v0.3 one-shot card, draft-only) | 2 replicates, seeds differ | 20 each |
| standalone one-shot | 1 | 2 |

That is 5 campaigns per instance, 10 in all, about 2 × (4 × 19 + 1) sessions × $0.05 ≈ $8 list.

Twenty candidates rather than 12 is justified by cost alone, about $0.40 more per arm. It changes two inherited lines, and both changes are stated:
- **H3 saturation** is read on best-of-19, which fires more often than v0.3's best-of-11 by construction. That is accepted: saturation by accumulation within 20 candidates would make the family useless for this programme, whatever the cause.
- **H5's window** stays at v0.3's 4th to 12th settled candidate. Steps between the 13th and 20th are reported, not counted.

**Lines.** Each one fires the family out:
- **H1 cost:** any arm above $5 list-price, or a median evaluation above 10 CPU-min per split.
- **H2 typical session:** the blind arms' median per-session search g > .5, on either instance. Against a worker whose median gate session was .066 this is nearly vacuous. It is kept as a guard against a mislabelled or upgraded worker, and said to be that.
- **H3 saturation:** best final g > .8 in any arm. The READ says whether it came by accumulation. It still fires.
- **H4 floor:** on both instances, the better policy's best final g < .05. The gate's best of 5 (.27) makes this unlikely; noted, not adjusted.
- **H5 flat:** no frozen replicate steps its best-so-far search g up at least twice, each step ≥ .03, between the 4th and the 12th settled candidate. Separately, `attribute.py` labels the family single-discovery if one form explains > 80 % of the best arm's dev g, subject to the 2× flag of §1. That label is reported and weighs as a kill.
- **H6 harness-blind:**
  - On each instance, D = mean g(frozen replicates) − mean g(blind replicates), on final.
  - The spread is max(the largest |replicate difference| among the four replicate pairs, .10). Instance-to-instance differences are not in it: the comparison is paired within instance.
  - H6 fires unless both D have the same sign and both |D| > spread, on g **and** on g per list-price dollar.
  - **The direction is predicted in the probe's PREREG, after the §2a pre-run, separately for g and for g per dollar.** A wrong direction on either reading means hrw is out for Haiku, with no v2.
- **H7 integrity:** as labbench v0.3 K7.
- **H8 reliability:** killed + invalid ≥ 5 of the 19 workers in any 20-candidate arm (v0.3's 25 %). Deferred jobs are counted and reported separately and never count here.
- **Turn calibration:** if a blind arm's median turns are under half the one-shot's on its instance, that arm's H3 reading is void. Medians are reported beside the gate's (15).

**Recorded, not gated:**
- **σ_run for Haiku:** the four replicate differences, the first campaign-level noise figures for this worker. Later pairs use them only as an order of magnitude, never as their SE.
- Per-arm forms found and the first candidate for each, plus the nested-sets reading for the enumeration threat (as in the Sonnet hrw v0.3 PREREG).

## 3. Experiments after admission

Each experiment has its own PREREG with its predicted direction, run on fresh instances.

1. **Effort pair, removal only.**
   - The default card against the same card with "Make ONE hypothesised change" and "Prefer simple and runnable over ambitious" removed, from `[worker.operator_text]` and from `task.md`. Nothing is added.
   - 2 instances × k = 4 per arm = 16 campaigns of 20 candidates, about $15 list.
   - **Primary line:** mean paired D on final g ≥ .05, and t = mean D / SE ≥ 1.895. SE comes from this experiment's 8 paired differences; 1.895 is the one-sided t at .05 with 7 df.
2. **Forget, as a 2×2 with effort,** only if effort shows anything.
   - Forget is an improve job whose parent is the best candidate, with no lineage, summaries or population on the card. Its instructions follow the effort arm's.
   - Each cell is named as the bundle it is. Forget needs a card-mode flag in labloop (not built), and that flag is built and acceptance-tested before its PREREG.
3. Any other single idea follows the same pattern, one at a time.

## 4. What ends the programme

- **hrw not admitted for Haiku:** the programme stops, and the READ says which line fired. No re-tuning of hrw for Haiku: tuning instances are burned (v0.3 item 6).
- **Three consecutive null experiments:** the programme stops and is written up. An experiment is *null* when |mean D| < .05, or the sign of mean D differs between the two instances. An effect in the unpredicted direction that clears the line is a finding, not a null, and is reported as one.
- **The usage-window pause of §1.**

## 5. Order relative to labbench v0.3

- The Sonnet hrw v0.3 probe (`../labloop-hrw-probe3-20261018`, launched 2026-10-18 09:18Z) is independent. It uses other instances (3 and 4), another worker and other rules.
- The two never share a `../labbench` lock window: the §2a pre-run and this programme's probe launch only after the Sonnet probe's unlock watcher has restored labbench.

## 6. Transfer to Sonnet

A policy that wins here gets one preregistered Sonnet read: frozen against that policy, 2 instances × k = 2, Sonnet 5.5, on fresh instances of a family admitted for Sonnet. If none is admitted, the read says so and is not run.
- **Line:** mean paired D on final g ≥ .05 and t ≥ 2.353 (one-sided .05, 3 df, from the 4 paired differences).
- It is reported beside the Haiku result, never pooled. Without a supported transfer read, a result here stays "on Haiku".

## Changelog

- **2026-10-18, v1, adopted after Fable 5.1's review of the draft.** Changes from the draft:
  - the H6 direction is no longer fixed in the rules: it comes after a disclosed pre-run on burned probe/0 (§2a), predicted for g and for g per dollar;
  - blind runs twice per instance;
  - the instance term is out of the H6 spread;
  - the H3/H5 changes from 20 candidates are stated, with the H5 window kept at 4–12;
  - the effort pair's line is a one-sided t with 7 df;
  - arms pool only when byte-identical;
  - "null" is defined, and there is a usage-window pause;
  - H2 is called nearly vacuous;
  - the single-discovery label is flagged on dev/search disagreement;
  - the transfer read has a line.
