# Four opening drafts vs one — result (2026-09-15)

Read after both arms had written `REPORT.md`, against the rule frozen in
`../../../labloop-drafts-20260914/PREREG.md` (and its pre-launch two-GPU amendment)
before either arm was launched. Every number below comes from
`scripts/drafts_mechanical.py`; its output is `mechanical.md` / `mechanical.json`
beside this file. Nothing in either arm directory was modified.

Written by an Opus subagent and checked by the operator session (§9). The primary
endpoint, the kill criterion and the M4 read are mechanical; the throughput diagnosis
in §5 separates what the numbers show from what is inferred.

## 1. The preregistered read: per arm, against the fixed 0.50

| arm | frozen | search fitness | final split (read once) | endpoint |
|---|---|---|---|---|
| D1, `initial_drafts = 1` (`engram-drafts1-w0`) | c0016 | 0.997925 | **0.997803** | **supported** |
| D4, `initial_drafts = 4` (`engram-drafts4-w0`) | c0017 | 0.803833 | **0.845581** | **supported** |

No pending clause applies to either arm: both ended at `max_candidates 20 reached`,
both settled ≥ 20 candidates (21 and 20), both were served the same models
(`claude-sonnet-5` with `claude-haiku-4-5-20251001` alongside it, in every session of
both arms), and every candidate in both arms completed — 0 invalid, 0 failed, 0
killed, 0 deferred, 0 re-dispatched.

Descriptive gap, D4 − D1 in final score: **−0.152**. It is one seed, one world, one
drawn order and two runs; PREREG says it is reported beside the two per-arm claims
and is **not** evidence that one setting is better. The two frozen candidates trained
on **the same card** (GPU 1, the faster one), so the GPU covariate does not explain
the gap in either direction; the full per-GPU table is `mechanical.md` §7.

## 2. The kill criterion does not fire

Fixed before launch: *the four-draft arm's frozen final is below the one-draft arm's
by more than .05* **and** *no draft after the first beat the first on the search
split.*

- Half A — **holds**: 0.845581 is 0.152 below 0.997803.
- Half B — **does not hold**: D4's first draft c0001 scored 0.587158 on the search
  split; c0003 (0.676514) and c0004 (0.709717) both beat it, and c0004 is the root of
  the lineage that produced the frozen candidate.
- **The criterion does not fire.** `initial_drafts > 1` is not killed on this task by
  this pair. Equally, nothing here argues for it.

## 3. Lineages — the point the pair was built to look at

PREREG's amendment counts each planned draft *and* each "disguised draft" (an improve
whose parent is `c0000`, or a crossover with `c0000` as a parent) as an opening
approach, reported as "N planned + M via the baseline".

**D1 — 1 planned + 2 via the baseline.**

| root | kind | members | best search fitness | ever held the running best | approach |
|---|---|---|---|---|---|
| c0003 | via the baseline (improve of c0000) | 13 | 0.997925 | yes | 16-table hashed n-gram memory gated in after decoder layer 2, with the hashing input **canonicalised** to a fixed `Entity:/Attribute:` prefix |
| c0001 | planned draft | 6 | 0.867798 | yes | 16-table hashed n-gram memory gated in after decoder layer 2, hashing the raw question wording |
| c0007 | via the baseline (crossover with c0000) | 1 | 0.296875 | no | c0001's memory plus a fallback to the baseline's per-attribute majority answer |

**D4 — 4 planned + 0 via the baseline.**

| root | kind | members | best search fitness | ever held the running best | approach |
|---|---|---|---|---|---|
| c0004 | planned draft | 8 | 0.803833 | yes | hashed n-grams over *canonicalised token text*, attached after decoder layer 0, dropout 0.1 on the memory read |
| c0003 | planned draft | 7 | 0.753296 | yes | whole-prompt cumulative-mean bag of hashed n-grams, content-dependent gate, injected after layer 8, prompt lowercased |
| c0001 | planned draft | 1 | 0.587158 | yes | hashed n-grams (orders 1–4, 4 heads) gated in after decoder block 2 |
| c0002 | planned draft | 3 | 0.373291 | no | shared hashed table (orders 1/2/3) gated in after layer 2 |

- **Three of D4's four drafts produced a lineage that at some point held the arm's
  running best** (c0001 as the first scored candidate, then c0003, then c0004).
- Slots on the frozen candidate's lineage: **D1 12 of 17** improve/crossover slots
  (0.71); **D4 7 of 15** (0.47). D4 spread its effort more, as intended.
- Search progress (best fitness after 4 / 8 / 20 settled): D1 **0.992 / 0.994 /
  0.998**, D4 **0.677 / 0.766 / 0.804**. D1 exceeded D4's final score on the search
  split at its **fourth** candidate, c0003; D4 **never** exceeded D1's final score on
  the search split.

The honest reading of this table is that D1 was not a one-approach arm. Rank
selection drew the baseline as an improve parent at job 3, and that candidate —
starting from no code at all — introduced prompt canonicalisation and jumped the arm
from 0.33 to 0.99 on the search split in one step. D1 got **two** genuine opening
approaches plus one throwaway; D4 got four. The treatment is `initial_drafts`, but
the realised number of opening approaches was 3 vs 4, not 1 vs 4, and the winning
approach in *both* arms is the one that canonicalised the hashing input. What this
pair actually contrasts is *when* the canonicalising approach appeared and how many
slots were left to refine it: D1 found it at candidate 3 with 17 slots still to come;
D4's c0004 found a version of it at candidate 4 but then split its remaining 15 slots
across four lineages.

## 4. Coverage and the governor

- **Coverage is full in both arms.** Every job's context held its direct parent(s),
  and once ≥ 4 cards existed at dispatch, every job saw ≥ 2 cards from outside its
  lineage — 0 violations in D1 (20 jobs) and 0 in D4 (19 jobs), whether or not the
  baseline's card is counted as out-of-lineage. Under findings-v2 the rule says
  coverage *must* be full, and it is; the mem2 pair's selector failure is not
  present here. "Cards that existed at dispatch" is computed from `ended` times, not
  from candidate ids, because with two slots a sibling still in flight has no card.
- **Governor.** The armed `window_budget = 20.0` soft gate fired once in each arm, as
  designed: D1 waited 282 s (2.8 % of wall), D4 643 s (7.8 %), peak window estimate
  71 % and 70 %. 0 rate limits, 0 deferrals, 0 hard kills, 0 failed jobs in both.
- **Cost.** D1 $14.10 over 20 sessions ($0.71 mean, $0.66 median); D4 $13.77 over 19
  ($0.73 mean, $0.67 median). The `session_cost = 0.48` calibration from the mem2
  sessions under-estimated both arms by about half.

## 5. The M4 throughput read — the criterion fires

| arm | slots | settled | GPU-hours | settled per GPU-hour | wall (h) |
|---|---|---|---|---|---|
| `engram-drafts1-w0` (D1) | 2 | 21 | 5.02 | **4.19** | 2.83 |
| `engram-drafts4-w0` (D4) | 2 | 20 | 4.35 | **4.60** | 2.28 |
| `engram-mem2-legacy-w0` | 1 | 20 | 4.23 | 4.72 | 4.79 |
| `engram-mem2-findings-w0` | 1 | 20 | 3.67 | 5.45 | 3.70 |

`docs/aira2-loop-design.md` M4: *kill if settled candidates per GPU-hour fall below
the single-GPU figure.* Both two-slot arms fall below **both** single-GPU references.
**The M4 criterion fires.** Per the amendment, two-slot dispatch is not used again on
this task until the cause is understood, and the campaign plan should say so.

### What the numbers show

- **`gpu_seconds` is the sum of the per-candidate leases, exactly, in all four
  arms** (difference 0.0 s everywhere). So "GPU-hours" is *slot-lease hours*, not
  measured GPU busy time: every second a slot is held is charged, including the
  seconds the worker spends reading, editing and thinking rather than training, and
  with two slots two of those seconds are charged per second of wall clock. The
  metric is therefore exactly `3600 / mean lease seconds per settled candidate`.
- **The leases are longer per candidate, not more numerous.** Median / mean lease
  seconds: D1 841 / 902, D4 841 / 824, legacy 751 / 761, findings 706 / 694.
- **It is not more training.** Training seconds the candidates recorded themselves:
  D1 480 / 511, D4 480 / 480, legacy 540 / 515, findings 540 / 492. The two-slot arms
  trained *less* per candidate (the workers chose 480 s budgets, the reference arms
  540 s) and still held their slots longer.
- **The growth is in the non-training part of the lease** (lease − training seconds),
  median / mean: D1 286 / 398, D4 300 / 327, legacy 226 / 286, findings 181 / 180.
- **It is not the second slot idling.** Two leases were open for 78 % of D1's wall
  clock and 91 % of D4's; slot occupancy (leases / 2 × wall) is 0.89 and 0.95 against
  0.44 and 0.50 for the one-slot arms. D1's lower figure is the start of the run: the
  second-slot draft rule (labloop `e464135`) correctly left the second slot empty for
  the 27 minutes of c0001, which is the fix that keeps D1 a one-draft arm.
- **It is not usage waiting, deferrals or failures.** Waiting happens between
  dispatches and is not inside any lease, so it does not enter `gpu_seconds` at all
  (mem2-legacy waited 1831 s on one slot and still scored 4.72). 0 deferrals, 0
  failures, 0 re-dispatches in both arms.
- **Turn counts are comparable** (median 21.5 / 19 against 22 / 16), so it is not a
  per-candidate explosion in agent turns either.
- **Wall clock did roughly halve**: 2.83 h and 2.28 h against 4.79 h and 3.70 h for
  the same 20-candidate budget.

### What I infer from that (interpretation, not a measurement)

The M4 criterion as written measures candidates per *leased* slot-hour, and a slot is
leased for the whole job — agent time included. On this task a candidate is roughly
480–540 s of training inside an 700–900 s lease, so a third to a half of every
"GPU-hour" is a language-model session, not the GPU. Doubling the slots doubles the
charged denominator immediately, and only pays it back if each lease stays the same
length. The leases did not stay the same length: they grew about 90–135 s at the
median, entirely in the non-training part.

The most likely cause is contention on one 20-core host running two worker sessions
and two trainings at once — the pre-launch gate run already measured concurrency
costing GPU 0 about 1 % of its optimizer steps, and the same contention plausibly
slows the agent's own tool calls (data loading, prediction passes, file reads) by
much more than 1 %. A second contributor specific to D1: 13 of its 20 candidates
record `loaded_existing_weights: true`, i.e. they ran `code/run.sh` a second time to
verify the reload path — a habit c0003 started after finding a real save/reload bug
and passed down its lineage through the cards. That adds a prediction pass of roughly
30 s plus turns to each of those leases (D1's mean lease, 902 s, is 61 s above its
median; c0003 itself held a slot for 1907 s across three `run.sh` runs). D4 records
the flag nowhere and still shows longer leases than the references, so contention,
not the reload habit, is the part that generalises.

Two things follow, neither of them measured here:

1. **The metric is probably the wrong one for this loop.** Settled candidates per
   leased slot-hour charges agent time as GPU time. A throughput read that separates
   the two — settled candidates per hour of *measured* GPU busy time, or per wall
   hour — would report two slots as roughly a 1.6–2.1× speed-up, which is what the
   wall-clock column shows. Changing the measure after seeing the result is exactly
   what preregistration forbids for *this* read; the fired criterion stands as
   written, and any replacement metric belongs in the next preregistration, fixed
   before the next run.
2. **If the metric is kept, the fix is to shorten the non-training part of the
   lease**, not to add slots.

## 6. Odd things found in the arms

- **D1 settled 21 candidates, D4 settled 20.** Both stopped at `max_candidates 20
  reached`. D1 therefore ran 20 non-baseline candidates and D4 only 19, so D4 had
  15 improve/crossover slots against D1's 17 (PREREG anticipated 16 and 19, counting
  the disguised drafts as slots). The arms were meant to differ only in
  `initial_drafts`; with two slots the candidate cap overshot by one in one arm and
  not the other. It is one slot in D1's favour, on the arm that scored higher. Worth a
  look in `tools/lab`'s stop check before the mixed pair.
- **D1 c0003 is not leakage.** Its search fitness jumps from 0.33 to 0.9922 as an
  *improve of the baseline*, which is the pattern that should be checked first. Its
  `summary.md` says it built the whole approach from scratch (the baseline has no
  memory code) and that the jump came from canonicalising the hashing input to a
  fixed `Entity:/Attribute:` prefix, from metadata present in every split and never
  from the answer. The "reload-determinism" runs it describes touch **only its own**
  `candidates/c0003/code/memory.safetensors`: `run.sh` reads no other candidate's
  directory, and the 20 weight files in D1 are pairwise distinct by sha256, so no
  child is scoring its parent's weights. It found and fixed a real bug on the way (a
  float32 cast silently corrupting int64 hash coefficients on reload), which is why
  its lineage kept re-running the load path.
- **No child inherited weights, in any arm.** Every `memory.safetensors` in all four
  arms postdates both its candidate's dispatch time and its own code copy; no two
  files in an arm are identical. `loaded_existing_weights: true` appears in 13 D1
  candidates (the reload-verification habit above, plus the frozen candidate whose
  file the final run rewrites) and in none of D4's — D4's code never writes the key
  at all, which is not the same as writing `false`.
- **One session exceeded the turn cap.** D1 c0003 reports 45 turns against
  `worker_max_turns = 40`; the watcher logged `max-turns=40` and the session ended
  `end_turn` with `is_error: false`, so nothing was truncated or killed. The SDK's
  `num_turns` and the harness's cap evidently count different things; worth
  confirming before a campaign relies on the cap as a budget.
- **Denied tool calls, all benign.** 12 denials across 10 D1 sessions and 4 across 4
  D4 sessions, all Bash — the operator's own permission rules (an `rm -rf /tmp/...`,
  a `mv memory.safetensors ... .corrupt-bak` while c0003 was chasing its reload bug).
  No `.corrupt-bak` or stray files were left in any candidate directory.
- **Every session logs a failed SessionEnd hook** (`node: not found`) on stderr, in
  both arms and in mem2-findings. It is cosmetic — no session is flagged `is_error`,
  no `api_error_status` anywhere — but it means `session.stderr` is non-empty for all
  39 sessions and cannot be used as an error signal as it stands. The hook is not the
  arm's: it is a user-level Claude Code plugin (`${CLAUDE_PLUGIN_ROOT}/scripts/
  session-lifecycle-hook.mjs`) that needs `node`, and `LAUNCH.md`'s sanitized `PATH`
  has none. Either put node's directory on that PATH or disable the plugin for
  workers; noted in `NEXT.md`.
- **Reference-arm caveat.** The two mem2 arms are the same task, model and one GPU,
  but not the same memory mode (one is legacy) and their workers chose 540 s training
  budgets against the drafts arms' 480 s. The M4 read compares them as PREREG
  specifies; the comparison is not a controlled one.

## 7. What is and is not claimed

- Each arm's frozen candidate cleared the threshold fixed before launch. That is the
  whole of the preregistered claim, and it is a feasibility claim per arm.
- The −0.152 final-score gap is **not** a result. One seed, one world, one drawn
  order, two runs, no test, and D1's realised head start came from a rank draw (the
  baseline as an improve parent) that the treatment does not control.
- Nothing here says four drafts are worse than one, or better. The kill criterion
  written to end the idea did not fire, because three of D4's four drafts mattered.
- The M4 criterion fired and the read stands as written. The diagnosis in §5 is an
  explanation offered with numbers, not a licence to change the measure for this
  read.
- No prose rating is involved in this comparison, so there is no blinding step and no
  rater; every measure above is mechanical and reproducible from the two arm
  directories with `scripts/drafts_mechanical.py`.

## 8. Procedure as executed

1. 2026-09-15: both arms finished and had written `REPORT.md`; D1 2026-09-14
   21:17Z→2026-09-15 00:07Z, D4 2026-09-15 05:45Z→08:02Z, sequentially as `ORDER.json`
   drew them.
2. `scripts/drafts_mechanical.py --d1 … --d4 … --ref …mem2-legacy… --ref
   …mem2-findings… --md mechanical.md --json mechanical.json`, read-only.
3. Every number in this file is taken from that output. No label, split or file under
   `/srv/labloop-private` was read; the final scores are the ones `lab run` recorded.
4. Operator check (Fable session, 2026-09-15): `mechanical.md` re-generated from the
   script and found byte-identical; `gpu_seconds` re-summed against the leases
   (18059.0 and 15661.0 s, equal); the 20 and 19 `memory.safetensors` files re-hashed
   and found pairwise distinct; the overshoot traced in `tools/lab_campaign.py`
   (`tick()` checks `max_candidates` against settled candidates only, then fills every
   free slot; with two slots and 19 settled plus one running, a 21st is dispatched) and
   fixed the same day with an acceptance case (`NEXT.md`, the commit that follows this
   file). The SessionEnd hook was traced to a user-level plugin, not the arm.

## 9. Operator's reading

The pair answers its preregistered question (both arms supported, the kill criterion
does not fire) and leaves the design question open, for the reason §3 gives: rank
selection drew the baseline as an improve parent in D1 and that draw, not the
treatment, produced D1's opening approaches. Two consequences for the plan:

- **Exclude the baseline from the parent pool once any non-baseline candidate is
  evaluated** (the change the mem2 read already proposed): otherwise
  `initial_drafts` does not control the number of opening approaches, and no future
  pair on this knob is interpretable. It changes the random stream, so it is a new
  campaign, never a change to a running one.
- **A throughput measure that does not charge agent time as GPU time** must be fixed
  in the next preregistration before the M4 question is asked again; §5 explains why
  the current one cannot separate the two. Until then two-slot dispatch stays under the
  fired M4 rule, and any arm that uses it says so and why.
