# Canonical v2 synthetic discovery integration (offline only)

This completes the **small offline integration seam**, not the live research system.
The existing standalone `campaign demo` remains a toy-ledger demo, unchanged in
meaning. This new, opt-in fixture actually uses `labloop_resources.Ledger`, its
canonical v2 sessions, multidimensional packets, pool occupancy and generations.
No provider/auth inspection, account allocation, OS sandbox, live adapter or public
state transition is enabled. Authentication verified and live eligibility are false.

## Runnable operator workflow

Choose a **new private directory outside the repository**, not an existing campaign
or account inventory. No inventory/runner/provider options are accepted here:

```sh
tools/lab campaign integrated-demo init --directory /tmp/my-integrated-demo --wait-seconds 1
timeout 30s tools/lab campaign integrated-demo run --directory /tmp/my-integrated-demo
tools/lab campaign integrated-demo status --directory /tmp/my-integrated-demo

tools/lab resources status \
  --inventory /tmp/my-integrated-demo/private/inventory.json \
  --policy /tmp/my-integrated-demo/project/labloop.json
```

`init` exclusively creates the directory and the exact fixed synthetic configuration.
It refuses reuse, including partial initialization. `run` is a bounded foreground
enforcer, not detached work. Wait is an explicit simulated subscription limit (0–5
seconds), not a provider response, daily reset, inferred allowance or renewed deadline.
`status` is read-only JSON; `report.md` is a regenerable view. Repeating `run` after
completion regenerates that report without any evaluation, lease renewal or ledger
mutation. A new `run` during incomplete work with lost enforcer evidence **refuses**;
it cannot manufacture recovery authority from SQLite or a passed deadline.

The fixture's v2 schema still describes a Claude adapter **intent**, because existing
strict v2 configuration supports only that intent. Its provider/model names and frozen
mission explicitly say synthetic. The integrated executor has exactly one hard-coded
`fixed-synthetic-no-provider` route, declares the intent/execution distinction in
JSON/report, and accepts only the exact fixture configuration and mission. It never
falls back to Claude. Ordinary `resources validate` is still not authentication.
Fresh synthetic fixtures are test allocations, not a mechanism for refreshing any real
account allowance. Never redirect an actual account to a new ledger to replenish it.

## What runs and what is charged

| Stable session/job | Purpose | Worker slices | Evaluator runs | CPU seconds | `local_token` units | Wall seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `demo-A` / `demo-A-job` | exploration | 1 | 1 | 2 | 3 | 10 |
| `demo-B` / `demo-B-job` | exploration | 1 | 1 | 2 | 3 | 10 |
| `demo-finalize` / `demo-finalize-job` | finalization | 1 | 1 | 2 | 3 | 10 |
| Unperformed confirmation partition | confirmation | 1 | 1 | 2 | 3 | 10 |

Campaign totals are four times each row's allotment. The two-candidate evaluator
mission is unchanged; the resource allocation additionally protects confirmation and
finalization opportunities. All dimensions charge **full allotments**, not measured
usage. The finalizer reserves its packet before producing B's finding and campaign
outcome; it performs no new evaluation but still charges its evaluator allotment.
No confirmation is fabricated to consume the remaining protected partition.

The unused confirmation packet remains reserved **as an immutable purpose partition**,
not as a pending session holding the single account slot. At completion: spent=3,
reserved/uncertain sessions=0, confirmation workers=1 with its full packet remaining,
exploration/finalization remaining=0 in every dimension. Resource status now includes
v2 operation IDs, purposes, costs, job/process identities and generations. The integrated
report and status consume that same transactional resource snapshot, not independently
computed usage or a second budget database.

## Actual termination/recovery boundary

The foreground enforcer launches only fixed, no-fork Python fixture children. Each
child is both its step's lease owner and evaluator/finalizer job. The parent creates a
lifecycle nonce and binds its exact identity to a retained `Popen` handle; it does not
claim that nonce is an OS start-time attestation.

1. Generation 1: A reserves/dispatches its canonical packet, commits the pure baseline
   measurement, then exits. The enforcer reaps it, settles once and records the shared
   evaluator's `abandoned` verdict (MSE 28, raw squared-error sum 196).
2. The durable synthetic wait occurs. Both protected partitions remain intact.
3. Generation 2 is admitted only after trusted observation of A's exit. B reserves and
   dispatches, evaluates the scripted square (MSE 0), commits immutable measurement,
   then signals readiness and pauses **before finding/completion acknowledgment**.
4. The parent records uncertainty, writes a pending report, externally sends SIGKILL
   and reaps B, checking `-SIGKILL`. A new Ledger connection reopens the same database.
5. Generation 3 requires the injected verifier to match the retained supervisor and
   job identities/outcomes. `Ledger.acquire_lease` atomically reconciles B and advances
   the generation, fully charging its packet once. It never treats the measurement as
   exit evidence. The finalizer reserves/dispatches its protected opportunity, reuses
   B's existing measurement, and records an honest unconfirmed outcome.
6. The finalizer exits without a final worker response; the enforcer verifies/settles
   it and renders `synthetic_improvement_unconfirmed` from durable evidence.

This is a **real killed lease-owning child and real connection/supervisor replacement
under a surviving trusted enforcer**, not crash survival of that enforcer or arbitrary
process-tree supervision. The in-memory verifier has no stored exit booleans, no PID
absence inference and no CLI trust-override option. Losing the enforcer loses its exit
proof. A new interpreter preserves unknown/active occupancy and existing allocation,
refusing replacement even after heartbeat expiry or deadline. If no measurement
committed, it does not silently reevaluate or invent an outcome. Recovering such jobs
requires an approved OS authority/supervision design; it is intentionally a gate.

## Durability and compatibility

There is one SQLite file, `private/resources.sqlite3`, and **no new SQL schema/version,
additional tables, allowance ledger or migration**. `sessions` + `session_packets` are
intents. Existing `audit` holds strict `synthetic.discovery.v1` envelopes with deterministic
keys and fixed candidate/session associations. Append/dedup/validation is within one
canonical write transaction. Duplicate, unknown-version, malformed and conflicting keys
fail closed. Raw evaluator evidence remains immutable, including invalid evidence.
The shared discovery validity/raw-sum gate, verdict, outcome and report writer are reused.

Reservation, dispatch, measurement commit, exit settlement, finding and finalization
are explicitly distinct durable transitions on that same connection/database. They
are **not** all one transaction: the measurement/exit-ack gap is intentional. Measurement
insertion fences the current lease and checks the active canonical intent in its write
transaction. Replacement settlement/generation uses the existing atomic reconciliation
API. Findings require settled evidence and are idempotent; report reads evidence and
resource status within one transaction. No cross-database exactly-once claim exists.
If interrupted before measurement commit, this coordinator gates rather than replaying
an incomplete campaign after losing its enforcer. Pure local evidence reuse after the
checked committed boundary is not remote request exactly-once execution.

The fixed fixture enforcer and private file modes are **not security boundaries against
same-UID code**, adversarial candidates or arbitrary descendants. v1/v2 inventory hashes,
allocations, schemas and existing clients retain their meanings. V2 status adds a
read-only operations list; the v1 status shape is unchanged. Existing toy evidence is
not migrated or rewritten. No PROTOCOL, state/events, FORMAT or legacy hooks change.

## Validation for this slice

- `timeout 90s python3 scripts/test_integration.py -v`: 9 tests pass. Includes real CLI
  execution; canonical status/report equality in every dimension; exclusive init and
  immutable authorization; external SIGKILL with fsynced test-only evaluator call audit
  (`constant-zero`, `square` exactly once); unchanged evidence after reopen; actual
  competing CLI denial; unknown/live occupancy; externally killed supervisor with lost
  verifier authority refusing fresh-process restart; audit rollback/corruption; invalid
  evidence; actual one-second simulated wait; and packet/deadline admission refusal.
  The external-SIGKILL/reopen/evaluator-call-audit test also passed 10 isolated repeats.
- All seven focused suites: 101 tests pass (9 integration, 19 discovery, 23 v1 resources,
  13 packet, 9 lease, 22 preflight, 6 sandbox).
- `timeout 180s bash scripts/acceptance.sh`: **152 passed / 10 failed**, exit 1. Fresh
  `git archive` of starting HEAD run under the same bound: **145 passed / the same 10
  provenance failures**. Exact labels are unchanged from [discovery](discovery.md).
  No legacy repair, suppression or claim of a green full suite.
- Logs: `/tmp/labloop-integration/` (focused suites, full/base acceptance, CLI output,
  validation/preservation). Implementation artifact includes durable copies.

Remaining live blockers: supported real identity/auth/account-side billing verification;
operator/worker/evaluator OS authority and sealed data; enforceable resource limits;
real descendant ownership/exit/outcome recovery after enforcer loss; bounded provider
adapter and account-pool integration; separately authorized publication. See [PLAN](PLAN.md).
