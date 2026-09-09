# Starting a campaign (the phaseless loop)

What a new project needs before `lab run` works. Learned on the first live run
(M1, MNIST, 2026-09-09); see NEXT.md for the design.

1. **A project directory** with the template's `tools/`, `.claude/`, `templates/`,
   `CLAUDE.md`, `.lab-redact` copied in, and `git init` (candidate provenance records
   the commit). Ignore `.lab/`, `.venv/`, raw data and weights in `.gitignore`.
2. **`campaign.toml`** from `templates/campaign.toml`, plus the task statement, the
   evaluator (stdlib-only Python: `score.py <predictions> <labels_dir>` printing
   `{"score": x, "n": k}`), and the baseline command. `tools/lab campaign check`
   validates it.
3. **Data splits.** `data/train` (readable), `data/search` and `data/final` inputs in
   the repo; their labels **outside** the repo under `$LAB_PRIVATE/<campaign>/…`.
   The final split is read once, at the end. Export `LAB_PRIVATE` only in the shell
   that runs `lab run`; workers never receive it.
4. **A Python environment for candidates.** The worker's `code/run.sh` must name an
   interpreter that has what the task needs (torch, numpy …); the system `python3` is
   used only by `lab` itself and the evaluator. Say the path in the task statement.
5. **Trust the project directory once** for Claude Code, or headless sessions ignore
   the project's `permissions.allow` (they still run the hooks). Either open
   `claude` interactively there once and accept the trust dialog, or set
   `projects["<abs path>"].hasTrustDialogAccepted: true` in `~/.claude.json`.
6. **Subscription login only.** `claude auth status` must say `loggedIn: true`; no
   `ANTHROPIC_API_KEY` or endpoint override in the environment. `lab run` and
   `lab-worker` refuse to start otherwise.
7. Optional but recommended: the **`labeval` user** (`docs/labeval.md`) so hidden
   labels are hidden by the OS, not by convention. REPORT.md states which.

Then:

```sh
export LAB_PRIVATE=~/.local/share/labloop-private
tools/lab campaign check
tools/lab run campaign.toml --poll-sec 10        # or under: lab watch start --op campaign --budget-min N -- tools/lab run …
tools/lab campaign status                        # any time, from another shell
tools/lab campaign stop [--now]                  # stop dispatching (and kill running jobs)
```
