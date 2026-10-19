# labloop v2: harness changes from the 2026-10-18 evidence (plan, draft 3)

**Status: draft 3, after review rounds 1 and 2** (Fable 5.1, an independent Opus 5.5 reviewer, and a literature pass over 11 papers, all verified on arXiv). It is written overnight, without the user. The user asked for research, several rounds of Fable/Opus review and a start on building. Building happens on branch `v2`; `main` and every campaign pinned to a commit stay untouched.

**Ceremony rule** (user, 2026-10-18: "I feel like this is getting nowhere"):
- each experiment gets one line fixed before launch;
- review rounds apply to the plan, not to each test;
- results are named as single-family evidence on hrw.

## 1. Evidence (corrected in round 1)

| # | finding | caveat (round 1) |
|---|---|---|
| E1 | Default improve and crossover jobs rarely add a planted structure: **4/180** (Sonnet 0/20, Haiku 0/80 and 4/80). Without "Make ONE hypothesised change" and "Prefer simple and runnable", **21/160** do (Haiku; per-job Fisher p ≈ .0003, which overstates given clustering). Crossovers added one form in 54. *Corrected 2026-10-19 after the replication:* not zero. | The bottleneck is the **card text**, not the improve operator as such. |
| E2 | Draft-heavy arms beat the default on hsrc-v1 and on both hrw instances. Four opening drafts beat one, under the line. | **Over-read in draft 1.** One arm per instance against a seed spread of .02–.30. The blind arms also ran twice the turns at 1.8–2.3× the cost, and per dollar frozen won on instance 3. This is effort plus breadth confounded, not breadth alone. |
| E3 | 32/160 effort-pair children have exactly the parent's score. **37/160 write predictions identical to the parent's. Only 2/160 have identical code.** | The waste is a **functional** no-op, not a literal one. A code-hash gate (draft 1's C5) catches about 1 %. |
| E4 | Improves use 13–16 of 40 turns (Haiku), and drafts 20 → 32.5 under the effort text. | The turn cap does not bind; the text does. Improves gained structure from permission to make more than one change, not from more turns. Sonnet's hrw one-shots ran 8–9 turns, not about 40. |
| E5 | Haiku sessions cost $0.02–0.04 and are lumpy (per-session sd .085). | |
| E6 | The same arm on the same instance spans final g .02–.30 across seeds. With sd(D) = .162, **8 pairs give about 45 % power for D = .1; 80 % needs about 16.** | Final-g lines at k = 8 are underpowered by design. |
| E7 | The best-by-search pick is noisy (.533 search, .818 final). Search scores tie at six decimals across different code. | The final pick, the parent ranks and any "raised the best" signal all inherit this noise. |
| E8 | The effort pair: final g .158 → .254, D +.096, t 1.68 (needed 1.895). The replication: .136 → .258, D +.121, t 1.80 (primary not supported). Pooled 16 pairs: D +.109, t 2.54 ≥ 1.753 (the preregistered secondary, supported). | The replication on hrw 7/8 is running. |

**From the literature** (details in the round-1 log):
- **Fork-and-Flush (2610.07447):** breadth plus selection works, on a **fixed schedule**. Plateau triggers often never fired (15/25). "Different approach" directives changed nothing.
- **AIRA-dojo (2507.02554):** operators, not search, are the bottleneck. Its complexity cue is graded by child count. Our two lines are a constant "simple" setting of that cue.
- **Beneath the Diff (2609.00077):** idea-level mode collapse, which an idea-novelty memory reduces (audited gain ratio .44 → .61 from memory alone).
- **Gupta et al. (2607.18235):** elaborate selection machinery buys nothing.
- **Elo-per-token (2609.15309):** short jobs are not the problem; long state accumulation is.
- **Interaction tax (2608.23541):** reading full solutions homogenises proposals.

## 2. Diagnosis (narrowed)

The card text tells every worker to take one small safe step, and they do. As a result:
- improves add no structure (E1);
- a quarter of them change nothing functional (E3);
- the only breadth comes from drafts (E2, confounded).

The noise of a single search score (E7) and of draft luck (E6) then hides anything else. v2 attacks the text first, makes experiments able to see effects (shared snapshots, per-job metrics), and only then tests breadth and selection.

## 3. Work items

### A. Config-only experiments: no build, on the pinned commit f77ea4a (not `v2`)

- **A1. The base is the effort text** (`[worker.operator_text]`). This is a **mechanism-based decision** (E1, 10/80 against 0/80), not a supported score result. If the C1 replication fails its line, A2's results are reported as "on an unsupported base". If it passes, the effort text also becomes labloop's default.
- **A2. A 2³ factorial on the effort base.** Haiku, hrw, 12 candidates.
  - **Blocking:** 4 fresh instances × 1 campaign per cell. That is 32 campaigns, about $10. The instance is the block; seeds do not reproduce LLM sessions, so seed pairing buys nothing.
  - **Factors:**
    - (i) `draft_p` 0 against .3 (breadth spread through the run);
    - (ii) `initial_drafts` 1 against 4 (breadth front-loaded; pair 1's knob). With (i) on, the cell is near-blind, so the factorial also reads Fork-and-Flush's schedule question at zero build;
    - (iii) the **no-op line**, appended to the improve text: "Before finishing, compare the per_target values in your out/predictions-search.json with your parent's (its path is readable). If they are all equal, your change did nothing: make a different one."
  - **Primary lines**, three of them, so the family-wise rate is about .14 (stated now):
    - (i) and (ii): mean final g with the factor on minus off, 16 against 16 campaigns. Welch one-sided at .05, and the difference ≥ .05.
    - (iii): the **per-campaign rate of planted forms added by improve jobs** (dev attribution), 16 against 16, Mann-Whitney one-sided at .05, predicted higher.
      - Its manipulation check, the per-campaign rate of improves whose dev `per_target` equals the parent's, is reported, never read as the result: the line instructs that behaviour, so it would pass trivially.
      - Rates are per campaign because identical-output children cluster heavily by campaign (e63 8/10, most 0–2), so a per-job Fisher test would be invalid.
  - **Reported, never read:** interactions (8 against 8), a blocked analysis by instance, turns, $, and the dev/search g ratio.
  - **Not temperature.** At τ = 1 the baseline c0000 enters the parent pool with weight about .37, which confounds selection with breadth, and no evidence points at temperature.
- **A3 (after A2), the crossover line, zero build:** "Read each parent's per_target in its out/predictions-search.json; keep what each parent gets right." It is tested on shared snapshots (B2) with forms added per crossover as the primary metric. This replaces draft 2's B3 hook.

### B. Builds on branch `v2`, each off by default, each with acceptance tests

- **B1. The output-identical metric** (built, a6ecaf3). `same_output_as_parent` is recorded at settle with `[data] same_output_ignore` (hrw: `seconds`, `sandbox`), and REPORT counts it.
  - **Caveat:** on hrw, `out/predictions-search.json` is the worker's **dev self-measurement** (score, per_target, seconds), not search predictions. So B1 there means "same dev per-target accuracy as the parent". On a normal task it means identical predictions.
  - A2 runs on f77ea4a, so its metric comes from a read script over the persisted files.
- **B2. Shared snapshot seeding** (to build, carefully). It is **for operator tests only**: for breadth and selection tests the draft lottery is the effect itself.
  - **Source checks:**
    - refuse findings modes (copied cards fail `check_card_sources`);
    - refuse a source whose task, data, evaluator or **search-split label hashes** differ, or whose `operator_text` differs from the arm's;
    - match the instance by manifest hash.
  - **What is copied:** only settled candidates (no queued, running or deferred ones, no watch ids), with their `debugged` flags, and whole dirs, weights included, since the final re-run needs them.
  - **Counters and accounting:**
    - recompute `settled`, `best` and `settled_at_best` in settle order;
    - mark the copies `seeded_from` and leave their sessions out of $ and g per $;
    - seeded candidates count toward `max_candidates` in both arms (stated);
    - LEDGER rows and events go through `tools/lab`.
  - **Design:** ≥ 4 snapshots (2 instances × 2 draft seeds), each running both arms. Per-job metrics are primary, and **the final-g line is void by construction**: the best candidate is often a seeded one in both arms.
- **C2. Stagnation drafts** (built, a6ecaf3, off). It refuses `blind`, a draft resets the count, and `restart_min_step` sets the step floor. It is tested only after A2's breadth factors, against `draft_p` matched to the same expected number of drafts.
- **Dropped:**
  - **B3, the feedback hook.** On hrw the parent's dev per_target is already readable, so A3 is a text change. Running untrusted code as the lab user, who can read the labels dir, would open a leak channel, and its output on later cards would be an inter-candidate prompt channel.
  - **Sibling cards (C3), the offspring penalty (C4) and the code-hash gate (C5)**, as in draft 2.

## 4. Order

1. **Tonight.**
   - Read the C1 replication when it ends.
   - Stage hrw instances 9–12 once `../labbench` is unlocked.
   - Scaffold A2 on f77ea4a (32 dirs, trust.sh, launch.sh), with a PREREG holding the lines above.
   - Build B2 on `v2` with acceptance tests.
2. **Morning (the human):** trust and launch A2.
3. **After A2.** A3 on shared snapshots. Then C2 against matched `draft_p`, if breadth moved.
4. **When two or more changes are supported:** one combined v2 against v1 pair at 16 campaigns per arm, before any default changes. A Sonnet read at k = 2 × 2 is a transfer check only: it cannot support a claim, and it is labelled as such.

## Review log

**Round 1 (draft 1), 2026-10-18 night.**
- **Fable 5.1:**
  - test breadth with existing keys first; C2's control must be matched `draft_p`; add a step floor;
  - count literal no-ops before building C5;
  - park C4; replace sibling cards with per-target dev rows on crossover cards;
  - 16 pairs, not 8; a factorial, since the bottleneck is dirs and trust, not dollars.
- **Opus 5.5:**
  - recounted E3: 37/160 output-identical, 2/160 code-identical;
  - E2 over-read and E4 partly wrong (see table);
  - a zero-build in-session no-op line; test `temperature` before C4;
  - make per-job mechanism metrics primary; pin shared opening drafts;
  - fix the final pick; C2 code risks (blind, parallel slots, rng stream).
- **Literature pass** (Sonnet agent, 11 papers verified):
  - fixed-schedule breadth over adaptive triggers;
  - graded complexity cue;
  - idea-novelty memory;
  - simple selection;
  - shared-snapshot test design.

**Round 2 (draft 2), 2026-10-18 night.**
- **Fable 5.1:**
  - three primary lines make a family-wise rate of about .14; interactions are reported, not read;
  - replace temperature with `initial_drafts` 1 vs 4; a graded cue is not worth a slot at 12 candidates;
  - B2 needs ≥ 4 snapshots, voids final g, needs operator_text matching and a manifest hash, and is not for breadth tests;
  - B3 risks: an inter-candidate prompt channel, untrusted code, and dev-overfitting;
  - A1 stated as a mechanism-based decision.
- **Opus 5.5:**
  - corrected its own E3: on hrw the predictions file is a dev self-measurement, and `seconds` always differs;
  - the factor (iii) Fisher test is invalid under per-campaign clustering, and its line is Goodhart, so forms-added is primary;
  - temperature 1.0 brings c0000 into the pool;
  - block by 4 instances × 1;
  - launch A2 on f77ea4a, not `v2`;
  - B2's risk list (findings cards, debugged flags, counters, max_candidates, weights, cached fitness, the cost report);
  - B3 unnecessary on hrw and a label-leak channel when run as the lab user;
  - B1 can be a read script.

**Round 3 (draft 3 and the A2 generator), plus a code review of `v2`, 2026-10-18/19 night.**
- **Fable 5.1 on A2:** a denominator rule for line 3; lines 1–2 read at equal candidate count, not equal cost; the unlock watcher gets a budget above the campaigns' and a trap that restores labbench; a freshness assert; the task-replace must fail loudly. All applied.
- **Opus 5.5 on A2:**
  - a labbench lock race with another experiment's unlock watcher, so launch.sh refuses then;
  - check that "Make ONE" is gone from every task.md;
  - campaigns that stop on the wall clock are excluded;
  - line 3 becomes a within-instance permutation test on pooled counts;
  - lines 1–2 use the blocked ANOVA as primary, with Welch reported.

  All applied.
- **Opus 5.5 B2 spec.** It was followed, except the operator_text check, which would have refused A3's treatment arm. Only drafts, the baseline and debugs are seeded.
- **Opus 5.5 code review of `v2`**, 10 findings, all fixed in c279872:
  - (1) a seeded frozen best carried the source's final read, so its children could read a final score. Now `predictions-final.json` is not copied and `fitness.json` keeps the search record only;
  - (2) the label hash cannot work under privilege separation. Now each seeded fitness is re-scored through the evaluator, as the eval user, and must match;
  - (3, 4) symlinks are refused, and `tree_sha256` follows linked dirs;
  - (5) the source TOML is checked by `campaign_file` and its sha; final inputs and the baseline command are compared; the model is checked per seeded candidate;
  - (6) the copy goes to a staging dir first, then is renamed into place;
  - (7) `debugged` is recomputed;
  - (9) B1 catches everything;
  - (10) FORMAT keys added, the seed note moved after campaign.start, and seeding checks added to `campaign check`.
- C2 had no bug.
