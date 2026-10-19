<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/labloop-plate-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/labloop-plate-light.svg">
    <img src="docs/assets/labloop-plate-light.svg" alt="The labloop plate" width="128">
  </picture>
</p>

# labloop

Coding agents can write and run experiments. That alone is not enough to conduct a research campaign: someone still has to decide which experiment to try next, keep the work inside its budgets, and make sure every result is evaluated the same way. Labloop is the tooling around the agent that takes on those tasks.

A campaign starts from a configuration written by a person: the task, a trivial baseline, an evaluator, the budgets and a success threshold. From there, `tools/lab run` turns a loop. It chooses a parent and an operator, gives one short headless agent session the job of making a new candidate, scores the result on a hidden search split, records it, and chooses again. The sessions run in Claude Code or in [Pi](https://pi.dev), which can drive a local open model or a hosted one; the model id in the configuration decides which. Labloop runs the search around the sessions and is the only writer of the campaign's records.

A good score during the search does not support a claim on its own. The search scores decide which candidates to pursue, so they are optimistic by construction. When the campaign stops, the selected candidate is evaluated once on a separate final split, and that one result is compared against the threshold fixed before the search began. Failed, invalid, killed and deferred candidates stay in the record with their configurations and reasons, so what is kept is what happened, not only the attempts that worked. The rules the lab runs by, and that an agent working in this repository follows, are in [CLAUDE.md](CLAUDE.md).

The loop follows AIRA₂ (Meta FAIR, arXiv 2603.26499): `draft`, `improve`, `crossover` and `debug` operators, temperature-scaled rank selection over search fitness, lineage summaries as the memory between candidates, and one hidden evaluation split used consistently. Labloop adds what running this on one machine with a subscription needs: watchers with budgets, records on the filesystem that survive a restart (and a power cut), labels that the operating system can hide, and a usage governor that treats the subscription's rolling window as a resource. It derives from [marcodsn/labloop](https://github.com/marcodsn/labloop) and keeps its values: preregistration, numeric thresholds, honest claims, evidence never deleted.

Labloop is experimental. It is exercised end to end by `scripts/acceptance.sh` without any model involved (643 checks), and it has run live on MNIST, CIFAR-10 and a family of generated rule-discovery tasks. The current state is in [NEXT.md](NEXT.md).

## How a campaign runs

```
campaign.toml ──► lab run ──► [ choose parent → worker → evaluate → add to population ] ──► REPORT.md
                    ▲                                                                       │
                    └──────────────── until a stop condition ───────────────────────────────┘
```

On every tick, `lab run` settles the jobs that ended (it reads their `fitness.json` and writes their LEDGER row), enforces the budgets (GPU-hours and the usage window), dispatches new jobs while a slot is free, and checks the stop conditions. The baseline goes first, then the opening drafts. After that each free slot gets an `improve` (probability 0.85) or a `crossover` (0.15) on rank-selected parents, and a `debug` when a candidate failed and its retry cap allows one. When a stop condition fires, the loop freezes the best candidate by search fitness, runs it once on the final split, writes `REPORT.md` with the claim against the fixed threshold, and exits. A loop that is killed is simply started again: it resumes from `population.json` and the candidate directories, and a job whose watcher died is settled as failed with that reason.

| status | meaning |
|---|---|
| `running` | searching |
| `waiting_usage` | the usage governor paused dispatch; `next_eligible` says until when |
| `stopping` | a stop condition fired; running jobs finish, then the final read |
| `finished` | `REPORT.md` is written; the claim is `supported`, `not_supported` or `inconclusive` |

![tools/lab campaign status after a campaign finished](docs/assets/labloop-status-finished.png)

That is `tools/lab campaign status` after one Haiku campaign on a rule-discovery task. The header carries the claim and the one final score; then the usage window and the GPUs; then the population, with each candidate's operator, parents, lease, the time its code spent fitting, turns, cost, the model that answered, and search fitness; then the loop's own log. In this one a draft was killed at its 45-minute wall, the debug job that followed rescued it, and a later draft became the best.

## Starting a campaign

1. Scaffold a project with `tools/lab campaign init <id>`. It writes `campaign.toml`, `task.md`, `eval/score.py`, `eval/baseline.sh` and the data directories.
2. Write the task statement, the evaluator and the baseline. The evaluator is a stdlib-only Python script that takes `<predictions> <labels_dir>` and prints `{"score", "n"}`. The labels of the search and final splits are kept outside the repository, under `$LAB_PRIVATE`.
3. Fix the success threshold in `campaign.toml` before running anything. It is reported against at the end and blocks nothing. A changed `campaign.toml` is a new campaign.
4. Trust the campaign directory in Claude Code once: open `claude` there and accept the dialog. Trust on a parent directory does not carry over, and `lab run` refuses to start in a directory Claude Code does not trust, because headless sessions there would ignore the project's allow-list.
5. Check the configuration and run the loop under a watcher:
   ```sh
   export LAB_PRIVATE=~/.local/share/labloop-private
   tools/lab campaign check
   tools/lab watch start --op campaign --budget-min 1500 -- tools/lab run campaign.toml
   tools/lab campaign status          # live view from another shell (--once for one frame, --plain for text)
   tools/lab campaign usage           # the usage governor's view
   tools/lab campaign stop [--now]    # stop dispatching (and kill running jobs)
   ```
6. Read `REPORT.md` when the campaign finishes. It states the baseline, the best candidate by search fitness, the one final score against the threshold, the GPU-hours, the usage and the deferrals.

The rest of what a new project needs is in [docs/campaign-setup.md](docs/campaign-setup.md): the Python environment the candidates use, the optional `labeval` user, calibrating the usage budget, Pi workers, and every policy key below.

## What a worker is told

Each job gets a card: the operator's instructions, the task statement, the contract (what it may read and write, how to run, when to stop), its parents' code and summaries, a five-deep lineage, and the population table. What the card says matters more than any selection rule. On a rule-discovery task with Haiku workers, removing two sentences from it ("Make ONE hypothesised change" from the improve card and "Prefer simple and runnable over ambitious" from the draft card) raised the final score in two independent runs, and the improve jobs that found a new hidden rule went from 4 in 160 to 21 in 160. Neither run cleared its own preregistered line; the sixteen pairs pooled cleared the secondary line declared before launch (rows E1 and E8 of [the v2 plan](docs/labloop-v2-plan.md)). Since 2026-10-19 the default cards no longer contain those sentences.

The cards are policy, so they can be changed per campaign without touching the code:

- `[worker.operator_text]` replaces one operator's instructions whole.
- `[selection] blind = true` makes every job a fresh draft that sees only the baseline: the card a lone one-shot session would get.
- `[selection] initial_drafts` and `draft_p` set how much of the campaign goes to fresh starts.
- `[selection] restart_after` dispatches a fresh draft once that many improves in a row have failed to raise the best by `restart_min_step`.
- `[campaign] seed_from` and `seed_upto` start a campaign from a copy of another campaign's opening, so two arms of an experiment begin from the same drafts. The copy is re-scored through the evaluator and must match before anything is written, and the source's final read never comes along.
- `[data] same_output_ignore` names the keys dropped when a child's output is compared with its parent's, which records improves that changed nothing.

What has and has not worked, with every number and every experiment that failed, is in [docs/labloop-v2-plan.md](docs/labloop-v2-plan.md). In short: the card change above holds up; spreading drafts through the run or front-loading them helped a little, too little to separate from noise at 32 campaigns; telling workers to check that they changed something removed the no-op jobs and did not help. Whether a crossover can combine what two parents found is being tested now.

## The two harnesses

The worker model named in `campaign.toml` decides which harness runs the session. An id such as `claude-haiku-5-5` runs the job through Claude Code on subscription login, in `tools/lab-worker`. An id of the form `provider/model`, such as `local/gpt-oss-20b`, runs it through Pi in `tools/lab-worker-pi`, against whatever that provider is in Pi's own `models.json`. Because the choice is per model id, the two can be mixed within one campaign through the per-operator model table.

For local models, `scripts/llm-server.sh` runs llama.cpp's CUDA server on one GGUF file, pinned to one GPU and bound to localhost. The server is a service, not a job: it is started once, outside any campaign, and `lab run` only checks, before a campaign begins, that the endpoint serves the requested model and that Pi's declared context window does not exceed the one served. Pi is configured the way Pi documents it, so a fork can point its workers at any OpenAI-compatible server or hosted API without changing labloop.

A Pi session works under the same contract as a Claude Code session. A small extension, `tools/pi/lab-worker.js`, loaded explicitly for each session and with nothing else discovered, enforces the turn budget, runs the same evidence guard, refuses reads of label paths, bounds every bash call within the remaining job budget, clips oversized tool results, and continues a run cut at the model's output limit. `session.json` has the same shape under both harnesses. Two probes on local models re-ran the first MNIST campaign and cleared its threshold; they show that the harness works end to end on a local model, not that the models compare ([the probe](docs/pi-probe-20260915.md)).

## What you own and what the lab owns

The person running the campaign owns `campaign.toml`, the task statement, the evaluator and the baseline. The lab never edits them, and it refuses to continue a campaign whose configuration has changed since it started.

The lab owns the population. The candidate directories, `population.json`, `LEDGER.md`, `events.jsonl`, `finding.json` and `REPORT.md` are written only by `tools/lab` and are never deleted, because a failed, killed, invalid or deferred candidate is evidence. A worker writes only inside its own candidate directory, never reads labels, and never starts a second session. A hook enforces this for every tool an agent has, and it is a deterrent rather than a wall: code a worker writes and runs is not inspected.

## Layout

```
campaign.toml        # the campaign: task, data, evaluator, budgets, threshold   (you write)
task.md              # the task statement workers receive verbatim              (you write)
eval/                # score.py and the trivial baseline                         (you write)
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
tools/lab_status.py  # the live status view
tools/lab-worker     # one headless Claude Code session per job (hands Pi ids to lab-worker-pi)
tools/lab-worker-pi  # the same job as one headless Pi session: local or hosted open models
tools/pi/            # the Pi extension: turn budget and the evidence guard, loaded per session
scripts/llm-server.sh  # a llama.cpp server for local GGUFs, started outside the campaign
.claude/             # settings and hooks (guard, session briefing)
docs/                # campaign-setup.md, labeval.md, the plans and the dated write-ups
scripts/             # acceptance.sh and its fixtures, sync-project.sh
```

A candidate directory is the unit of evidence. `config.json` records the operator, the parents, the seed, the git commit, the command, the hardware, the package versions and which model was asked for and which answered. `job.json` is what the worker was told. The candidate's own code is in `code/`, and `summary.md` is written when the candidate ends, including when it was killed, in which case it says so and why. `fitness.json` is written by `lab eval` and by nothing else. `session.json` is the result of the worker session: its turns, its list-price cost and the model that answered.

## `tools/lab`

The CLI has no dependencies beyond Python 3, and it is the only writer of the machine files: `population.json`, `LEDGER.md`, `events.jsonl`, `fitness.json`, `finding.json` and `FORMAT.json`. A `PreToolUse` hook blocks hand edits, whether by a shell command or by an agent's Write and Edit tools.

```
lab campaign init <id> | check | status | usage [--json] | stop [--now]
lab run [campaign.toml] [--once --poll-sec N]
lab candidate list
lab eval <candidate dir> [--split search]       the only reader of labels; final is never on request
lab job card <candidate dir>                     the job card a worker receives
lab watch start --op NAME --budget-min N [--stall-min N --kill-regex RE] -- <cmd>
lab watch list | check | kill <id> --reason … | close <id>
lab log <type> --msg "…" [--data '{…}'] [--candidate <id>]
lab events tail -n 20 [--class news|activity]
lab usage [--since YYYY-MM-DD] [--json]
lab validate
lab format show | sync | version
```

## Format versioning

Everything the lab writes is meant to be parsed by machines, so every artifact declares the format it was written in. `FORMAT.json` at the root publishes the whole contract: file locations, campaign and candidate statuses, operators, claims, the feed class of every event type, where provenance is recorded, and the limits. A consumer, such as [nullsilver.com](https://nullsilver.com), should build its filters from that file rather than from this README.

`population.json` carries a `format` field restamped on every write, and so does each candidate's `config.json`. Every event carries its own `format`, fixed when it was written; `events.jsonl` is append-only, so a long-running project's feed may hold lines written by several versions of `lab`, and the per-line stamp means a consumer never has to guess. `FORMAT.json` is generated from the constants in `tools/lab` and `tools/lab_campaign.py` and is never edited by hand; `lab validate` fails if it has drifted.

The major version changes when a consumer that ignored the change would misread the data: a key renamed or removed, a status renamed, an event moved to another feed class, a limit tightened. The minor version changes for additions a consumer can safely ignore.

| version | change |
|---|---|
| 1.0 | initial contract: the six-phase state machine, `state.json`, trials, gates |
| 1.1 | additive: model provenance, requested vs served |
| 1.2 | additive: `note` event type |
| 1.3 | additive: `trial.verdict` event type |
| 1.4 | additive: the campaign loop's events beside the phase vocabulary |
| 2.0 | the phase machine is gone. `state.json`, phases, gates, protocol revisions, trials, sessions, predictions and their event types are removed. Events carry `campaign` and `candidate` instead of `phase`/`run`/`revision`. `population.json` is the live state; `FORMAT.json` publishes campaign and candidate statuses, operators and claims |
| 2.1 | additive: opt-in finding cards. `candidates/cNNNN/finding.json`, `population.json` `memory`, `job.json` `findings`, `FORMAT.json` `memory` section |
| 2.2 | additive: `population.json` `seeded`; per candidate `seeded_from` and `same_output_as_parent` |

## The event feed

`events.jsonl` is written to be published as it is, whether in a public repository or by a site tailing it, so the lab enforces its contract mechanically. The set of event types is closed, `msg` is one line of at most 140 characters, an event is capped at 4 KB, `metric` events are throttled to one per candidate per minute, and redaction is always on: keys of the forms `sk-…`, `AKIA…`, `hf_…` and `ghp_…`, bearer tokens, and the literal values of every environment variable named in `.lab-redact`.

Each event type has a fixed feed class. `news` (`campaign.start`, `campaign.stop`) is eligible for a homepage and an RSS feed. `activity` (`candidate.launch`, `candidate.done`, `candidate.failed`, `campaign.paused`, `note`, `error`) belongs on a project timeline only. `metric` is chart data and never a feed item. Setting `NULLSILVER_INGEST_URL` (and `NULLSILVER_TOKEN`) enables a realtime push of events; it is best-effort and silent on failure, because git remains the source of truth.

## Configuration

The model, the turn budget, the GPUs, the wall clocks, the stop conditions, the usage budget and the policy keys above all live in `campaign.toml`. `lab campaign check` validates the file, including whether a seeded campaign's source would be accepted, and `templates/campaign.toml` documents every key.

Claude Code workers run with `--permission-mode auto`, so anything the classifier will not approve is denied rather than left waiting for a prompt, and an unattended loop never hangs. A worker may lose an action this way, and the contract check turns that into an invalid candidate rather than a silent success. Pi workers need no trust step, since the wrapper passes `--no-approve` and loads only the lab's extension.

## The plate

<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/labloop-construction-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/labloop-construction-light.svg">
    <img src="docs/assets/labloop-construction-light.svg" alt="The labloop plate with its construction" width="360">
  </picture>
</p>

Labloop's plate is drawn on an em of six cells, every edge on a half-cell lattice. The thin thread is the loop, the two heavy terminals are the gate, and the slot between them is the only way out: the loop turns many times on scores that are optimistic by construction, and a claim leaves only through one evaluation on data the search never saw. The terminals always outweigh the thread, and the slot never closes.

![labloop's print](docs/assets/labloop-print.webp)

In the print, the plate is the clear area. The plates and prints of the lab's projects are made by [nullsilver.com](https://nullsilver.com)'s design system, where the construction is described in full.

## License

MIT, see `LICENSE`.
