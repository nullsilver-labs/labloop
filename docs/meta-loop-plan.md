# labloop on labloop — a plan (2026-10-17)

Status: **draft for the human's review. Nothing here is built or launched.**
Written from tools at `6fc4772`. Every number carries the file it comes from; a number
marked *computed* is arithmetic on cited numbers, and one marked *estimate* has not been
measured by anything in this repo or its sibling campaigns. Paths starting `../` are
sibling dirs of this repo.

## 0. The question, and why it is not the first experiment

The idea is to run labloop's search loop on labloop itself. The candidates would be
variants of the policy: how parents are chosen, what a worker is told, what memory it
sees, which tools it has. The ideas on the table are web search for workers, an LLM
scheduler, and an agent forum moderated by a bigger model.

A search is only as good as its fitness. labloop's fitness on a task is cheap to read,
because a hidden split and a score script give it. A fitness for a *harness* is
different: it is a whole campaign, or several, read through a final split. The
evidence so far says that number is noisy:

- Nine Sonnet arms on the same engram w0 task, with harnesses that differ in one memory
  or drafting knob, finished between **.644 and .998** on the final split (sd .121,
  *computed* from the finals in `docs/memory-comparison-20260913/mechanical.md:13-16`,
  `docs/mem2-comparison-20260914/mechanical.md:14-17`,
  `docs/mem3-comparison-20260915/mechanical.md:15-17`,
  `docs/drafts-comparison-20260915/RESULT.md:17-18` and
  `docs/mixed-comparison-20260915/RESULT.md:92`).
- One draw of the opening approach moved a final by **.15**
  (`docs/drafts-comparison-20260915/RESULT.md:236-240`;
  `docs/mem3-comparison-20260915/STATUS.md:113-114`).
- The memory pair read **supported / not_supported / supported** over three seeds
  (`docs/mem3-comparison-20260915/RESULT.md:71-75`). The flip had a mechanical cause,
  not a statistical one (`docs/mem2-comparison-20260914/RESULT.md:59-88`), but no arm
  has ever been repeated at the same seed.
- The M2 search-vs-greedy pair read **D = +.0044**, one standard deviation of a
  difference at n = 5000 (`NEXT.md:127-130`).

An automated meta-search over a fitness whose noise floor is unknown would select on
noise, and it would spend the usage window doing it. So the order of work is:

1. Split the trusted core from the policy surface (§1).
2. Build a small benchmark suite, **labbench**, under preregistered admission rules (§2–§4).
3. Fix the meta-fitness before any run (§5).
4. Measure the frozen commit's noise floor on the suite (§6).
5. Hand-run A/B pairs of single ideas (§9).
6. Automate only if step 4 says the suite can see the effects step 5 finds.

The user added two constraints, and they drive most of the choices below: **the suite
must be cheap**, and **its tasks must not be easy for today's frontier LLMs**.

## 1. Trusted core vs policy surface

A meta-candidate is untrusted code that runs *inside* the loop. That is new. Today the
only untrusted code runs as a worker, under the guard and the watcher. Anything a
meta-candidate can change, it can also use to cheat, so the line has to be drawn by what
can cheat, not by what is convenient.

### 1a. Frozen: never supplied by a candidate

| what | where today | why frozen |
|---|---|---|
| scoring, the only label reader | `evaluate` `tools/lab_campaign.py:1425-1464`; `cmd_eval` refuses `--split final` (`:1475`) | it *is* the fitness |
| final split read once | `run_final` `tools/lab_campaign.py:1723-1779` (early return `:1741`; `evaluate` idempotent `:1429`) | one read supports a claim |
| label hiding | `labeval` user and `/srv/labloop-private` (`docs/labeval.md:18-33`); `worker_env` strips `LAB_PRIVATE` (`tools/lab_campaign.py:844-873`); `_private_paths` scrub (`:1257`); guard regex (`.claude/hooks/guard.sh:193-195`); Pi copy (`tools/pi/lab-worker.js:27`) | same |
| single writer of `population.json`, `LEDGER.md`, `events.jsonl`, `finding.json` | `save_pop` `tools/lab_campaign.py:509-526`; `ledger_upsert` `tools/lab:479-501`; `emit`/`append_event` `tools/lab:191, 243-286`; redaction `tools/lab:170-188`; card writer and validator `build_card`/`validate_card`/`check_card_sources` `tools/lab_findings.py:430, 659, 874` | evidence is immutable |
| the watcher | `cmd_watch_start`/`cmd_watch_run` `tools/lab:662-870`; subreaper and pidfd containment `tools/lab_process.py:18-77` | budgets are enforced, not requested |
| usage accounting and governor | `usage_state` `tools/lab_campaign.py:1515-1574`; `govern` `:1585-1629`; `defer_job` `:1496`; `read_session` `:1002`; `session_kill_regex` `:876` | the window is a shared resource across the inner and outer loops |
| worker contract checks | `settle` `tools/lab_campaign.py:1103-1204` (forged card `:1118-1122`, predictions `:1123-1128`, exit 2 `:1151`); wrappers `tools/lab-worker:85-103`, `tools/lab-worker-pi:87-106` | "completed" must mean the same thing in every arm |
| the guard | `.claude/hooks/guard.sh:1-250`, wired in `.claude/settings.json:13-31` | read scope, write scope, detach, labels |
| caps and freezes | `max_candidates` (`tools/lab_campaign.py:1711`, `:2003-2008`); slots and leases (`:1936-1969`); campaign hash (`:187`, refusal `:2043-2047`) | a candidate must not buy itself more budget |
| the child-never-inherits-weights copy | `new_candidate` copy step, `tools/lab_campaign.py:748-754` | a parent is never scored twice |

### 1b. Mutable: what a meta-candidate may supply

| knob | where today |
|---|---|
| scheduler and parent selection | `rank_select` `tools/lab_campaign.py:1632-1644`; the policy half of `choose_job` (`:1676-1703`); `[selection]` keys parsed at `:265-284` |
| operator prompts | `OPERATOR_TEXT` `tools/lab_campaign.py:85-100`; the card assembly in `new_candidate` (`:789-837`) minus the contract fields; `render_job_card` (`:2197-2243`); `SUMMARY_FORMAT` `tools/lab_findings.py:1515`; the worker brief in `.claude/hooks/session_start.sh:32-46` |
| memory and finding selection | `select_context` `tools/lab_findings.py:964-1150`, `select_index_context` (`:1181`), the renderers (`:1244-1486`), the limits (`:71-101`) |
| the index | which `lab index` subcommands a worker may call (`tools/lab_index.py:584`); ranking in `search`/`lexical`/`vector` (`:342-389`) |
| worker tools and model | `worker_model_for` `tools/lab_campaign.py:705`; `[resources] worker_model`, `worker_model_by_operator`, `worker_max_turns`; CLI flags in `tools/lab-worker:63-68`; Pi turn countdown and clip in `tools/pi/lab-worker.js` |

### 1c. Where the two are tangled today

The code map found eight entanglements. Four of them matter for this plan:

1. **`new_candidate` does everything** (`tools/lab_campaign.py:716-841`). It selects
   memory, creates dirs, copies code without weights, draws the seed, writes
   provenance, assembles the card and registers the candidate, all in one function.
2. **`contract.may_read` is both prompt text and access control.** The card's
   `may_read` (`tools/lab_campaign.py:817-824`) is what the guard reads to widen a
   worker's read scope (`.claude/hooks/guard.sh:36`). A policy that wrote the card
   would also write its own permissions. The index has the same loop:
   `log_query` writes `queries.jsonl` (`tools/lab_index.py:550-565`), and the guard
   widens reads from it (`guard.sh:45`).
3. **`choose_job` mutates core state.** It pops deferred jobs, which is the governor's
   re-dispatch (`tools/lab_campaign.py:1655-1658`), and sets `debugged`
   (`:1668, 1675`).
4. **The tools are not under the campaign hash.** `campaign_sha256` covers
   `campaign.toml`. `git_commit`/`git_dirty` in `config.json`
   (`tools/lab_campaign.py:757-758`) are the only record of which `tools/` ran.

There is a fifth, which is a security problem rather than a design one. The sudoers
line grants `labeval` **`python3` in general** (`docs/labeval.md:36-37`). Policy code
loaded into the `lab run` process runs as the operator user, who may call
`sudo -n -u labeval python3` with any script and read every label. This is item 1 of
`NEXT.md`'s priority list already. Under a meta-loop it stops being a hardening
nicety: it is the first thing a meta-candidate would find.

### 1d. The refactor

The goal is a **policy module a candidate dir can supply**, with no change in behaviour
for the default module:

- `policy/` holds `policy.py` and an optional `policy.toml`. It runs in its own process,
  as a user with no sudo rights (a `labpolicy` user, or the no-network container
  `../labloop-compress` already uses). It talks JSON over stdin and stdout and is
  never imported into `lab run`.
- The interface has four calls, each pure:
  - `select(view, rng_seed) -> {operator, parents}`. `view` is a read-only copy of
    the population: ids, operators, parents, search fitness, status, summaries. The
    core handles deferred jobs and debug retries *before* the call, then checks that
    the operator is known and the parents exist.
  - `memory(cards, parents, limits) -> {text, card_ids}`. The core adds `card_ids`
    to `may_read`; the policy never writes `may_read` itself.
  - `card(job, memory_text, task) -> {instructions, extra}`. The core appends the
    contract (`may_read`, `may_write`, predictions, seed, max turns), so a policy
    cannot rewrite it.
  - `worker(operator) -> {model, max_turns, index_commands}`, validated by the core
    against an allowlist (`backend_for`, `tools/lab_pi.py:29`).
- `new_candidate` splits into core steps plus one policy call. `lab_findings.py`
  splits into a core half (build, validate, ensure) and a policy half (select,
  render).
- The policy dir's hash goes into `population.json` next to `memory_snapshot`
  (`tools/lab_campaign.py:603`). A changed policy under a running campaign is
  refused, the same way a changed `campaign.toml` is.
- `tools/` and the hooks are pinned by commit, and `lab run` refuses a dirty tree when
  `[meta]` is set.
- **The gate:** the default module, replayed against the recorded populations of the
  drafts, mem2 and mem3 arms, must pick the same `(operator, parents)` and render
  byte-identical job cards at every tick. `scripts/mem_replay_selector.py` and
  `scripts/orchestrator_replay.py` already do half of this. The no-LLM acceptance
  count must not drop (478 passed on 2026-09-15, `NEXT.md` "Current no-LLM
  acceptance").

## 2. labbench admission criteria (preregistered, mechanical)

A task enters labbench only by passing all five rules below. The thresholds are
**proposals**: the human fixes them before the first probe, and a changed threshold
is a new suite version.

### (a) Cost: CPU-minutes, small usage budget

- The inner evaluation of one candidate on one split takes **≤ 10 CPU-minutes on one
  core** (proposal), runs in the no-network container, and needs **no GPU training**.
  `../labloop-compress` sets the template: 60 s on one core each way, 8 GB, no network,
  no GPU (`../labloop-compress/task.md:18-28`), with an eval timeout of 10 min at worst
  (`../labloop-compress/campaign.toml:22`).
- Generating a fresh instance takes **≤ 5 CPU-minutes** (proposal).
- **One inner campaign has 12 candidates**: c0000 plus 11 worker sessions. The
  baseline has no session (`../labloop-mem2-legacy-20260914/REPORT.md:55` shows 20
  sessions for 20 candidates only because of a re-dispatched deferral; every other
  20-candidate arm shows 19).

The usage window binds, not compute. Here is what one Sonnet session cost in past
campaigns:

| campaign | $ list-price / sessions | mean $ per session (*computed*) | median (reported) | source |
|---|---|---|---|---|
| m2 (CIFAR) | 15.11 / 39 | .39 | .39 | `../labloop-m2/REPORT.md:70-71` |
| mem2 findings | 9.26 / 19 | .49 | .47 | `../labloop-mem2-findings-20260914/REPORT.md:54-55` |
| mem2 legacy | 11.55 / 20 | .58 | .57 | `../labloop-mem2-legacy-20260914/REPORT.md:55-56` |
| drafts D1 | 14.10 / 20 | .71 | .66 | `docs/drafts-comparison-20260915/RESULT.md:101` |
| drafts D4 | 13.77 / 19 | .73 | .67 | `docs/drafts-comparison-20260915/RESULT.md:102` |
| mem3 legacy | 14.58 / 19 | .77 | .69 | `../labloop-mem3-legacy-20260915/REPORT.md:54-55` |
| mem3 findings | 15.46 / 19 | .81 | .75 | `../labloop-mem3-findings-20260915/REPORT.md:54-55` |
| mixed (Opus drafts) | 15.75 / 19 | .83 | .83 | `../labloop-mixed-20260914-arm/REPORT.md:54-55` |

The governor's calibration is `session_cost = 0.48`, the pooled median of the mem2
sessions (`../labloop-drafts-1-20260914/campaign.toml:53`). It under-estimated the
next arms by about half (`docs/drafts-comparison-20260915/RESULT.md:101-103`), and the
cost per session has risen since m2. So the plan uses a range:

- **One inner campaign costs $5.3–$9.1 list-price** (*computed*: 11 sessions × the $0.48
  calibration to the highest mean, $0.83).
- **Wall clock is about 1.2–1.5 h on two slots** (*estimate*). Worker sessions ran a
  median of 11–15 min in the engram arms (*computed* from `candidates/*/session.json`
  in those arms), and CPU tasks need no GPU slot, so two or more slots cost nothing
  extra.

**The window's capacity is not measured.** No token figure is published, and the
procedure for calibrating it is written down but has not been run
(`docs/campaign-setup.md:224-228`). The two data points are:

- the armed `window_budget = 20.0` in the drafts arms
  (`../labloop-drafts-1-20260914/campaign.toml:54`), which is an operator's guess;
- one live limit at the eighth job of mem2-legacy, with other sessions sharing the
  window (`../labloop-mem2-legacy-20260914/REPORT.md:35, 58-60`).

Taking $20 per 5-hour window as a working figure (*estimate*), a window holds **two to
three inner campaigns**. Every budget below is in these units, and the first operator
task in §6 is to measure the window properly.

**Rule:** a task is admitted only if its median inner campaign in the headroom probe
(§4) costs **≤ $10 list-price and ≤ 3 CPU-hours of evaluation** (proposal).

### (b) Headroom: well below a ceiling

The rule compares two attempts against a ceiling `C`: one strong-model attempt in a
single session (best of two), and one short labloop run of 12 candidates. Neither may
get close. With `g = (s − b)/(C − b)`, oriented so that higher is better and `b` is
the baseline:

- **one-shot g ≤ 0.5**
- **short-run best g ≤ 0.8**

Both thresholds are proposals. `C` is either *known*, because the generator gives it
(an entropy bound, a planted optimum, a noise level), or *estimated* by a
reference run with no time limit that the task's own budget forbids. engram had such
references: LoRA .9653 and a full fine-tune .9961
(`../labloop-engram/data/train/reference/RESULTS.md:11-12`). A task whose ceiling
can be neither computed nor estimated is not admitted.

**Amendment, 2026-10-17, made after the first probe and disclosed as such.** For
compression families, `b` in rule (b) is a *frozen generic compressor*, the gauge, and not
the task's trivial baseline. The trivial baseline (`xz -9e`) stays c0000 of every campaign
and stays in every report. The reason is the hsrc-v0 probe
(`../labloop-hsrc-oneshot-20261017/READ.md`): one Sonnet 5.5 draft reached g = .679
against xz while missing most of the hidden structure. Its plain
context mixer alone sat at the .5 line. Offline tuning of a harder generator (hsrc-v1)
left that mixer at g ≈ .45–.55 against xz on every setting tried
(`../labbench/README.md`). Against xz, rule (b) measures how weak LZ is on text with
skewed character statistics, not how much of the source a one-shot has discovered. The
gauge is c0001's mixer from that probe, without its layout transform, frozen in
`../labbench/gauges/c0001-cm/`. The thresholds are unchanged: one-shot g ≤ .5 and
short-run g ≤ .8, now measured as `g = (gauge − s)/(gauge − C)`. Rule changes after this
one are a new suite version.

### (c) The harness must matter

- **The anytime curve rises.** In the short run, best-so-far at candidate 12 minus
  best-so-far at candidate 4 must be **≥ 0.10 in g** (proposal). The engram arms
  mostly fail this: mem3 findings was flat at .7499 from candidate 8 to 20
  (`docs/mem3-comparison-20260915/mechanical.md:14-15`), and D1 stood at .9922 by
  candidate 4 (`docs/drafts-comparison-20260915/mechanical.md:76-79`). M2's search arm
  found its best eligible candidate at 20510 s of 34746 s
  (`docs/matched-pair-20260912/comparison.md:7-24`).
- **A crippled harness loses.** The probe adds one run of a deliberately weak policy:
  draft only, no parent and no memory, which is random restarts. The frozen policy's
  best g must beat it by more than the spread between the two frozen runs. If random
  restarts do as well, no policy change can show up on this task.

### (d) Contamination-proof: procedurally generated from a hidden generator

- **Instances.** Every instance comes from a generator with **hidden code and hidden
  parameters**, owned by `labeval`, outside this published repo. The instance seed is
  `H(master_secret, family, purpose, index)`, so every inner campaign gets a fresh
  instance and the held-out final instances cost nothing to make.
- **Hidden code, not just a hidden seed.** cartridge's stance is that the code is
  public and the seed is the secret (`../cartridge/cartridge/data.py:1-4, 47-50`).
  That works for random fact tables. It fails for tasks where *discovering the
  structure* is the point: a worker with web search, or a model that has read this
  repo, would implement the generator.
- **Designs that fail (d).** A public dataset fails. So does a slice of one:
  `../labloop-compress` uses enwik8 (`../labloop-compress/task.md:3-7`), which any
  frontier model has read, and its README argues contamination is harmless only
  because program size counts (`../labloop-compress/README.md:19`). So does one world
  reused across campaigns: every engram campaign points at the same w0 world and
  labels (e.g. `../labloop-mem3-findings-20260915/campaign.toml:19,22`).

### (e) Integrity: opaque ids, no reconstructible labels

The engram w0 lesson comes from `docs/pi-engram-20260916/READ.md`. A Pi lineage keyed
its memory on the question's record id and `attribute` field, not on its tokens
(`:39-49`). Worse, question ids carry the person, so the public `facts.json`
"reconstructs every hidden label, search and final" (`:64-73`). The OS wall around
the label *files* held, but the labels were knowable anyway. Mechanically, then:

1. **Program submission.** Where the task allows it, the candidate submits *code*, and
   the evaluator runs that code on the hidden instance inside the container, as
   `../labloop-compress` does. The worker never holds the search or final inputs, so
   it has nothing to read labels from.
2. **Opaque ids.** Every id the worker can see is a random token. No metadata field
   sits next to an input unless the task statement grants it.
3. **The metadata cheater.** A scripted solver with no model sees only ids, sizes, file
   order and metadata, and predicts. It must score within noise of the baseline. Its
   code is part of the task's admission record.
4. **Held-out structure, not held-out wording.** Search and final instances are fresh
   draws, never new phrasings of training items (the fix list in
   `docs/pi-engram-20260916/READ.md:104-118`).
5. **A swap audit for tasks that keep a frozen reader.** This follows
   `../labloop-reader-20260922/scripts/audit_swap.py:2-18`, run per candidate rather
   than post hoc.

### Why MNIST and CIFAR fail

- **M1 (MNIST)** cleared its threshold at the first draft: c0001 scored .9864 against
  .985, and the final was .9875 (`../labloop-m1/REPORT.md:7-14, 24-28`). That fails
  (b).
- **M2 (CIFAR-10)** cleared .90 at c0001 with .9054, and the best final was .9472 after
  40 candidates (`../labloop-m2/REPORT.md:7-14, 25`). Its own task statement says a
  ResNet reaches 0.90 in ten minutes (`../labloop-m2/task.md:6-8`), and the matched
  pair saturated from about half the budget on. That fails (b) and (c).
- Both are public datasets, which fails (d), and both need GPU training, which fails
  (a).

## 3. Task families to probe

Each family below is a *generator of tasks*. One instance is one inner campaign. All
costs are *estimates* until the probe in §4 measures them.

### 3.1 Compression of a hidden structured source (successor of `../labloop-compress`)

- **Task.** Lossless compression of text sampled from a hidden generator: a random
  grammar with latent state, long-range agreement and templated records with hidden
  field dependencies, drawn fresh per instance. Score = (archive + code bytes) /
  text bytes, as in `../labloop-compress/task.md:3-7`.
- **Cost.** It reuses the existing docker evaluator as `labeval`, which is CPU only, 60 s
  each way (`../labloop-compress/task.md:18-23`). An xz candidate took 1.5 s to
  compress (`../labloop-compress-probe-20260917` c0006 `summary.md`). The worst case is
  about 4 CPU-min per split per candidate (*computed* from `campaign.toml:22`).
- **Ceiling: known.** The generator owner can compute the sample's exact code length
  under the true model, −log₂ P(text | params), which is the floor any compressor
  approaches. enwik8 has no such number (`../labloop-compress/README.md:4`, "no
  ceiling"). This is the strongest reason to replace the corpus.
- **Why it has headroom.** xz sits on the structure-blind side of the gap, and the
  bound sits on the other. One shot, a strong model writes a generic order-k context
  mixer. Closing the rest means finding the latent structure from a public dev sample
  and fitting a model of it into 60 s and a counted code size. That is research, not
  recall (*estimate*; the probe measures it).
- **Prior evidence on difficulty.** The Qwen3.8 probe on enwik8 never beat xz. Its best
  was the baseline reproduced (.29346), and 5 of 9 candidates were killed at the 30-min
  wall (`../labloop-compress-probe-20260917/REPORT.md:7-12, 29-36`). That is evidence
  about a weak worker and the wall, not about headroom.
- **Leakage risks.**
  - The public dev sample is necessary, and it carries the structure by design.
  - If the generator family is too narrow, a candidate fits it exactly and the task
    saturates. Rule (b) catches that.
  - If the generator's source is ever readable, the task is spent.
  - A candidate could hard-code dev-sample statistics, which code-size counting charges
    for.

### 3.2 Hidden-rule worlds (engram successor, CPU only)

- **Task.** A world of entities with attributes, some derived by hidden compositional
  rules from others, with exceptions at a known noise rate. The candidate submits a
  *learner*. The evaluator runs it on a fresh world's public part and scores its
  predictions for the held-out entities.
- **Why not reuse cartridge or engram as they are.**
  - cartridge's world is a random fact table: assignments "are not derivable from
    spelling … or another attribute" (`../cartridge/PLAN.md:160-163`). Nothing in it
    can be inferred.
  - engram needs GPU training of a frozen Qwen3-0.6B, up to 10 min of training and a
    20-min `run.sh` (`../labloop-engram/task.md:26-27`), which fails (a).
  - w0 is spent on (d) and (e).
  - What carries over: cartridge's seeded streams, balanced splits and byte-identical
    regeneration (`../cartridge/cartridge/data.py:47-50`; `scripts/make_world.py:11`).
- **Cost.** It needs seconds to generate and CPU-minutes to evaluate (*estimate*).
- **Ceiling: known.** It is one minus the exception rate, the Bayes accuracy under the
  generator.
- **Headroom.** The rule depth and the number of distractor attributes are generator
  parameters, tuned at the probe until the one-shot learner sits at g ≤ 0.5.
- **Leakage risks.** This family has the most engram-shaped risk: opaque entity ids, no
  `attribute` hints beyond the schema, and entities held out, not wordings. The
  metadata cheater (§2e.3) is mandatory here.

### 3.3 Heuristics for generated combinatorial-optimization instances

- **Task.** An unusual problem variant, chosen so no off-the-shelf solver applies
  (routing with time-coupled side constraints, or packing with a hidden interaction
  term, for example). Instances are drawn from a hidden distribution with planted
  structure. The candidate submits a solver, and the evaluator runs it on about 20
  hidden instances at 10 s each on one core (*estimate*: about 3.3 CPU-min per split).
- **Ceiling.** It is *known* when an optimum is planted, and *estimated* otherwise from
  a reference run of a strong general solver at 100× the time budget.
- **Headroom.** A one-shot model writes greedy plus local search. The distance from
  there to the planted structure is the room for research. A standard problem such as
  plain TSP is excluded because the frontier model knows LKH by heart.
- **Leakage risks.** The objective is computed from the candidate's output, so there
  are no label files, only the reference values. The risks are timing exploits, which
  the one-core container with a hard wall handles, and a distribution that is too
  narrow, which (b) handles.

### 3.4 Program or law inference from generated data

- **Task.** Each instance is a hidden program drawn from a DSL whose primitive weights
  and depth distribution are hidden (string transforms, integer recurrences, cellular
  automaton rules, a noisy physical law). The candidate submits an *inference
  procedure*. The evaluator runs it on about 200 fresh programs' training pairs and
  scores predictions on their held-out inputs (*estimate*: about 3 CPU-min per split
  at about 1 s per program).
- **Ceiling: known.** It is the noise level the generator injects.
- **Headroom.** Enumerative search is the obvious one-shot answer. Depth and the hidden
  primitive weights decide how far that gets. The probe tunes them.
- **Leakage risks.**
  - A published DSL invites an exact enumerator, so the task states the primitives
    loosely and the weights not at all.
  - Ids must be opaque.
  - A generator written by the same model family as the worker may carry that family's
    habits; randomising the *structure* per instance, not only its parameters, limits
    this (*estimate* of a risk, unmeasured).

**Suite shape, proposed.** Probe all four families. Admit up to three for the
meta-search split. Hold one family out entirely, read only in the meta-final (§5).

## 4. Headroom probe per task, with kill criteria

Before admission, each task gets one probe, preregistered in its own `PREREG.md`:

| arm | what | cost (*estimate*) |
|---|---|---|
| one-shot | Sonnet and Opus, one session each, task card only, no loop | ≈ 2 sessions |
| short run A, B | frozen labloop, 12 candidates, two instance seeds | 2 × $5.3–9.1 |
| crippled | draft-only, no memory, 12 candidates, instance A | $5.3–9.1 |
| cheater | scripted metadata-only solver | CPU only |

Total cost is **about $17–29 list-price per task, roughly one to one and a half
windows** (*computed* from §2a, *estimate* by the window figure).

**Kill criteria.** Any one rejects the task version. A fix is a new version with a new
probe, and the old probe stays on file.

- **K1 cost:** median eval > 10 CPU-min per split, or an inner campaign > $10.
- **K2 too easy:** best one-shot g > 0.5.
- **K3 saturates:** short-run best g > 0.8 in either run.
- **K4 floor:** short-run best g < 0.05 in both runs. The inner workers cannot get
  started, so no policy can differ.
- **K5 flat:** the anytime rise from candidate 4 to 12 is < 0.10 in both runs.
- **K6 harness-blind:** the frozen best does not beat the crippled best by more than
  |A − B|.
- **K7 integrity:** the cheater scores above baseline + |A − B|, or any candidate is
  found reading or reconstructing labels.
- **K8 operations:** killed + invalid > 25 % of settled in either short run. The
  compress probe had 6 of 9 (`../labloop-compress-probe-20260917/REPORT.md:12`); with a
  frontier worker that rate means the task's wall or wording is wrong, not the policy.

### Admission rules v0.2 (2026-10-17, after the hsrc-v1 probe; they replace K2–K8 above)

**Why they exist, said plainly.** The hsrc-v1 probe
(`../labloop-hsrc1-probe-20261017/READ.md`) failed K5 and K6 because labloop's default policy
lost to draft-only restarts: final gauge g .035 against .307. K5 and K6 as written assumed the
default policy is competent. The first draft of v0.2 relaxed exactly the two rules that would
turn those numbers into a pass. An adversarial review (Fable 5.1, 2026-10-17) called that what
it is, a rule fitted to a result. The rules below are that draft with the review's changes.
Their job is to make the re-probe able to fail and further revisions costly. No other rule was
considered for change before the numbers were seen. Tightening K5 (to .15, for example) was not
considered at all; it is recorded here as not considered, rather than as considered and
rejected.

**The probe gains one arm:** a crippled arm on instance B as well as on A, about $5. The
crippled arms are *blind*: no population table, no "best so far", no other candidate's files.
That needs a job-card mode labloop does not have yet (§7), and the guard fix for the gap
disclosed in that READ, with its acceptance test cited. A crippled arm that can see scores is
a weak memory policy, not breadth.

- **The gauge (K2–K4).** Each family has a frozen generic reference solver, its gauge. Its
  commit hash is fixed in the family's first PREREG, before K2 of its first version, and never
  changes within the family. `g = (gauge − s)/(gauge − C)`, higher is better. The trivial
  baseline stays as c0000 in every campaign and report. If gauge − C < max(.03, 10 % of
  |C|) in the task's units on any probe instance, K4 fires: there is no room to read.
- **K2 too easy:** the best one-shot g > .5 (unchanged, now against the gauge).
- **K3 saturates:** the best g > .8 in any short-run arm.
- **K4 floor:** the *better* policy's best final g < .05 on both instances, or the gauge
  margin above fails.
- **K5 no climb:** in no arm does the best-so-far search g, taken in **settle order**, step up
  at least twice between the 4th and the 12th settled candidate, each step ≥ .03. Also, the
  generator owner records which candidates found each planted structure. If one structure
  explains more than 80 % of the best arm's g, the READ labels the family *single-discovery*,
  and it cannot be one of the two tasks in §6.
- **K6 harness-blind:** on instance A *and* on instance B, compute D = g(frozen) −
  g(crippled). K6 fires unless both D have the same sign and both |D| > max(|g(A) − g(B)|,
  .10), where A and B are the frozen arms. It is read twice: on g, and on g per list-price
  dollar of the arm. Both readings must clear the line, in the same direction. A task where
  spending more per candidate wins, whatever the policy, does not pass. Per-arm $ goes into
  `k_values.json`.
- **K7 integrity and K8 operations:** unchanged.
- **Weighting.** §5's `mean_t(g_t)` weights families by how strong their gauge is. That is
  kept as a convention, stated here; per-family z-scores are the alternative if it bites.

**The commitments that make this costly to revise.**
1. A rule revision after v0.2 re-probes every admitted family on fresh instances.
2. hsrc-v1 gets exactly one re-probe under v0.2, on instances never used before, with the
   K6 direction *predicted* in its PREREG: crippled > frozen. If it fails, the family is out
   and no v0.3 is made from it.
3. v0.2 is first read on a family whose numbers no one has seen. That family's probe is
   read before hsrc-v1's re-probe.
4. The rule changelog lives here. It holds 2 revisions so far, both made on 2026-10-17
   after the first probe: the gauge for compression K2 (§2b), and v0.2.

### Admission rules v0.3: ADOPTED 2026-10-18, after popt's v0.2 READ (proposed 82be6bc)

**Adoption note.** popt's v0.2 READ (`../labloop-popt-probe-20261017/READ.md`) was written first, as
v0.2's commitment 3 required. popt is not admitted under either version (K3, K5, K6). v0.3 is
adopted with **one change, procedural, not a scoring line**:

8. **Every arm runs in a dir Claude Code trusts.** The popt READ found that no campaign dir since
   pinf was trusted: trust on a parent dir does not carry over, so lab-worker ignored the project's
   `permissions.allow` in every job of the pinf, pair-1, hrw and popt arms. Each new campaign
   dir's trust is set before launch (the human's step), and the launch checks it. An arm that logs
   "ignoring … permissions.allow entries" is flagged in its READ.

popt's other lessons are about generator design, not admission: the per-instance lottery over one
planted key, and the need for several independent, graded structures. They go to §2 and §3's
family work, not into a new line. Two things must exist **before the next probe runs**: the
blind-card change of item 3 (the population table showing c0000), and the standalone one-shot arm
of item 2.


**The objection** (the user, 2026-10-17, after the hrw K2 read): "isn't it obvious that better and
better LLMs will start to find solutions in one step? We are not benchmarking LLMs here." v0.2's
K2 is a gate on model capability. What it protected against is a ceiling effect, and a ceiling is
relative to the worker the harness uses.

**What is disclosed.** K2's removal was proposed after the hrw read. The pattern across three
families was known at the time: Opus one-shots broke hrw (g .73), pinf (.88) and hsrc-v0 (against
xz), while Sonnet stayed lower. v0.3 removes the rule that rejected three of four families and
excludes the model that rejected them. An adversarial review (Fable 5.1, 2026-10-17) said to adopt
it with the changes below, folded in here. v0.2's commitment 3, that its first read is on an
unseen family, is popt. So v0.3 is **proposed** here, its commit hash goes in the changelog, and it
is adopted only after popt's v0.2 READ: unchanged, or with every change listed.

1. **One worker model per suite version: Sonnet 5.5** (`claude-sonnet-5-5`, named in every PREREG).
   If any candidate's served model differs from the requested one, that arm is invalid. An
   admission is a claim about that worker, and it decays with model upgrades (§8). A model is a
   policy knob only inside a policy pair, never inside admission.
2. **Arms:** frozen A and B, blind A and B, 12 candidates each, plus **one standalone one-shot**
   per instance. The standalone one-shot calibrates turns.
3. **The blind arm's card is the one-shot's card**: the same draft text, with the population table
   showing only c0000. Each PREREG records median turns in the blind arm and in the standalone
   one-shot. If the blind median is under half the one-shot's, the blind arm's K3 reading is
   **void, not passed**. A blind arm that works less than a one-shot under-reports what one
   session can do.
4. **K2 becomes a typical-session line:** the blind arm's *median* per-session final g > .5 fires
   it. The best-of-11 is K3's business. This is a loosening of K2, not a removal, and is stated
   as such.
5. **K3:** the best final g > .8 in any arm, blind and one-shot included. **K4–K8** are as in v0.2.
6. **No admission by tuning.** When a generator is re-tuned for a new worker, the tuning instances
   are burned, and the knob values go into the PREREG before the probe runs on fresh instances.
7. **v0.3 is the last revision before §6 runs.** Any change after it is a new programme name, and
   every probe re-runs.

**Families, decided now.**
- **popt:** read under v0.2 as preregistered (primary), with v0.3 beside it. v0.3 cannot rescue
  it, since K3 is the same in both. Before this draft, arm B (frozen, instance 2) had been seen
  with a best search score of exactly 0, the planted optimum. Its c0002 summary describes an exact
  exact solver for the planted structure. Seen about 20:52Z, before any final read. A full K7 audit of that lineage
  comes before any K3 verdict. The K2 one-shots on instance 0 sat at g ≈ .03 while a campaign
  draft found the structure on instance 2. That gap is explained or flagged in the READ.
- **hrw:** one v0.3 probe on fresh instances, after popt's READ and after hsrc-v1's re-probe. Its
  PREREG predicts the blind best-of-11 band and K6's direction. A wrong direction means hrw is out,
  with no v0.4.
- **hsrc-v1:** its promised re-probe (v0.2 commitment 2: crippled > frozen predicted) runs under
  v0.3. Its v0.2 and v0.3 K2 verdicts coincide, since it passed K2 with Opus lowest. That
  coincidence is recorded, not glossed.
- **pinf v0:** not re-probed. Prediction on record: a Sonnet one-shot at .68 means a blind
  best-of-11 saturates. A v1 is a redesign, per its READ.

### Decisions 2026-10-18, after the five-family tally (not rule revisions)

These were made by the operator session with Fable 5.1's review. The user said "ask fable first, do what you 2 decide together". No line of v0.3 changes. Rule 7 forbids quiet revision, not stopping, so what is not run is written down here.

1. **No more planted-key families.**
   - hsrc-v1 and popt were lotteries over one key: found means near C, not found means at the gauge, and the instance sets the odds.
   - hsrc-v0, pinf and hrw (under v0.2) were one search away for a frontier session.
   - A sixth single-key design would fail the same way.
2. **hsrc-v1's committed re-probe is not run.** This is a decision, not a result. The family class, not the rules, was judged the cause. **Prediction on record:** it would fail K5/K6 as popt did.
3. **hrw's v0.3 probe runs, as committed,** on fresh instances probe/3 and probe/4. hrw plants several independent rules per instance, graded per target by `attribute.py`, so it is the one built family that is not single-key.
   - Hub: `../labloop-hrw-probe3-20261018`.
   - Predictions fixed in its PREREG: K6 frozen > blind, blind best-of-11 in [.35, .80], frozen in [.40, .85].
   - It names the K3-by-accumulation risk, and the threat that the family ranks only enumeration depth. That is measured as nested found-form sets across arms.
   - K2's median session line is read on search g, since the final split is read once per arm.
   - Attribution runs on the public dev split.
4. **If hrw is not admitted, labbench v0.3 is closed in writing.** Any graded-family programme that follows meets four conditions:
   - it gets a new name;
   - its rules are written and committed before any graded instance is scored, with the prediction that the old class fails them;
   - it uses a novel problem variant: a public generator is fine, but a public problem with public top solutions is not;
   - C comes from a reference solver frozen per instance.
5. **No forget pair on hsrc-v1.** The paper the user brought (Tan et al., arXiv 2610.20563, "Scaling Discovery Requires Forgetting") attributes the plateau to *session* accumulation. labloop already discards the session on every job. What it carries is search state (parent summary, lineage, population), which the paper never isolates. On a one-key task a policy pair reads only a discovery count, which cannot reach power at k ≤ 3. If a pair runs next, it is the **effort pair, removal only**: the card without "Make ONE hypothesised change" and "Prefer simple and runnable over ambitious" (`[worker.operator_text]`, f77ea4a), on a graded family.
6. **Haiku 5.5 as a deliberately weak inner worker** (the user's question): a separate programme, **labbench-haiku**, opened only through a preregistered gate (`../labloop-haiku-gate-20261018/PREREG.md`). The gate is 5 blind Haiku sessions on hrw's burned probe/0 and needs three things:
   - the contract met (≤ 1 of 5 invalid);
   - a median session search g in [.05, .17];
   - at least one planted rule found that generic pair search does not reach.

   The per-session spread, turns and window cost are recorded. Haiku never enters a Sonnet admission arm. Its effects get one preregistered Sonnet transfer read at the end.
7. **Tooling (labloop f77ea4a):** the blind card is the one-shot card (item 3), `[worker.operator_text]`, and a trust check at launch (change 8). Acceptance 613/0.

**labbench v0.3 closed 2026-10-18, with no family admitted** (decision 4 above). hrw's v0.3 probe (`../labloop-hrw-probe3-20261018/READ.md`) fired K3 (a blind draft reached final g .818), K5, and K6 in the opposite direction from the prediction (blind > frozen on both instances). In 20 improve and crossover jobs, the frozen arms added no planted form, while one blind draft found most of the planted rules. labbench produced no admitted suite, so §6 (noise floor on the suite) and the automated outer loop do not run on it. Harness work goes ahead as hand-run pairs (§9) on hrw, read as single-family results: first the effort pair, which this probe's data supports.

**Changelog of rule revisions: 3**, all 2026-10-17: the gauge for compression K2 (§2b, a70928d); v0.2
(8e4d912); v0.3 proposed (82be6bc), adopted 2026-10-18 with change 8 (9222081).

## 5. Meta-fitness, fixed before any run

### Per task

For each inner campaign on task t:

`g_t = (s_final − b_t) / (C_t − b_t)`

- s_final is the inner campaign's frozen candidate on its own final split, read once
  by the inner `lab run`.
- b_t is the baseline's score on that instance.
- C_t is the ceiling.
- The formula is oriented so that higher is better. For compression, the scores are
  negated first.

### Per meta-candidate

`M = mean_t(g_t) / (R / R₀)`

- R is the resource spend over the same inner campaigns, list-price usage dollars
  plus CPU-hours at a fixed exchange rate fixed in the preregistration.
- R₀ is the frozen commit's mean spend from §6. So the frozen commit scores M ≈ its
  own mean g.

### Hard constraints, never weighted terms

A meta-candidate that breaks any of these has **no fitness**. It stays in the outer
population with its reason, like any invalid candidate.

1. **Invalid rate.** Inner invalid + killed rate must not exceed the frozen commit's
   rate + 10 points.
2. **Leakage.** No inner candidate may trip a leakage check: the guard's label regex,
   an audit flag, a cheater-level score explained by metadata.
3. **Quality floor.** `mean_t(g_t)` must not fall below the frozen commit's mean by more
   than the smallest detectable effect from §6. This is the guard against a policy
   that wins the ratio by spending nothing: turn budgets of one, no sessions. Dividing
   by resources is only safe with a floor under the numerator.
4. **Task-specific strings.** The policy may contain no family names or task-specific
   keys. A lint checks it, with the same principle as `b764b76` ("index-v1 instruction
   names no task-specific key or file").

### Two levels of held-out

- **Inner.** Every inner campaign has its own search and final split. Its final is read
  once, by its own `lab run`, as today.
- **Outer.**
  - The meta-search reads `M` on *meta-search instances* of the admitted families.
  - The **meta-final** reads the best meta-candidate, and the frozen commit beside it,
    once. It runs on fresh instance seeds of the admitted families *and* on the
    held-out family.
  - The meta-final seeds are derived from the master secret under a purpose string the
    meta-search never uses. They are not generated until the read.
  - The two parts of the read are reported side by side, never pooled.
- **The claim.** It reads against a `success_threshold` on `M_final − M_frozen`. The
  threshold is fixed in the outer `campaign.toml` before the outer run, no lower than
  the §6 detectable effect.

## 6. First real experiment: the noise floor

**Before it:** calibrate the usage window by the written procedure
(`docs/campaign-setup.md:224-228`): one short campaign with `/usage` read beside
`lab campaign usage`. Every count below is in windows, and the only number for a
window today is a guess (§2a).

**Design.** The frozen labloop commit, after the §1 refactor and with the default
policy module, which is byte-identical in behaviour per its gate. It runs on the
admitted tasks with no treatment. Two variance components matter, and the design
separates them:

- σ_inst is between instance seeds of a task: different hidden worlds.
- σ_run is between runs on the *same* instance: the selection seed and the model's
  sampling.

A meta-comparison will pair arms on the same instance seeds, so σ_run sets its noise
floor. The repo has never measured σ_run: no arm has been repeated at the same seed
(the confound in `docs/mem3-comparison-20260915/RESULT.md:71-75`, where seed and
ledger version moved together).

**Smallest version that can kill the idea first:**

- 2 admitted tasks × 2 instances × 2 runs = 8 inner campaigns.
- About **$42–73 list-price**, three to four windows at $20 (*computed* from §2a;
  window *estimate*).
- About 10–12 h of wall clock on two slots (*estimate*).

**Reading.** The read reports σ_run, σ_inst and the smallest detectable paired
effect. For k paired runs per arm (normal approximation, two-sided α = .05, power .8,
understated at small k), MDE ≈ 2.8 · σ_d / √k:

| σ_d (in g) | k = 3 | k = 5 | k = 10 |
|---|---|---|---|
| .03 | .048 | .038 | .027 |
| .06 | .097 | .075 | .053 |
| .12 | .194 | .150 | .106 |

These values are *computed*, and the σ_d values are illustrative. The engram finals
across seeds and tooling versions had a sd of .061 (findings arms) and .113 (legacy
arms) (*computed* from the mechanical files cited in §0). Averaging over T independent
tasks divides σ_d by about √T.

**Kill criterion for automated meta-search (proposal).** The question is whether the
suite, at an affordable k (k ≤ 3 per arm and task), can detect a **0.05 gain in mean
g**. If it cannot, the outer loop is not built. Single-idea pairs (§9) at a larger k
are the whole programme instead.

**Cost of the thing this protects.** Suppose a meta-search has 10 meta-candidates,
each run on 3 tasks at k = 3. That is 90 inner campaigns, **$477–819 list-price, or
about 24–41 windows** (*computed*; window *estimate*). Spent on noise, that is the
whole usage budget for weeks.

## 7. Missing tooling

1. **The §1 refactor and its replay gate.** This includes the sudoers line narrowed to
   the evaluator's exact path (`docs/labeval.md:36-37`).
2. **`lab bench`.** It materialises an inner campaign dir from a task template and an
   instance seed. The generator runs as `labeval` and writes the private labels and the
   ceiling `C_t`. It also runs the admission probe's scripted arms: the cheater, and the
   crippled policy as a policy module.
3. **`lab meta eval`.** This is the meta-evaluator. For one meta-candidate it runs the
   inner campaigns:
   - **from a pinned, frozen labloop commit**, in a read-only worktree, with
     `git_dirty` refused;
   - with the candidate's `policy/` loaded out of process, as `labpolicy` with no sudo;
   - each inner `lab run` under `lab watch --op` with a wall and usage budget of its
     own;
   - inner labels and instance seeds readable only by `labeval`. The meta-worker, the
     agent writing policy variants, never sees generator code, instance seeds or inner
     candidates' code. It sees inner REPORT metrics, its parent policy and the frozen
     core.

   It writes `fitness.json` for the meta-candidate. It is the only reader of the
   meta-final seeds.
4. **One usage ledger for both levels.** Inner sessions and meta-worker sessions draw
   on the same Max window. The governor's state must be shared, or the two loops will
   each think they have the whole window.
5. **No cross-campaign memory inside a meta-evaluation.** Each inner campaign starts
   empty. Memory carried between instances would score a meta-candidate on what it
   saw before. The rule mirrors "a child never inherits trained weights".
6. **A blind draft mode** for the crippled arms of admission rules v0.2 (§4). The job
   card carries no population table, no "best so far" and no lineage, and the read scope is
   the worker's own dir only.
7. **An anytime curve in every REPORT.** Best-so-far fitness against candidate index
   and against cumulative usage. Today it exists only as checkpoints at 4/8/20 in the
   mechanical files.

## 8. Weak local inner workers

Pi on a local model costs **$0.00** of the window
(`../labloop-pi-engram-20260915/REPORT.md:54`). It costs GPU time and wall clock
instead:

- 8.32 GPU-hours for 19 settled candidates, 2.28 per GPU-hour
  (`../labloop-pi-engram-20260915/REPORT.md:13-15`).
- A median session of about 1479 s, against 700–880 s for Sonnet (*computed* from
  `candidates/*/session.json`).
- So a 12-candidate inner campaign would hold one GPU for about 4.5–5 h (*estimate*).

The meta-search in §6 would then be 400+ GPU-hours instead of 24–41 windows
(*estimate*).

The option is worth having for three jobs: plumbing (`lab meta eval` end to end), the
noise-floor *method*, and the cheater and crippled arms. **It has two caveats, and both
are serious:**

1. **Floor effects hide harness effects.** On enwik8 the Qwen3.8 probe never got past
   the baseline (`../labloop-compress-probe-20260917/REPORT.md:7-12`). On engram w0 the
   Pi lineage scored 1.0 by keying on metadata (`docs/pi-engram-20260916/READ.md:39-49`).
   A task that passes K4 for Sonnet may fail it for Qwen. A suite has to be admitted
   per worker model.
2. **A policy tuned for a weak worker need not transfer.** A frontier worker that
   reads the whole parent tree in one turn wants different memory than a model that
   thinks 25k tokens per session at `xhigh` (`NEXT.md`, Pi workers row). A meta-result
   on local workers is a claim about local workers. Transfer to Sonnet is its own
   read, on its own preregistration.

## 9. Hand-run A/B pairs come first

Each idea gets one pair: the frozen policy against the policy with that one change. It
runs on the admitted suite, at the k that §6 says detects a 0.05 effect, paired on
instance seeds, under its own PREREG. Automated evolution is only worth building if at
least one pair moves `M` by more than the noise floor.

- **LLM scheduler.** The replay is done (`docs/orchestrator-replay-20260916/READ.md`).
  Jev's argmax was the best-so-far at .93, .78 and 1.00 of ticks (`:38-52`), and the
  read was "Jev in this form is a ranker" (`:121`). The headroom variant would move
  about 4–9 points of selection mass off exhausted lines (`:165-171`). By the replay's
  own estimate that is "not distinguishable at one seed" (`:176-182`). This pair is the
  natural first user of the §6 numbers: the question is the k at which a 4-point shift
  in allocation becomes visible. The replay harness exists, and in the §1 interface the
  scheduler is one `select` module.
- **Web search for workers.**
  - Its leakage risk depends on the task. On a public-data task it is fatal: enwik8 is
    on the web. On labbench it is mostly safe, *if* generator code never leaves
    `labeval` and nothing published (this repo, nullsilver.com) describes a
    generator beyond its task statement.
  - The query log goes into the evidence: every query and every fetched URL in the
    candidate dir, with a leakage check that greps for the instance's opaque ids.
  - Web search is also a new egress channel. The container stays offline for the
    *evaluator*. The worker's search has to go through a logged proxy.
- **Agent forum moderated by a bigger model.** The forum already exists in an
  immutable form: finding cards, plus the index as retrieval
  (`docs/experiment-index-plan.md` §2). The idx1 pair, findings-v3 against index-v1,
  is scaffolded and not launched (`NEXT.md`, 2026-09-17 entry). That pair comes
  first, because a forum without a working index is a longer job card. The moderator
  adds two things the evidence rules must cover:
  - its calls spend the same window;
  - its curation is a selection policy that sees every worker's claims.

  It must not see scores the workers cannot see, or it becomes a scheduler with
  extra steps. That is a confound with the LLM-scheduler pair.

## 10. What this plan does not claim

- That labbench's families have headroom. §3 gives the reasons to expect it. §4 is
  where they are measured.
- That the harness matters on any of them. The evidence so far, on one task, says draw
  luck dominates (§0). K6 and the §6 reading are where that is tested.
- That `M` is a good fitness. It is fixed so that it can be wrong in a recorded way.
- Any window figure. $20 per window is a placeholder until §6's calibration.

**For the human to decide before anything runs:**

- the admission thresholds (§2, §4);
- the meta-fitness exchange rate between dollars and CPU-hours, and its quality floor
  (§5);
- whether the sudoers fix and the §1 refactor land before any labbench probe. They
  should, because a probe on the old core would have to be re-run anyway.
