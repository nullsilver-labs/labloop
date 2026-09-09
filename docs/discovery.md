# Budget-aware discovery: implementation record

Branch: `aira-adj`

Exact starting commit: `992c2f4b921fb82e9f6d2b6657fc98ce03a4f595`.

## Direction

Keep legacy verification unchanged. A future operator-authorized discovery mission
allows different approaches without changing the objective, evaluator, permissions,
or spending authorization. Start with one checkpointed researcher, not a swarm.
Zero additional spending is the default; subscription capacity is not API credit.
No provider is enabled by this change.

This branch starts with **milestone 0**, a synthetic vertical slice. It is not the
subscription-only release described in the implementation proposal, and it does
not demonstrate autonomous scientific reasoning or enforce live account budgets.

The next partial slice adds a [private subscription resource foundation](resources.md):
strict configuration, hash-bound allocations and an atomic shared local-slice ledger.
It still cannot launch live workers, verify subscription authentication or enforce
worker/credential isolation. No local personal inventory or live allocation was
created during implementation; all tests use temporary synthetic configurations.

The next [bounded authentication/isolation feasibility slice](preflight.md) is now
partially implemented. It pins a CLI contract and adds explicit opt-in private status
collection, offline billing-attestation validation and a fixed Linux OS probe seam.
No real account inspection, namespace probe or live dispatch occurred. Official
identity schema and host isolation remain unverified; live eligibility stays false.

## Canonical resource integration now available

The original demonstrator below retains its toy ledger and command compatibility.
For the completed **offline canonical-v2 integration**, use the separate explicit
[`campaign integrated-demo init/run/status`](integration.md) workflow. It rejects A,
waits synthetically, evaluates B, externally SIGKILLs its real fixed child after
measurement, and reconciles on a new supervisor generation using retained trusted
fixture exit evidence. Its finalizer charges the protected resource packet, while
confirmation stays unperformed/reserved as a partition. Evidence and all accounting
share the existing v2 SQLite tables, not two databases. No schema migration or real
inventory activation occurs. Auth/live eligibility stays false; losing the enforcer's
exit evidence gates fresh-process recovery rather than freeing unknown occupancy.

This slice passes 101 focused tests and full bounded acceptance 152/10 versus a fresh
starting-HEAD 145/10, with exactly the same ten provenance failures listed below.
Independent review of this integration remains required; real account/OS/descendant
supervision and provider dispatch remain live-release gates, not demo guarantees.

## Run the no-spend demonstrator

From the repository root, choose a **new** private directory outside the repo:

```sh
tools/lab campaign demo init --directory /tmp/my-labloop-demo --wait-seconds 2
tools/lab campaign demo run --directory /tmp/my-labloop-demo --watch
tools/lab campaign demo status --directory /tmp/my-labloop-demo
```

`init` refuses an existing directory. It does not reset prior evidence. The directory
is created with mode 0700. Use a suitable private parent directory on shared hosts.

`run --watch` is a foreground, deterministic timer, bounded by the persisted campaign
deadline (default one hour including waits). It does not detach anything or call a
model. Without `--watch`, run returns at a resource wait; a later invocation resumes
from durable state. Restart without `--simulate-crash` after an injected crash.

```sh
tools/lab campaign demo init --directory /tmp/my-labloop-crash --wait-seconds 0
tools/lab campaign demo run --directory /tmp/my-labloop-crash --simulate-crash after_measurement
# Previous command intentionally exits 75.
tools/lab campaign demo run --directory /tmp/my-labloop-crash --watch
```

Available fault points are `after_reservation` and `after_measurement`.

## What it actually demonstrates

- One fixed mission: approximate y=x*x on seven registered integer inputs.
- A constant-zero baseline/candidate is measured and abandoned (MSE 28).
- A fixed scripted alternative, x*x, is measured (MSE 0). This is NOT a model
  discovering a hypothesis, nor evidence of generalization.
- A synthetic subscription wait occurs between candidates. Repeated invocations
  during the wait add neither operations nor waiting events.
- Two integer **synthetic worker slices** are authorized. Each operation records
  a durable intent/reservation before evaluation. Settlement replaces a reservation
  rather than charging it twice. These units have no monetary or quota meaning.
- Measurement and settlement are separate transactions. Process death between them
  preserves the measurement, which restart reconciles without reevaluation. A real
  parent-delivered SIGKILL regression now checks this gap in addition to injected exits.
  This demo uses its own toy ledger, not the shared subscription resource ledger.
- The evaluator is pure and local: interruption before its durable measurement can
  safely be replayed. This does NOT establish exactly-once remote request execution.
- A process-lifetime file lock rejects a second executor for the same demo directory.
  This is NOT an account-wide allocator or a remote-job lease protocol.
- Deadlines stop new evaluations. Already recorded results reconcile first; unresolved
  intents retain their reservations and appear in the report instead of becoming free.
- `report.md` is a regenerable, atomically replaced view. SQLite measurements and
  findings are source evidence; the demo never updates or deletes their rows.
- Claim status is always `untested`; no synthetic improvement is called confirmed.

All campaign state and uniquely keyed internal events live in `demo.sqlite3`.
No `state.json`, `events.jsonl`, frozen protocol, LEDGER, or public format is changed.
Internal events are not public exports; no publication/outbox guarantee is implied.
No arbitrary commands, HTTP requests, provider keys, or Claude sessions are used.

The database lives under the invoking user's authority. Its mission consistency
check catches accidental incompatibility; it is **not tamper resistance**. The demo
must not be repurposed as an isolation or monetary authorization boundary.

## Tests

```sh
python3 scripts/test_discovery.py
bash scripts/acceptance.sh
```

The legacy acceptance script includes the new offline suite. Tests cover a pivot
without mission change, waiting without repeated work, injected `os._exit(75)` at both
durable boundaries and externally delivered SIGKILL after measurement commit but before
settlement, settlement after a deadline, retained pending reservations,
concurrent executor refusal, idempotent report recovery, exclusive initialization,
mission mismatch refusal, and bounded foreground resumption.

### Validation of this first slice

- `python3 scripts/test_discovery.py`: 11 tests passed.
- `bash scripts/acceptance.sh`: 146 checks passed, 10 failed.
- Untouched starting commit, extracted to a temporary directory and tested under
  the same environment: 145 checks passed, the same 10 failure labels. All concern
  existing session/model provenance. The new aggregate discovery check accounts
  for the additional pass. The full legacy suite is therefore **not green** in this
  environment; no fix or suppression of those failures is included here.
- Python compilation and `git diff --check` passed.

### Immediate-order #2: externally killed evaluator recovery

- `timeout 45s python3 scripts/test_discovery.py -v`: **12 passed**; existing injected
  `after_reservation` / `after_measurement` crash tests are unchanged.
- `test_external_sigkill_after_durable_measurement_before_acknowledgment` launches a
  real child using a test-only wrapper around `advance`. After the real evaluator and
  SQLite commit, the wrapper signals a pipe and pauses before settlement or a final
  worker response. Readiness is bounded to 10s; the child pause itself is bounded to
  30s. The parent sends SIGKILL, checks return code `-SIGKILL`, empty stdout/stderr,
  and reaps it before opening a fresh connection. Cleanup also kills/reaps on timeout
  or assertion failure; no production crash/probe feature was added.
- Reopened evidence contains exactly one baseline measurement, one reserved operation,
  zero spent slices, three events, no finding, no outcome and claim `untested`. A
  report is regenerated directly from SQLite before restart, honestly showing pending
  work and baseline MSE 28 without any final worker reply.
- A fresh interpreter restarts with an fsynced evaluator-call audit: exactly
  `constant-zero`, then `square`, with no repeated baseline evaluation. Assertions cover
  unchanged original evidence/events, exactly two settled operations/two synthetic
  slices spent/nine event keys, baseline abandoned, alternative merely promising and
  `synthetic_improvement_unconfirmed`. Repeating restart after report loss reproduces
  the same report, every table and call audit unchanged. The isolated test passed
  **10 additional repetitions**. Synchronization/call counting are test wrappers;
  evaluation, SQLite commits, child process death and reopening are real, not mocks.
- Focused suites: **63 passed** (12 discovery, 22 preflight, 6 sandbox, 23 resources).
  Each other suite ran as `timeout 60s python3 scripts/test_<suite>.py -v`.
- `timeout 180s bash scripts/acceptance.sh`: **149 passed, 10 failed**, exit 1.
  Fresh extraction of untouched starting commit with `git archive`, running the same
  acceptance script under `timeout 180s`: **145 passed, 10 failed**, exit 1.
  The four aggregate offline suites account for the four additional passes.
  Both runs have exactly these same failure labels (none new, none suppressed):
  1. `and points lab at the live session`
  2. `session.start carries the requested model unasked`
  3. `and marks it a record, not a guess`
  4. `trial served models come from the transcript`
  5. `served keeps order, drops synthetic, keeps the switch visible`
  6. `and the fallback is the conf value`
  7. `lab model --json reports both facts in the recorded shape`
  8. `session.end carries what the transcript says was served`
  9. `state.json tracks the live run's models, served superseding requested`
  10. `run.done carries the run's models unasked`
- Python compilation (all four modules/suites and `tools/lab`), C syntax with
  `-std=c11 -Wall -Wextra -Werror -fsyntax-only`, shell syntax, `git diff --check`
  and whitespace checks on the three actual untracked-file deltas passed. Incoming
  tracked diffs and all other untracked files are unchanged; nothing is staged.
- Local logs: `/tmp/labloop-external-kill.yyy8PQ/` contains `discovery.log`,
  `external-kill-repeat.log`, `preflight.log`, `sandbox.log`, `resources.log`,
  `acceptance.log`, `baseline-acceptance.log`, `checks.log` and
  `preservation-and-diff.log`. These are local validation artifacts,
  not published evidence. Independent review subsequently found no issues; the parent
  also reran all 12 tests successfully at that milestone.

This proves recovery only for a committed result in the pure local toy evaluator. It
is not remote exactly-once execution, descendant supervision, real subscription
accounting, authentication or OS isolation verification. Invalid/all-poor evaluator
fixtures are now checked below; the true live gates in [PLAN.md](PLAN.md) remain outstanding.

## Downstream publication is part of the product

Projects still enter `../index` and render on `../nullsilver.com`. Discovery is not
an alternative registry or a separate dashboard. The current inspected contracts:

- `../index/projects.json` format 1.0 records repository/branch, slug, kind, title,
  human-authored summary, mark, and added date. It does not duplicate live state.
- The website reads the registry and fetches each project's `state.json` and
  `events.jsonl` from the registered GitHub branch.
- `../nullsilver.com/src/lib/lab/format.ts` manually mirrors lab format 1.3,
  accepts major 1 only, and defines legacy phase/status labels. Do not disguise
  discovery states as those legacy statuses simply to pass its parser.

Before any live discovery publication, make a coordinated consumer-first change:

1. Specify and fixture a new major discovery contract; keep historical major-1
   state/events readable, including mixed historical event versions after migration.
2. Update the website's manually maintained types, parsing, status presentation,
   project pages, timeline, and news/RSS classification. Test legacy and discovery
   projects together; resource waits must not look like scientific failures, and
   exploratory improvements must not look like confirmed findings. Run the website's
   required `npm run check` for website changes.
3. Add a supervisor-owned, redacted allowlist export and durable outbox. Export
   must exclude account inventory, balances, credentials, raw transcripts, and sealed
   confirmation material. Test interruption and retry without loss or duplication.
4. Generate the new lab format through `lab format sync`, not by editing FORMAT.json.
   Activate only after the compatible consumer is available and publication authorized.
5. Register projects through the existing index with owner-approved metadata/branch;
   never auto-author its human summary or push registration/deployment without approval.

No sibling repository is modified by the synthetic slice. No existing registered
project is migrated or published as a side effect of running it. Publication design
and consumer fixtures should be developed alongside the live mode, not left to an
unplanned dashboard task at the end.

## Next slices, in order

1. **Resource-safe foundation (partially implemented):** private operator inventory
   and project policy, strict field validation, hash-bound local slice allocations,
   shared SQLite admission, protected purpose partitions and cross-project contention
   tests now exist. See `docs/resources.md` for enforcement limits. Still required:
   verified account identity, operator-only OS ownership, official authentication
   preflight, billing checks/attestations and actual bounded session enforcement.
   Real subscription allowance stays unknown. No prepaid or metered route exists.
2. **Authentication/isolation feasibility spike (bounded partial slice implemented):**
   CLI `2.1.263` contract, conservative paid-path conflict checks, opt-in uninterpreted
   official status collection, expiring operator-attestation validator and fixed Linux
   sandbox/probe seam now exist. See [evidence classifications and blockers](preflight.md).
   Identity JSON schema is unsupported; no real account was inspected or attested.
   Adversarial sandbox tests are offline argument/packet fixtures, not host proof.
   Host probe and candidate/harness/evaluator OS authority separation must be proved
   before unattended live execution. No arbitrary worker runner exists.
3. **One live worker:** approved mission hash, compact checkpoints, bounded slices,
   candidate/finding records, evaluator-derived outcomes. Add all-poor and invalid
   measurement/leakage fixtures before interpreting live improvements.
4. **Durable supervisor:** account lease generation, process identity, restart
   reconciliation, bounded timer/service integration and reuse of supervised jobs.
   No final worker message is required for recovery. Resource reservations must
   include worker opportunities, compute, credits, and confirmation time separately.
5. **Confirmation/reporting:** frozen candidate and evaluator, sealed confirmation
   data, explicit minimum confirmation packet, deterministic finalization. New public
   format and consumer migration before publishing discovery states.
6. **Prepaid integration only after provider identification:** native-unit accounting,
   bounded request runner, retained unknown usage, provider-side billing controls,
   approved data routing. No live smoke test without explicit small authorization.

The synthetic slice now checks invalid measurements and all-poor search; it does not
test real authentication, credential isolation, public export recovery, or real billing. Those are
release blockers for their respective live features, not guarantees inherited from
these tests. Keep legacy prompts, hooks, and `loop.sh` unchanged until the live
mode exists; do not relax current guardrails preemptively.


## Remaining offline A/C, D/E slice

The demo's outcome previously reported success unconditionally after two candidates.
It now derives findings/outcome from validated authoritative evaluator evidence:
strict shape/types, finite nonnegative metric, fixed candidate/artifact/evaluator/data/
seed provenance, valid measured trivial baseline, strict improvement **and** the
existing square-grid-v1 zero-MSE gate. The baseline remains MSE 28 in the normal demo;
no baseline or frozen mission was changed to satisfy fixtures. Nonzero improvements
still fail that historical gate; ties are ties. Invalid baseline yields inconclusive
comparison, not a zero-error success. Explicit outcomes are `inconclusive_invalid_evidence`,
`no_improvement_tie`, `no_qualifying_improvement`, and the original
`synthetic_improvement_unconfirmed`; claim remains `untested`.

Raw SQLite evaluator evidence is retained byte-for-byte, including malformed JSON.
Reports skip invalid metric calculation and identify invalid evidence instead of
crashing or promoting it. Duplicate fields, nonfinite numbers, invalid types/counts,
provenance mismatch and unexpected leakage markers are invalid. This is contract
validation, not real-world leakage detection or tamper resistance.

19 discovery tests pass after the P1 corrections below, including the unchanged scripted demo, external SIGKILL,
injected crashes and immutable/idempotent recovery. New strict fresh-v2 resource and
lease APIs are **separate from the toy demo database**, described in resources. No
claim is made that the demo now runs through the canonical resource ledger or a
provider. Remaining live end-to-end integration is explicitly deferred.

Final remaining-slice validation after P1 corrections: 92 focused tests pass; bounded acceptance reports
151 passed / the same 10 failure labels listed above, versus incoming 149/10 and
untouched HEAD 145/10. Two new aggregate suites explain the additional passes.
Logs/attribution are in `/tmp/labloop-remaining/`, with durable artifact copies alongside
the supervisor implementation report. No failing legacy check was suppressed or fixed.


### P1 correction: compare authoritative sums, never rounded MSE

Review found a real bug in the initially checked verdict path: `5e-324 / 7` underflows
to `0.0`, incorrectly turning a positive error sum into a zero-gate success. Division
can also collapse distinct nonzero sums into a false tie. Validation now returns the
finite, nonnegative **raw sum**; equality, strict improvement and the historical
**actual zero-error** gate use raw sums, since both sample counts match the fixed
contract. Division is presentation-only, with the raw sum also shown in the report.
The normal baseline/mission and gate are unchanged, not relaxed to fit fixtures.

Two new regression tests failed before the fix and now pass: positive subnormal error
against the original baseline stays abandoned, and synthetic nonzero-baseline cases
exercise better/worse errors, genuine ties, exact zero versus positive subnormal,
and large integer sums that collide after division. Raw evidence and restart remain
unchanged. The initial 17 passing tests did not cover these edges. Independent
re-review approved the correction with no new issues; the parent independently reran
all 19 discovery tests and all 92 focused tests successfully. Fix-only diffs and
red/green logs are in the managed
`remaining/review-fix-evidence/` directory and `/tmp/labloop-review-fixes/`.
