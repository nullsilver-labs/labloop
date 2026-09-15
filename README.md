<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/labloop@256-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/labloop@256-light.png">
    <img src="docs/assets/labloop@256-light.png" alt="labloop" width="256">
  </picture>
</p>

# labloop

Coding agents can write and run experiments, but that alone does not make a research
campaign. Someone still has to decide which experiment to try next, keep the work inside
its budgets, and make sure every result is evaluated the same way. Labloop is the tooling
around the agent that takes on those tasks.

A campaign starts from a configuration written by a human: the task, a trivial baseline,
an evaluator, the available budgets, and a success threshold. From there, `tools/lab run`
runs a loop. It selects a parent candidate and an operator, gives one short headless
agent session the job of producing a new candidate, evaluates the result on a hidden
search split, records it, and selects again. The agent sessions run in Claude Code or in
[Pi](https://pi.dev), which can drive a local open model or a hosted one; the model id in
the configuration decides which. Labloop manages the search around the sessions and is
the only writer of the campaign's records.

Search scores are used to decide which candidates to pursue, so they are optimistic by
construction and do not support a claim on their own. When the campaign stops, the
selected candidate is evaluated once on a separate final split, and that single result
is compared against the threshold fixed before the search began. Failed, invalid, killed
and deferred candidates stay in the record with their configurations and their reasons,
so that what is preserved is what actually happened rather than only the attempts that
worked. The rules that the lab is run by, and that an agent working in the repository is
expected to follow, are written in [CLAUDE.md](CLAUDE.md).

The loop follows AIRA₂ (Meta FAIR, arXiv 2603.26499): `draft`, `improve`, `crossover`
and `debug` operators, temperature-scaled rank selection over search fitness, lineage
summaries as the memory between candidates, and one hidden evaluation split used
consistently. Labloop adds what running this on a local machine with one or two GPUs and
a subscription requires: watchers with budgets, bookkeeping on the filesystem that
survives a restart, labels that can be hidden by the operating system, and a usage
governor that treats the subscription's rolling window as a resource. It derives from
[marcodsn/labloop](https://github.com/marcodsn/labloop) and keeps its values:
pre-registration, numeric thresholds, honest claims, evidence never deleted.

Two machine-readable files, `population.json` and `events.jsonl`, describe a campaign in
a published format, so that a site such as [nullsilver.com](https://nullsilver.com) can
render a project that opts in.

Labloop is still experimental. The loop is exercised end to end by
`scripts/acceptance.sh` without any model involved, and it has run live on MNIST and
CIFAR-10. The current state is in NEXT.md and the design in
[docs/aira2-loop-design.md](docs/aira2-loop-design.md).

## How a campaign runs

```
campaign.toml ──► lab run ──► [ select parent → worker → evaluate → add to population ] ──► REPORT.md
                    ▲                                                                       │
                    └──────────────── until a stop condition ───────────────────────────────┘
```

On every tick, `lab run` reaps the jobs that finished (it reads their `fitness.json` and
writes their LEDGER row), enforces the budgets (GPU-hours and the usage window),
dispatches new jobs while a slot is free, and checks the stop conditions. The baseline is
dispatched first, then the initial drafts. After that, each free slot gets an `improve`
with probability 0.85 or a `crossover` with probability 0.15 on rank-selected parents,
and a `debug` when a candidate failed and its retry cap allows one. Once a stop
condition fires, the loop freezes the best candidate by search fitness, runs it once on
the final split, writes `REPORT.md` with the claim against the pre-fixed threshold, and
exits. If the process is killed it can simply be started again; it resumes from
`population.json` and the candidate directories.

| status | meaning |
|---|---|
| `running` | searching |
| `waiting_usage` | the usage governor paused dispatch; `next_eligible` says until when |
| `stopping` | a stop condition fired; running jobs finish, then the final read |
| `finished` | `REPORT.md` is written; the claim is `supported`, `not_supported` or `inconclusive` |

![tools/lab campaign status after a campaign finished](docs/assets/labloop-status-finished.png)

The screenshot shows `tools/lab campaign status` after a campaign has finished. The
header carries the claim and the one final score, then the usage window and the GPUs,
then the population with the operator, parent, lease, turns, cost and search fitness of
each candidate, and finally the loop's own log.

## Starting a campaign

1. Scaffold a project with `tools/lab campaign init <id>`. It writes `campaign.toml`,
   `task.md`, `eval/score.py`, `eval/baseline.sh` and the data directories.
2. Write the task statement, the evaluator and the baseline. The evaluator is a
   stdlib-only Python script that takes `<predictions> <labels_dir>` and prints
   `{"score", "n"}`. The labels of the search and final splits are kept outside the
   repository, under `$LAB_PRIVATE`.
3. Fix the success threshold in `campaign.toml` before running anything. It is reported
   against at the end and blocks nothing. A changed `campaign.toml` is a new campaign.
4. Check the configuration and run the loop under a watcher:
   ```sh
   export LAB_PRIVATE=~/.local/share/labloop-private
   tools/lab campaign check
   tools/lab watch start --op campaign --budget-min 1500 -- tools/lab run campaign.toml
   tools/lab campaign status          # live view from another shell (--once for one frame, --plain for text)
   tools/lab campaign usage           # the usage governor's view
   tools/lab serve                    # the same, as a page on http://<this host>:8791/
   tools/lab campaign stop [--now]    # stop dispatching (and kill running jobs)
   ```
5. Read `REPORT.md` when the campaign finishes. It states the baseline, the best
   candidate by search fitness, the one final score against the threshold, the
   GPU-hours, the usage and the deferrals.

The rest of what a new project needs is in
[docs/campaign-setup.md](docs/campaign-setup.md): the Python environment the candidates
use, trusting the project directory once so that headless Claude Code sessions honour
the allow-list, the optional `labeval` user, calibrating the usage budget, and setting up
Pi workers. Before trusting the tooling with compute, `scripts/acceptance.sh` runs the
whole loop with scripted workers and a fake agent CLI.

## The two harnesses

The worker model named in `campaign.toml` decides which harness runs the session. An id
such as `claude-sonnet-5` runs the job through Claude Code on subscription login, in
`tools/lab-worker`. An id of the form `provider/model`, such as `local/gpt-oss-20b`, runs
it through Pi in `tools/lab-worker-pi`, against whatever that provider is in Pi's own
`models.json`. Because the choice is per model id, the two can be mixed within one
campaign through the per-operator model table: a Claude Code draft where the approach is
chosen, and local improves for the many jobs that follow.

For local models, `scripts/llm-server.sh` runs llama.cpp's CUDA server on one GGUF file,
pinned to one GPU and bound to localhost. The server is a service rather than a job. It
is started once, outside any campaign, and shared by every client on the machine; `lab
run` never starts or stops it, and only checks before a campaign begins that the endpoint
serves the requested model id and that Pi's declared context window does not exceed the
one served. Pi is configured the way Pi documents it, so a fork of this repository can
point its workers at any OpenAI-compatible server or hosted API without changing
labloop.

A Pi session works under the same contract as a Claude Code session. A small extension,
`tools/pi/lab-worker.js`, loaded explicitly for each session and with nothing else
discovered, enforces the turn budget, runs the same evidence guard, refuses reads of
label paths, bounds every bash call within the remaining job budget, clips oversized tool
results, and continues a run that was cut at the model's output limit. Pi's event stream
and session file are kept beside the candidate, and `session.json` has the same shape
under both harnesses.

Two probes on 2026-09-15 re-ran the first MNIST campaign (M1, Claude Code on Sonnet)
with five candidates each on local models, against the same threshold of 0.985 fixed for
M1. gpt-oss-20b scored 0.9888 on the final split and Qwen3.8-27B Q4_K_M scored 0.9937;
M1 itself had scored 0.9875. All three claims are supported at that threshold. These
runs show that the harness works end to end on a local model. They do not compare the
models, since five candidates on MNIST sit at the noise floor. The details, including
what went wrong in each run, are in [docs/pi-probe-20260915.md](docs/pi-probe-20260915.md).

## What you own and what the lab owns

The human owns `campaign.toml`, the task statement, the evaluator and the baseline. The
lab never edits them, and it refuses to continue a campaign whose configuration file
has changed since the campaign started.

The lab owns the population. The candidate directories, `population.json`, `LEDGER.md`,
`events.jsonl`, `finding.json` and `REPORT.md` are written only by `tools/lab` and are
never deleted, because a failed, killed, invalid or deferred candidate is evidence. A
worker writes only inside its own candidate directory, never reads labels, and never
starts a second session.

## Layout

```
campaign.toml        # the campaign: task, data, evaluator, budgets, threshold   (YOU write)
task.md              # the task statement workers receive verbatim              (YOU write)
eval/                # score.py and the trivial baseline                         (YOU write)
data/                # train (readable) and the inputs of the hidden splits
$LAB_PRIVATE/<id>/   # the hidden splits' labels, outside the repo
population.json      # the live state of the campaign                            (lab writes)
candidates/cNNNN/    # config.json, job.json, code/, summary.md, fitness.json, finding.json, session.json
LEDGER.md            # one row per candidate, ever                               (lab writes)
events.jsonl         # append-only public feed                                   (lab writes)
REPORT.md            # written once, at the end                                  (lab writes)
FORMAT.json          # the output-format contract, for machine consumers         (generated)
tools/lab            # the CLI, the only writer of the machine files
tools/lab_campaign.py  # the loop
tools/lab-worker     # one headless Claude Code session per job (hands Pi ids to lab-worker-pi)
tools/lab-worker-pi  # the same job as one headless Pi session: local or hosted open models
tools/pi/            # the Pi extension: turn budget and the evidence guard, loaded per session
scripts/llm-server.sh  # a llama.cpp server for local GGUFs, started outside the campaign
.claude/             # settings and hooks (guard, session briefing)
docs/                # campaign-setup.md, labeval.md, the dated result write-ups
scripts/             # acceptance.sh and its fixtures, sync-project.sh
```

A candidate directory is the unit of evidence. `config.json` records the operator, the
parents, the seed, the git commit, the command, the hardware, the package versions and
the model provenance. `job.json` is what the worker was told. The candidate's own code is
in `code/`, and `summary.md` is written when the candidate ends, including when it was
killed, in which case it says so and why. `fitness.json` is written by `lab eval` and by
nothing else. `session.json` is the result of the worker session: its turns, its
list-price cost and the model that answered. When the campaign opts into finding cards,
`finding.json` is written once by `lab run` after the candidate settles, which keeps the
worker's account of its work separate from the measured search score.

### Which model ran it

Two facts are kept apart. The requested model is the one named in `campaign.toml`. The
served model is the one that actually answered, read from the session result the worker
stores. Both are recorded in the candidate's `config.json` under `agent`, together with
their sources. `lab usage` reads every session's transcript for token counts, and
`lab campaign usage` reads the list-price cost per candidate.

## `tools/lab`

The CLI has no dependencies beyond Python 3, and it is the only legal writer of the
machine files: `population.json`, `LEDGER.md`, `events.jsonl`, `fitness.json`,
`finding.json` and `FORMAT.json`. A `PreToolUse` hook blocks hand edits, whether by a
shell command or by an agent's Write and Edit tools.

```
lab campaign init <id> | check | status | usage [--json] | stop [--now]
lab run [campaign.toml] [--once --poll-sec N]
lab candidate list
lab eval <candidate dir> [--split search]       the only reader of labels; final is never on request
lab job card <candidate dir>                     the job card a worker receives
                                                 (under finding cards, the stored findings snapshot)
lab watch start --op NAME --budget-min N [--stall-min N --kill-regex RE] -- <cmd>
lab watch list | check | kill <id> --reason … | close <id>
lab serve [--bind 0.0.0.0] [--port 8791]        read-only page for the LAN: population, timeline, report
lab log <type> --msg "…" [--data '{…}'] [--candidate <id>]
lab events tail -n 20 [--class news|activity]
lab usage [--since YYYY-MM-DD] [--json]
lab validate
lab format show | sync | version
```

## Format versioning

Everything the lab writes is meant to be parsed by machines, so every artifact declares
the format it was written in. `FORMAT.json` at the root of the repository publishes the
whole contract: file locations, campaign and candidate statuses, operators, claims, the
feed class of every event type, where provenance is recorded, and the limits. A consumer
should build its filters from that file rather than from this README.

`population.json` carries a `format` field that is restamped on every write, and so does
each candidate's `config.json`. Every event carries its own `format`, fixed when it was
written. Since `events.jsonl` is append-only, the feed of a long-running project may
contain lines written by several versions of `lab`, and the per-line stamp means a
consumer never has to guess which rules applied to a given line.

`FORMAT.json` is generated from the constants in `tools/lab` and `tools/lab_campaign.py`
and is never edited by hand. `lab validate` fails if it has drifted from the code or
declares a version the lab does not write.

The major version is bumped when a consumer that ignored the change would misread the
data: a key renamed or removed, a status renamed, an event type moved to another feed
class, a limit tightened. The minor version is bumped for additive changes a consumer can
safely ignore, such as a new event type or a new optional key.

| version | change |
|---|---|
| 1.0 | initial contract: the six-phase state machine, `state.json`, trials, gates |
| 1.1 | additive: model provenance, requested vs served |
| 1.2 | additive: `note` event type |
| 1.3 | additive: `trial.verdict` event type |
| 1.4 | additive: the campaign loop's events beside the phase vocabulary |
| 2.0 | the phase machine is gone. `state.json`, phases, gates, protocol revisions, trials, sessions, predictions and their event types are removed. Events carry `campaign` and `candidate` instead of `phase`/`run`/`revision`. `population.json` is the live state; `FORMAT.json` publishes campaign/candidate statuses, operators and claims |
| 2.1 | additive: opt-in finding cards. `candidates/cNNNN/finding.json`, `population.json` `memory`, `job.json` `findings`, `FORMAT.json` `memory` section |

## The event feed

`events.jsonl` is written to be published as it is, whether in a public repository or by
a site tailing it, so the lab enforces its contract mechanically. The set of event types
is closed, `msg` is collapsed to one line and truncated at 140 characters, an event is
capped at 4 KB, `metric` events are throttled to one per candidate per minute, and
redaction is always on. Redaction covers keys of the forms `sk-…`, `AKIA…`, `hf_…` and
`ghp_…`, bearer tokens, and the literal values of every environment variable named in
`.lab-redact`.

Each event type has a fixed feed class. `news` (`campaign.start` and `campaign.stop`) is
eligible for a homepage and an RSS feed. `activity` (`candidate.launch`,
`candidate.done`, `candidate.failed`, `campaign.paused`, `note` and `error`) belongs on a
project timeline only. `metric` is chart data and never a feed item. The authoritative
table is the `events.types` section of `FORMAT.json`.

Setting `NULLSILVER_INGEST_URL` (and `NULLSILVER_TOKEN`) enables a realtime push of
events. The push is best-effort and silent on failure, because git remains the source of
truth and the site backfills from it on push.

## Configuration

The model, the turn budget, the GPUs, the wall clocks, the stop conditions and the usage
budget all live in `campaign.toml`. `lab campaign check` validates the file, and
`templates/campaign.toml` documents every key.

Claude Code needs the project directory trusted once before the first run: open `claude`
there and accept the dialog, or set `hasTrustDialogAccepted` for the path in
`~/.claude.json`. Until then, headless sessions ignore the `permissions.allow` entries
in `.claude/settings.json` for that workspace, the hooks still run, and the sessions
lose more actions to auto-deny than they need to. Pi workers need no trust, since the
wrapper passes `--no-approve` and loads only the lab's extension.

Claude Code workers run with `--permission-mode auto`, so anything the classifier will
not approve is auto-denied rather than left waiting for a prompt, and an unattended loop
can never hang. A worker may lose an action this way, and the contract check turns that
into an invalid candidate rather than a silent success. The `permissions.deny` rules in
`.claude/settings.json` and the evidence guard hook stay on in either case.

## License

MIT, see `LICENSE`.
