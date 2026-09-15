# Opus drafts, Sonnet improves — result (2026-09-15)

Read after the mixed arm had written `REPORT.md` (2026-09-15T11:37:57Z), against the
rule frozen in `../../../labloop-mixed-20260914/PREREG.md` and its "Amendment before
launch — two GPUs, the D4 control as it ran", both written before the arm was
launched. Every number below comes from `scripts/mixed_mechanical.py`; its output is
`mechanical.md` / `mechanical.json` beside this file, and anything not from it comes
from a command shown in §11. Nothing in any arm directory was modified, and no label,
split or file under `/srv/labloop-private` was read: the final score is the one
`lab run` recorded in its single read.

One arm, one seed, one world, no order draw. The all-Opus reference does not exist
(that bundle is shelved), so read 2 is two numbers and one ratio, as the amendment
restates it.

**Control integrity.** `../labloop-drafts-4-20260914/population.json` hashes to
`2a4450cefa9dc8797d23380c38f4b9ce7d60d2662db50adb083799135684daa3`, exactly the value
recorded in the mixed bundle's `SHA256SUMS` before launch. **The control is
unchanged.** `diff` of the two `campaign.toml` files shows only the differences PREREG
names: `[campaign].id`, the `[resources.worker_model_by_operator]` table, `[usage]`,
`[stop].wall_clock` (9h → 12h), and the header comments (plus a comment on the `gpus`
line; both arms run `gpus = [0, 1]`, `max_parallel_jobs = 2`).

## 1. Read 1 — the task claim

| | |
|---|---|
| arm | `engram-mixed-w0` (`../labloop-mixed-20260914-arm`) |
| frozen candidate | c0016 (improve of c0006), search fitness 0.986938 |
| final split, read once | **0.997192** |
| threshold, fixed in `campaign.toml` before launch | 0.50 |
| endpoint | **supported** |

Each pending clause, evaluated as PREREG writes it:

- **Ended early?** No. `status: finished`, `stop_reason: max_candidates 20 reached`;
  the 720-min watcher budget and the 12 h `wall_clock` were never approached (wall
  clock 2.431 h). All 21 watcher entries under `.lab/watch/done/` ended `done`, exit
  0, `kill_reason: null`.
- **Fewer than 20 settled?** No. 20 settled, 20 completed, 0 invalid, 0 failed,
  0 killed, 0 deferred, 0 re-dispatched.
- **Any session served a model other than the one requested for its operator?** No.
  19 worker sessions checked one by one from `candidates/cNNNN/config.json`
  (`agent.requested`, `agent.requested_source`, `agent.served`): the 4 `draft`
  sessions requested `claude-opus-5` from `campaign.toml
  worker_model_by_operator.draft` and were served `claude-opus-5`; the 13 `improve`
  and 2 `crossover` sessions requested `claude-sonnet-5` from `campaign.toml
  worker_model` and were served `claude-sonnet-5`. **0 mismatches.** c0000 is the
  baseline and runs no agent session. `claude-haiku-4-5-20251001` is served alongside
  the requested model in all 19 sessions, as it is in all 19 of D4's; it is the
  harness's quick model, not a worker model, and is reported rather than counted as a
  mismatch.

## 2. Read 2 — cost per candidate

From per-session cost over settled candidates. `config.json` carries no cost field;
the per-session number is `session.json`'s `total_cost_usd`, which `population.json`
copies verbatim to `session.cost_usd` (19 of 19 agree in both arms), and these are
the list-price equivalents `claude -p` reports for a subscription session.

| | mixed arm | D4 control | all-Opus reference |
|---|---|---|---|
| campaign | `engram-mixed-w0` | `engram-drafts4-w0` | — |
| worker sessions | 19 | 19 | — |
| settled candidates | 20 | 20 | — |
| total, all sessions | $15.7519 | $13.7722 | — |
| **cost per settled candidate** | **$0.7876** | **$0.6886** | — |
| per-session mean / median | $0.8290 / $0.8349 | $0.7249 / $0.6688 | — |
| per-session min / max | $0.5345 / $1.2852 | $0.4359 / $1.1397 | — |

**Ratio, mixed / D4: 1.1438.** The all-Opus reference **does not exist** — that
bundle is shelved and was never run — so there is no third number and no second
ratio. The mixed arm is 14.4 % dearer per candidate than its all-Sonnet control.

Cost split, the four Opus draft sessions against the Sonnet sessions:

| arm | four drafts | model | drafts total | drafts mean | other sessions | others total | others mean |
|---|---|---|---|---|---|---|---|
| mixed | c0001–c0004 | `claude-opus-5` | $4.0776 | $1.0194 | 15 | $11.6743 | $0.7783 |
| D4 | c0001–c0004 | `claude-sonnet-5` | $3.4063 | $0.8516 | 15 | $10.3659 | $0.6911 |

The four Opus drafts cost **1.20 ×** D4's four Sonnet drafts ($4.0776 vs $3.4063),
not the ~5 × the usage calibration reserved for. §9 records why: the Opus sessions
used about half the turns and half the output tokens of the Sonnet drafts. The
mixed arm's *Sonnet* sessions were also dearer than D4's ($0.7783 vs $0.6911 mean),
which is not a model difference and is not explained here.

## 3. Read 3 — final-split score beside the common threshold

| arm | frozen | search fitness | final split (read once) | threshold | endpoint |
|---|---|---|---|---|---|
| mixed, `engram-mixed-w0` | c0016 | 0.986938 | **0.997192** | 0.50 | supported |
| D4 control, `engram-drafts4-w0` | c0017 | 0.803833 | **0.845581** | 0.50 | supported |

Descriptive difference, mixed − D4: **+0.151611**. Both clear the same fixed
threshold. This is two single runs at one seed with no order draw; per PREREG it is
descriptive and **is not evidence** that the model split is better. The GPU
covariate does not explain it either way (§6): the two frozen candidates trained on
different cards (mixed c0016 on GPU 0, D4 c0017 on GPU 1), and the per-card best
fitnesses inside the mixed arm are 0.986938 (GPU 0) and 0.978149 (GPU 1) — a
difference far smaller than the gap between arms.

## 4. Read 4 — where the Opus money went

### The four opening drafts, side by side

The two arms draw the same selection sequence at seed 3, which is the closest thing
to a paired look the design offers; it is still descriptive.

| # | mixed (Opus) | search fitness | approach | D4 (Sonnet) | search fitness | approach |
|---|---|---|---|---|---|---|
| 1 | c0001 | 0.572021 | hashed 2/3-gram memory, 8 tables ≈ 2.09 M rows × 64, zero-init, key-gated into the residual after block 2 | c0001 | 0.587158 | hashed n-grams (orders 1–4, 4 heads) gated in after decoder block 2 |
| 2 | c0002 | 0.597168 | one zero-init sparse hashed-n-gram table (orders 1/2/3 × 4 heads) over canonicalised tokens, context-gated after block 2 | c0002 | 0.373291 | shared hashed table (orders 1/2/3) gated in after layer 2 |
| 3 | c0003 | 0.695801 | hashed 2/3-gram memory (8 heads, 2.1 M × 128) trained with 48 self-written question templates mixed 50/50 with the real wordings | c0003 | 0.676514 | whole-prompt cumulative-mean bag of hashed n-grams, content-dependent gate, injected after layer 8, prompt lowercased |
| 4 | **c0004** | **0.964966** | hashes **only tokens inside a known person-name span** (every other token → NULL), gated in after block 3 | c0004 | 0.709717 | hashed n-grams over *canonicalised token text*, attached after layer 0, dropout 0.1 on the memory read |

- The mixed arm's best draft, **c0004 at 0.964966, is the only draft in either arm
  that exceeds D4's best draft (c0004 at 0.709717)** — and it exceeds D4's whole
  arm's best search fitness (0.803833) at its fourth candidate.
- Two of the mixed arm's four drafts (c0001, c0003) landed within ±0.02 of the D4
  draft in the same position; c0002 was 0.224 better and c0004 0.255 better.
- All four of the mixed arm's drafts at some point held the arm's running best, as
  each improved on the one before it. In D4 three of the four did: c0002 (0.373291)
  never held it.

### Lineages

A disguised draft — an improve whose parent is `c0000`, or a crossover with `c0000`
as a parent — counts as an opening approach. **Neither arm had one: both are 4
planned + 0 via the baseline.** (This is the confound that made the drafts pair hard
to read; it did not occur here.)

**mixed — 4 planned + 0 via the baseline.**

| root | kind | members | best search fitness | ever held the running best | approach |
|---|---|---|---|---|---|
| c0004 | planned draft | 12 (c0004, c0006, c0007, c0009, c0011–c0018) | 0.986938 | yes | name-span-only hashed 2/3-gram memory after block 3 |
| c0002 | planned draft | 4 (c0002, c0005, c0010, c0019) | 0.947266 | yes | canonicalised-token sparse hashed table after block 2 |
| c0003 | planned draft | 2 (c0003, c0008) | 0.741455 | yes | hashed 2/3-gram memory plus 48 self-written paraphrase templates |
| c0001 | planned draft | 1 (c0001) | 0.572021 | yes | hashed 2/3-gram memory after block 2 |

**D4 — 4 planned + 0 via the baseline** (c0004 8 members / 0.803833; c0003 7 /
0.753296; c0002 3 / 0.373291; c0001 1 / 0.587158; full table in `mechanical.md` §5).

- **The frozen candidate descends from the best draft in both arms.** Mixed c0016 is
  an improve of c0006, a crossover of c0004 and c0003 whose first parent is c0004 —
  the 0.964966 draft. D4's c0017 likewise sits in its c0004 lineage.
- **Slots spent on the best draft's lineage:** mixed **11 of 15** improve/crossover
  slots (0.733); D4 **7 of 15** (0.467). The mixed arm concentrated; D4 spread.
- **Distinct opening approaches:** 4 in each arm, 0 candidates in no lineage in
  either.
- Search progress, best fitness after 4 / 8 / 20 settled: mixed **0.695801 /
  0.976074 / 0.986938**; D4 **0.676514 / 0.765503 / 0.803833**. The arms are level
  after four candidates — the mixed arm's fourth draft c0004 had not yet settled at
  index 4 — and separate immediately afterwards.

## 5. The kill criterion does not fire

Fixed before launch: *if the mixed arm's cost per candidate is within 10 % of the
all-Sonnet control's **and** none of its four drafts reached a higher search fitness
than the control's best draft, the per-operator model split bought nothing measurable
on this task and is not pursued further here.*

- **Half A — does not hold.** $0.7876 against $0.6886 is a relative difference of
  **14.38 %**, outside the 10 % band. The mixed arm is measurably dearer.
- **Half B — does not hold.** c0004 reached 0.964966 on the search split, above D4's
  best draft c0004 at 0.709717.
- **The criterion does not fire.** Both halves fail, so it would not fire even read
  as "or". The per-operator model split is not killed on this task by this arm.
  Equally, nothing here establishes that it is worth its price: see §10.

## 6. Secondary measures

**Requested vs served, per session and per operator.** 19 of 19 worker sessions
served exactly the model requested for their operator — `draft` → `claude-opus-5`
(4 sessions, source `campaign.toml worker_model_by_operator.draft`), `improve` (13)
and `crossover` (2) → `claude-sonnet-5` (source `campaign.toml worker_model`). D4:
19 of 19 → `claude-sonnet-5`. `claude-haiku-4-5-20251001` alongside in all 38
sessions. 0 sessions with an error flag, 0 `api_error_status`, 0 rate-limited in
either arm.

**The governor.** 0 pauses, **0.00 h waiting on usage = 0.0 % of wall clock**, peak
window estimate **34.06 %** of the $48 budget, 0 rate limits, 0 hard kills, 0 jobs
deferred, 0 re-dispatched. The soft gate at 0.70 never came near firing — as the
amendment predicted, and unlike D4, which paused once for 643 s (7.8 % of its wall
clock) at a peak of 70.76 % against its tighter $20 budget. The $2.55 flat
reservation over-reserved for the 15 Sonnet sessions, as PREREG said in advance it
would; the arm's actual spend, $15.75, is a third of the $48 window budget.

**Cross-branch coverage under findings-v2.** **Full — 0 violations.** Over the 19
jobs that carried cards: every job's pack held its direct parent(s) (0 parent
violations), and once ≥ 4 cards had **ended** before dispatch, every job saw ≥ 2
cards from outside its lineage — 0 violations whether or not the baseline's card
counts as out-of-lineage. "Cards that existed at dispatch" is computed from `ended`
times, not candidate ids, because with two slots a sibling still in flight has no
card. D4 is likewise 0/0/0 over 19 jobs. Under findings-v2 coverage *must* be full;
it is, so this is not a tooling failure. The mem2 pair's selector defect is not
present.

**The knob ledger** (as the mem2 PREREG reports it, bound 2048 bytes,
`out/memory_config.json`):

| | mixed | D4 |
|---|---|---|
| settled non-baseline candidates | 19 | 19 |
| candidates that wrote the knobs file | 19 | 19 |
| ledger rows carried, total / median / max | 107 / 7 / 10 | 120 / 7.5 / 11 |
| rows dropped by the 2 KiB bound, total / max | **46** / 10 | 33 / 8 |
| jobs with at least one dropped row | 7 of 20 | 6 of 20 |
| ledger bytes, median / max | 1249 / 2047 | 1263.5 / 2017 |

The bound bites in the same way it did in mem2: from job c0013 on, rows are dropped,
and by c0019 ten of the seventeen available rows are gone (`c0013` 10 carried / 1
dropped, rising monotonically to `c0019` 7 carried / 10 dropped). This arm is the
one the mem2 read named as misleading workers; the defect is unchanged here, and the
ledger-v3 work in `NEXT.md` is not affected by anything in this bundle.

**Valid candidates per GPU-hour** (all 20 settled candidates completed, so valid =
settled): mixed **4.19**, D4 **4.60**.

**Exec counts.** mixed: completed 20, invalid 0, failed 0, killed 0, deferred 0,
re-dispatched 0. D4: identical.

**GPU per candidate, as a covariate.**

| arm | GPU | candidates | best search fitness | mean / median lease (min) |
|---|---|---|---|---|
| mixed | 0 (RTX 3090) | 10 (c0000, c0002, c0004, c0005, c0008, c0010, c0012, c0014, c0016, c0018) | 0.986938 | 14.16 / 15.27 |
| mixed | 1 (RTX PRO 4000) | 10 (c0001, c0003, c0006, c0007, c0009, c0011, c0013, c0015, c0017, c0019) | 0.978149 | 14.46 / 14.27 |
| D4 | 0 | 10 | 0.765503 | 12.54 / 13.76 |
| D4 | 1 | 10 | 0.803833 | 13.56 / 14.02 |

The split is exactly 10/10 in both arms. The mixed arm's four drafts split two per
card (c0002, c0004 on GPU 0; c0001, c0003 on GPU 1), so the best draft's card is not
confounded with a single-card advantage. Frozen: mixed c0016 on GPU 0, D4 c0017 on
GPU 1.

## 7. The two-slot throughput read (reported only, no threshold)

Added by the amendment as the cheapest next look at the M4 cause; **no threshold
attaches to it and it changes nothing about the M4 read that already fired in the
drafts pair.**

| arm | slots | settled | lease-hours | settled / lease-hour | wall (h) | settled / wall-hour | lease s med/mean | training s med/mean | lease − training s med/mean |
|---|---|---|---|---|---|---|---|---|---|
| `engram-mixed-w0` | 2 | 20 | 4.771 | **4.19** | 2.431 | **8.23** | 886 / 903.3 | 540.1 / 541.1 (n=19) | 345.8 / 362.1 |
| `engram-drafts4-w0` (D4) | 2 | 20 | 4.350 | **4.60** | 2.284 | **8.76** | 841 / 823.5 | 480.1 / 480.1 (n=11) | 299.9 / 326.6 |
| `engram-mem2-legacy-w0` | 1 | 20 | 4.234 | **4.72** | 4.794 | **4.17** | 751 / 761.4 | 540.0 / 514.8 (n=19) | 225.9 / 285.8 |
| `engram-mem2-findings-w0` | 1 | 20 | 3.667 | **5.45** | 3.698 | **5.41** | 706 / 693.9 | 540.0 / 492.0 (n=15) | 181.0 / 179.8 |

`gpu_seconds` equals the sum of the per-candidate leases exactly (difference 0.0 s)
in all four arms, so "GPU-hours" is slot-lease hours, as §5 of the drafts result
established.

### What this adds

- **It reproduces the drafts pair's pattern on a third two-slot arm.** 4.19 settled
  per lease-hour is below both one-slot references (4.72 and 5.45) — the same side of
  the M4 line, and the same figure as D1's 4.19.
- **On wall-hours the ordering reverses, again.** 8.23 and 8.76 settled per wall-hour
  on two slots against 4.17 and 5.41 on one: a 1.5–2.1 × speed-up in the thing a
  human waits for. This is the same contrast the drafts result inferred; it is now
  measured on a third arm.
- **The non-training part of the lease is again where the extra time sits**, and again
  it grows with slots: 345.8 s (mixed) and 299.9 s (D4) at the median against 225.9 s
  and 181.0 s on one slot. The mixed arm's figure is the largest of the four.
- **It does not isolate the cause, and it adds one confound of its own.** The mixed
  arm's workers chose a **540 s** training budget where D4's chose **480 s**; 60 s of
  the mixed arm's 45 s-longer median lease is that choice, not contention. So the
  mixed-vs-D4 lease comparison is not clean, and the mixed arm's lower settled
  per lease-hour is partly a training-budget difference. Against the one-slot arms,
  which also trained 540 s, the non-training gap (345.8 s vs 225.9 s and 181.0 s)
  survives that correction, which is the part that generalises.
- **D4's training seconds are recorded by only 11 of its 19 candidates** (the other 8
  wrote a `wall_seconds` of 18–27 s, which is a prediction-pass wall, not a training
  wall), so D4's training and non-training medians rest on a partial sample. The
  mixed arm's rest on 19 of 19.
- **Slot idling is still not the explanation.** Two leases were open for **96.8 %** of
  the mixed arm's wall clock (D4 91.1 %); slot occupancy, leases / (2 × wall), is
  **0.981** (D4 0.952) against 0.442 and 0.496 on one slot. Turn counts are
  comparable (median 21 / 19 / 22 / 16). Usage waiting is 0 s here and is outside any
  lease in every arm.

**What it does not add to the M4 diagnosis.** It still cannot separate host
contention from anything else: nothing here measures GPU busy time, CPU contention or
tool-call latency directly. The drafts result's inference — one 20-core host running
two worker sessions and two trainings — remains an inference. A measure that
separates agent time from GPU time must be fixed in the next preregistration before
the M4 question is asked again. This arm ran on two slots as the disclosed exception
the amendment granted; the plan (§6) has the `mem3` pair run on two slots too, under its
own disclosure, because the memory question does not depend on lease accounting and wall
clock halves. The M4 read itself stands as written until a measure that separates agent
time from GPU time has been fixed and read.

## 8. Leakage checks

Run exactly as in the drafts result, over all four arm directories.

- **Every weight file postdates its candidate's dispatch and its code copy.** 19
  `code/memory.safetensors` files in the mixed arm; 0 violations (0 in D4, 0 in both
  mem2 arms too).
- **All weight files are pairwise distinct by sha256** — 19 files, 19 distinct hashes
  in the mixed arm (same in each of the other three). No child is scoring its
  parent's weights.
- **No child's config says it loaded existing weights.** `loaded_existing_weights` is
  `true` in **no** mixed candidate; it is `false` in c0001 and the key is absent in
  the other 18, because their code never writes it (absent is not the same as
  `false`). D4 writes the key nowhere. For contrast, the reload-verification habit
  shows up in the reference arms (8 candidates in mem2-legacy, 4 in mem2-findings).
- **No candidate's code reads another candidate's directory.** `grep -rn
  "candidates/" candidates/*/code/` returns nothing in the mixed arm.
- **The frozen candidate reused what it trained.** c0016's weight file is dated
  11:20:31Z, inside its own 11:07:40Z–11:22:26Z lease and well before the final run
  (11:37:17Z–11:37:57Z), so the final read loaded the trained memory rather than
  retraining it, as the contract requires.
- **The two suspicious jumps are explained from the code.** The largest single-step
  gains in the mixed arm are c0010 (improve of c0002, 0.597168 → 0.947266, +0.350)
  and c0005 (improve of c0002, → 0.913330, +0.316). Both `summary.md` files describe
  the same one-line change in two variants — restricting the memory's hash keys to
  tokens inside a person-name span found from `entities.json` (c0005 permanently,
  c0010 as a 0.5 training-time dropout on non-name tokens) — which is the same idea
  the best draft c0004 built from scratch. The signal is entity metadata present in
  every split, never an answer; both candidates trained fresh (`no prior
  code/memory.safetensors`), and their weight files are distinct from c0002's and
  from each other. This is the mixed arm's version of the canonicalisation jump that
  drove both drafts arms, and it is not leakage.

## 9. Odd things found, as observations

- **The Opus drafts were cheap because they were short, not because Opus is cheap.**
  The four Opus draft sessions used 9–15 turns (median 10.5) and 16.1–19.7 k output
  tokens, against D4's four Sonnet drafts at 19–23 turns (median 20.5) and 27.5–38.8 k
  output tokens. Cached input differs by more than 4 ×: 257–426 k cache-read tokens
  per Opus draft against 1.14–1.37 M per Sonnet draft. Whatever the model split buys,
  on this task it did not buy it by spending five times the money — it spent 1.20 ×.
  This is an observation about four sessions, not a rate.
- **No session exceeded the turn cap here.** `worker_max_turns = 40`; the maximum
  reported `num_turns` is 32 (c0008 and c0016). The SDK-vs-cap discrepancy the drafts
  result flagged (D1 c0003 at 45) did not recur, so it remains unconfirmed rather than
  resolved.
- **Every session still logs a failed SessionEnd hook.** All 19 `session.stderr`
  files are 130 bytes and hold exactly `SessionEnd hook [node
  "${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs" SessionEnd] failed:
  /bin/sh: 1: node: not found`. Cosmetic — no session is flagged `is_error` — but
  `session.stderr` is non-empty for all 19 sessions and still cannot be used as an
  error signal. The hook is a user-level Claude Code plugin, not the arm's; the fix
  (node on the sanitized `PATH`, or the plugin disabled for workers) is already in
  `NEXT.md` and was not applied before this arm ran.
- **12 denied tool calls across 9 sessions, all Bash, all benign.** Eight are
  `rm -rf`/`rm -f` of the session's own scratch or its own weight file
  (`/tmp/c0007_smoke`, `out/smoke`, `candidates/c0008/code/memory.safetensors`), which
  the operator's permission rules deny here. Four are attempts to read or copy another
  candidate's `code/` (`cp candidates/c0006/code/engram.py …` in c0009 and c0016,
  `diff -rq candidates/c0007/code …` in c0007, `grep -n "clip\|gnorm" candidates/
  c0016/code/engram.py` in c0018). All were blocked; the harness had already placed
  the inherited parent code in each candidate's own dir, so nothing was lost. It is
  worth noting that the only cross-candidate accesses attempted in this arm were
  denied.
- **One non-fatal CUDA caching-allocator OOM** is recorded in c0010's `summary.md`
  during held-out prediction; the allocator recovered and the run exited 0. On a
  two-slot host this is the kind of event that would become fatal on a busier card.
- **`config.json` records `git_dirty: true`** for every candidate, with
  `git_commit: 61f6866` — that is the arm clone's own commit, not labloop's; the
  tools were synced from labloop `b9bdecd` per `LAUNCH.md`. The dirty flag is
  expected (the run writes into its own working tree) but means the commit alone does
  not pin the arm's state; `SHA256SUMS` does, and it matched at launch.
- **The `max_candidates` guard did what the amendment said.** 20 settled exactly,
  19 non-baseline, 15 improve/crossover slots — matching D4 and not D1's 21. The
  fix (`b9bdecd`) behaved as intended under two slots.
- **The mixed arm's Sonnet sessions cost more than D4's** ($0.7783 vs $0.6911 mean
  over 15 sessions each). Both are Sonnet, same task, same seed, same slots. Not
  measurable from the retained evidence why; it is noted because it, not the Opus
  drafts, accounts for most of the $1.98 total difference between the arms
  ($1.31 of it, against $0.67 from the drafts).
- **Event feed.** 43 events, longest `msg` 122 characters, within the 140-char bound;
  20 launches, 20 dones, one start, one note, one stop. 20 `finding.json` and 20
  `fitness.json` files, one per settled candidate.

## 10. What is and is not claimed

- The mixed arm's frozen candidate cleared the threshold fixed before launch
  (0.997192 ≥ 0.50). That is the whole of the preregistered claim, and it is a
  feasibility claim for this one arm.
- The +0.151611 final-score difference against D4 is **not** a result. One arm, one
  seed, one world, **no order draw** (this arm was run last, by itself), and the
  comparison is against a single run. Reads 2, 3 and 4 are descriptive by
  preregistration; none of them is a test.
- The kill criterion written to end the idea did not fire, on both halves. That
  means the idea is not killed here — **not** that Opus drafts are worth their price.
  This bundle can show what the mixed configuration costs (14.4 % more per candidate
  than its control) and that it cleared the task threshold; it cannot show that the
  model split caused the higher scores. A draft's search fitness is one sample from
  one seed on one world.
- The all-Opus reference was never run, so the question the mixed arm was designed to
  bracket — how much of an all-Opus arm's quality it buys — **is not measurable from
  the retained evidence**.
- The throughput read is reported without a threshold and does not revise the M4
  criterion, which fired in the drafts pair and stands as written.
- No prose rating is involved in this bundle, so there is no blinding step and no
  rater; every measure above is mechanical and reproducible from the arm directories
  with `scripts/mixed_mechanical.py`.

## 11. Procedure as executed

1. Read `../labloop-mixed-20260914/PREREG.md` whole, including the "Amendment before
   launch", plus `LAUNCH.md` and `SHA256SUMS`, before looking at any result.
2. Control integrity and the campaign diff:

   ```sh
   sha256sum ../labloop-drafts-4-20260914/population.json
   grep 'drafts-4' ../labloop-mixed-20260914/SHA256SUMS
   diff ../labloop-drafts-4-20260914/campaign.toml \
        ../labloop-mixed-20260914-arm/campaign.toml
   ```

3. The mechanical read. `scripts/mixed_mechanical.py` is new and reuses
   `scripts/drafts_mechanical.py`'s functions (`arm_facts`, `lineages`, `progress`,
   `coverage`, `gpu_covariate`, `timing`, `session_anomalies`, `weight_checks`,
   `approach_line`); it adds the per-session requested-vs-served check, the cost
   split, the knob-ledger counts, the weight hashing, the per-wall-hour throughput
   figures and this arm's kill criterion. It also widens the training-seconds key
   list, because **this arm's candidates wrote three different keys** —
   `train_wall_s` (12 candidates), `train_wall_seconds` (7, of which 6 also wrote
   `train_seconds`) — where `drafts_mechanical.py` looks only for `train_seconds`.
   Without that widening the arm's training seconds would have read as missing.

   ```sh
   python3 scripts/mixed_mechanical.py \
     --arm ../labloop-mixed-20260914-arm \
     --control ../labloop-drafts-4-20260914 \
     --ref ../labloop-mem2-legacy-20260914 \
     --ref ../labloop-mem2-findings-20260914 \
     --md docs/mixed-comparison-20260915/mechanical.md \
     --json docs/mixed-comparison-20260915/mechanical.json
   ```

4. The two checks not in the script, shown because §8 rests on them:

   ```sh
   cd ../labloop-mixed-20260914-arm
   grep -rn "candidates/" candidates/*/code/          # no output
   stat -c '%n %y' candidates/c0016/code/memory.safetensors
   ```

5. Everything in §§1–10 is taken from that output or from those commands. No label,
   split or file under `/srv/labloop-private` was read; no file in any arm directory
   was written, touched or modified. The final score is the one `lab run` recorded in
   its single read of the final split.
