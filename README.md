# nullsilver lab

A repo template for **agent-driven research that runs itself in public**. One repo is
one research project. You write and critique `PROTOCOL.md`; from then on a fixed state
machine of phases runs the project, each phase a fresh Claude Code session. Two
machine-readable files — `state.json` and `events.jsonl` — are the contract with
nullsilver.com, which renders the project live.

It is the nullsilver variant of [labloop](https://github.com/nullsilver-labs/labloop),
with the same values — pre-registration, numeric gates, honest verdicts, evidence is
never deleted — but with the procedure moved out of prose and into hooks, a CLI, and
per-phase prompts. Target host: **Claude Code**.

## The loop

```
init → build → pilot → execute → analyze → decide ──→ init   (next run, next revision)
                                              └─────→ conclude
```

| phase | what it does | fails into |
|---|---|---|
| `init` | compiles `PROTOCOL.md` into `plan.json` + one spec per experiment | a gate if a hypothesis has no numeric gate |
| `build` | writes the experiment code and every baseline; one smoke trial | — |
| `pilot` | logs predictions, then cheap trials that check the *measurement* | back to `build` |
| `execute` | full-budget trials in the background, budget and kill-criteria enforced | kills, not overruns |
| `analyze` | reads trials against the **pre-registered** gates; verdicts, summaries, LEDGER | INCONCLUSIVE is a real verdict |
| `decide` | revise the protocol (rev N+1), conclude, or ask you | a gate |
| `conclude` | `REPORT.md` + `CLAIMS.md`, negative results with equal billing | terminal |

Each phase is a separate session, so context resets are structural rather than
accidental. `lab` validates every transition; an agent that gets stuck raises a gate
instead of improvising.

## Getting started

1. **Copy this repo** and rename it after your project.
2. **Write `PROTOCOL.md`** — the one thing only you can do. Start from
   `templates/protocol.md` (already copied to `PROTOCOL.md` with `REPLACE-ME`
   placeholders). Fill the frontmatter (id, budgets, `autonomy: gated|auto`) and every
   prose section. **Critique it yourself before the first run** — the lab never runs a
   "critique the protocol" phase, and a vague success criterion is how a project ends
   up measuring nothing. Every hypothesis needs a *number* in Success criteria.
3. **`tools/lab init`** — bootstraps `state.json`, `events.jsonl`, `LEDGER.md`,
   `NOTES.md`, `HANDOFF.md`, and freezes `protocol/rev001.md`. It refuses while the
   placeholders are still there.
4. **`./loop.sh`** — runs phases until a gate, the conclusion, or the iteration cap.

   Or, attended: start `LAB_ROLE=orchestrator claude`, run `/orchestrate`, and enable
   Remote Control (`/remote`) to answer gates from your phone. `LAB_ROLE` marks it an
   operator session — kept out of the public feed and exempt from the handoff rule
   that phase sessions owe.
5. **When it stops at a gate**: `tools/lab gate resolve --approve|--reject --note "…"`,
   then rerun `./loop.sh`.

Check it works before trusting it with compute: `scripts/acceptance.sh` scripts the
entire state machine with no LLM involved and asserts the whole contract.

## What you own, what the lab owns

**Yours**: `PROTOCOL.md` prose. The lab may only change it in the `decide` phase, via
freeze → edit → `lab protocol activate`, and under `autonomy: gated` only after you
approve a written proposal. Every revision is frozen to `protocol/revNNN.md` and
carries a Changelog entry naming the result that motivated it.

**The lab's**: everything else — code, specs, trials, summaries, LEDGER, NOTES, the
report. It may not delete evidence, may not change a gate after seeing results without
logging `gate.overridden` and reporting against both gates, and may not end a session
without an accurate `HANDOFF.md` (a Stop hook enforces this).

## Layout

```
PROTOCOL.md          # the project: frontmatter contract + prose        (YOU write)
protocol/revNNN.md   # frozen revisions — the history of the question
state.json           # machine state; the site polls it                 (lab writes)
events.jsonl         # append-only public event feed; the site tails it (lab writes)
FORMAT.json          # the output-format contract, for machine consumers (generated)
plan.json            # the current run's machine plan (init compiles it)
HANDOFF.md           # phase → phase handoff, overwritten every session
NOTES.md             # lab notebook: predictions, interpretations, surprises
LEDGER.md            # one row per trial, ever
runs/rNNN/           # specs/, trials/<trial_id>/, summary.md
REPORT.md CLAIMS.md  # written by conclude, not before
code/                # experiment code
tools/lab            # the CLI — the only writer of state.json/events.jsonl
loop.sh              # unattended driver
.claude/             # settings + hooks + one prompt per phase + loop.conf
scripts/acceptance.sh
```

A trial dir is the unit of evidence: `config.json` (config, seed, git commit, command,
start time, hardware, package versions), append-only `results.jsonl`, `console.log`,
and a `summary.md` written when it ends — including when it was killed, saying so and
why. Trial dirs are committed and never deleted.

## `tools/lab`

Zero dependencies beyond Python 3, and the only legal writer of the two machine files
(a `PreToolUse` hook blocks hand-edits).

```
lab init                       bootstrap from PROTOCOL.md
lab validate                   lint state, events, trials, plan, protocol, loop.conf
lab state get [key] | set phase=analyze
lab trial new <exp> [--seed N --config @f.json --spec … --command …]
lab trial log <dir> --data '{"step":1,"loss":0.4}'
lab trial done <dir> [--verdict GO|NO-GO|INCONCLUSIVE] [--killed --reason …]
lab log <type> --msg "…" [--data '{…}'] [--trial <id>]
lab protocol freeze | activate --diff-summary "…"
lab gate request --type … --question "…" | gate resolve --approve|--reject
lab events tail -n 20 [--class news|activity]
lab format show | sync | version
```

## Format versioning

Everything here is parsed by machines, so every artifact declares the format it was
written in. `FORMAT.json` at the repo root publishes the whole contract — file
locations, the phase list and legal transitions, the status→badge map, **the feed
class of every event type**, the trial-dir requirements, and the limits. A consumer
should build its filters from that file rather than hardcoding this README, and can
then adapt per-repo instead of assuming every project is on the same version.

- `state.json` carries `format`, restamped on every write.
- **Every event carries its own `format`**, fixed at write time. This is the one that
  matters: `events.jsonl` is append-only, so a long-running project's feed contains
  lines written by several versions of `lab`. A per-line stamp means a consumer never
  has to guess which rules applied to a given line. A missing `format` means pre-1.0.
- Each trial's `config.json` carries it too, so a trial stays interpretable.

`FORMAT.json` is generated from the constants in `tools/lab` — never hand-edit it.
`lab validate` fails if it has drifted from the code or declares a version the lab
doesn't write, so the published contract cannot quietly become a lie.

**Bump policy.** MAJOR when a consumer that ignored the change would misread the
data: a key renamed or removed, a phase or status renamed, an event type's feed class
changed, a limit tightened. MINOR for additive changes it can safely ignore: a new
event type, a new optional key.

| version | change |
|---|---|
| 1.0 | initial contract |

## The public feed

`events.jsonl` is public in realtime, so `lab log` enforces the contract mechanically:
closed set of event types, `msg` collapsed to one line and truncated at 140 chars,
events capped at 4 KB, `metric` events throttled to one per trial per minute (full
resolution stays in `results.jsonl`), and **redaction always** — `sk-…`, `AKIA…`,
`hf_…`, `ghp_…`, bearer tokens, plus the literal values of every env var named in
`.lab-redact`.

Each type has a fixed feed class: `news` (`project.created`, `protocol.revised`,
`run.done`, `project.concluded`) reaches the homepage and RSS; `activity` (phases,
sessions, predictions, trials, surprises, kills, gates) reaches only the project
timeline; `metric` is chart data and never a feed item. Heartbeats are not events.
The authoritative table is `FORMAT.json` → `events.types`; read it from there.

Set `NULLSILVER_INGEST_URL` (+ `NULLSILVER_TOKEN`) for realtime push; it is
best-effort and silent on failure, because git is the source of truth and the site
backfills on push. `push=true` in `.claude/loop.conf` makes `loop.sh` push after every
phase that moved the state.

## Configuration

`.claude/loop.conf` is the single place model and driver choices live: one model per
phase, `orchestrator=` for attended mode, `permission_mode`, and the loop's safety
knobs (`max_iterations`, `max_no_progress`, backoff). `lab validate` checks it.

Run `claude` interactively in the project once and accept the trust dialog before the
first `loop.sh`. Until you do, Claude Code ignores the `permissions.allow` entries in
`.claude/settings.json` for that workspace (hooks still run), so headless phases lean
entirely on the classifier and lose more actions to auto-deny than they need to.

`permission_mode=auto` means anything the classifier won't approve is auto-denied
rather than prompting, so an unattended loop can never hang — a phase can lose an
action instead, which is why every phase prompt says: *if a command is denied, do not
work around it — raise a gate and stop*. `bypassPermissions` is opt-in and only
sensible inside an isolated container or VM without credentials, never as root; the
`permissions.deny` rules in `.claude/settings.json` and the evidence guard hook stay on
either way.

## License

MIT — see `LICENSE`.
