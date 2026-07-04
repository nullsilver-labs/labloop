# experiments/

- `LEDGER.md` — the registry. Every experiment gets a row before any code is written.
- `specs/expNN_<slug>.md` — pre-registered spec (from `templates/experiment-spec.md`)
  for anything whose outcome steers the project.
- `expNN_<slug>.py` — one self-contained script per experiment (shared code in
  `common.py`). Numbered in execution order; a superseding variant gets a letter
  suffix (`exp05b_...`).

Conventions:
- Every run logs through `tools/explogger.py` (or an equivalent honoring the run-dir
  contract in AGENTS.md §3) into `logs/<exp_id>/<run_id>/`.
- Console output is tee'd: `python experiments/exp03_foo.py 2>&1 | tee logs/console_exp03_<tag>.log`.
- Configs are explicit at the top of the script or in a config file — no magic
  numbers buried in the body. The full resolved config is snapshotted per run.
- Each script starts with a docstring: what question it answers, and the gate.
