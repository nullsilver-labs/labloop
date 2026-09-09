# Private resource foundation (experimental)

This is **local scheduling/accounting plumbing, not a live Claude adapter**. It
cannot call a provider, execute experiment code, or publish project state. Native
authentication, account-side billing controls, process supervision and OS authority
separation are outstanding prerequisites. A separate [bounded preflight feasibility
slice](preflight.md) adds opt-in uninterpreted official status collection, offline
billing-attestation validation and a fixed Linux probe; real identity and host
isolation remain unverified. Do not grant a worker access to this inventory or
ledger and treat that as sandboxing.

## Implemented contract

The JSON version-1 schema below is intentionally smaller than the original proposal.
Its existing contract is unchanged; the explicit fresh-v2 extension is documented below.
Use `templates/resources.subscription.example.json` and
`templates/labloop.discovery.example.json`. The examples contain no credentials,
private balances, actual entitlements, or activated project. Unknown fields fail
validation; larger proposed schemas are not silently accepted.

Supported:

- Exactly one subscription account pool per inventory, one active/unresolved
  Labloop-managed session in that pool, one configured research route per project.
  Several provider/model aliases may reference the same pool, never new allowances.
- Private operator inventory, outside the project repo; file mode 0600 (or stricter),
  parent directory 0700. A private SQLite ledger under a 0700 directory, mode 0600.
  File symlinks, hard links and foreign-owned private paths are rejected. These
  filesystem checks are hygiene, **not an adversarial same-user isolation boundary**.
- Integer local worker-slice ceilings, UTC-day accounting, campaign deadline including
  waits, and separately protected confirmation/finalization partitions.
- Authorization binds the resolved inventory (including ledger path), project policy,
  project root and mission content hash. Model selection changes also change the hash.
  The approved configuration and mission text are frozen in the private ledger for
  audit/recovery; CLI responses print hashes, not the private mission snapshot.
- Atomic reservations across all projects using that ledger. Outstanding reservations,
  active sessions and uncertain sessions each occupy the one local account slot.
- Durable audit records, idempotent authorization and stable reservation IDs. Repeated
  authorization cannot renew a deadline, change an allocation or reset consumption.
- Private budget summaries; vendor capacity is always reported **unknown**.

Not supported: prepaid balances or request pricing, metered cash spending, multiple
account pools/hosts, cross-provider fallback, publication, live dispatch, config
revision/migration, account-wide process identity verification, or proving that two
separately configured inventory files refer to the same real subscription account.
Every local project sharing an account must use the **same inventory and ledger**.
A new ledger is not a legitimate way to refresh a spent budget. Verified account
identity and operator-only ledger ownership must be established before live release.

### What each limit actually means

| Setting | Current status |
| --- | --- |
| Local pool/project daily slice ceilings | Enforced atomically at reservation |
| Local campaign purpose partitions | Enforced atomically at reservation |
| One unresolved session per configured pool | Enforced at reservation; no automatic expiry |
| Campaign deadline | Enforced at admission and dispatch bookkeeping |
| Turn and session-wall ceilings | Validated configuration; live enforcement awaits adapter/watch integration |
| Native subscription authentication | Not verified; opt-in preflight status schema unsupported |
| Disabled account-side overage/auto-replenishment | Not provider-verified; separate offline operator-attestation validator only, no real attestation created |
| No subagents/paid features | Required configuration; live harness enforcement not implemented |
| Subscription remaining allowance | Unknown, not inferred from local slice counts |
| No new spending in this foundation | No inference/live dispatch exists; separate preflight has opt-in non-inference status and fixed OS probe, neither run during implementation |

Route explanation always says `eligible_for_live_dispatch: false` and lists blockers.
`resources validate` means configuration validation, **not verified billing safety**.
There is no dollar-based usage estimate or invented subscription-token balance.

## Operator workflow

Prepare a private inventory from the example, a project `labloop.json`, and a human
mission `MISSION.md`. Do not copy an existing protocol into an open-ended mission
without explicit approval. Keep a single canonical private inventory across projects.
These commands do not enable any live route:

```sh
tools/lab resources validate \
  --inventory ~/.config/labloop/resources.json --policy /path/to/project/labloop.json

tools/lab route explain research \
  --inventory ~/.config/labloop/resources.json --policy /path/to/project/labloop.json
```

Review the mission, policy, inventory and returned `authorization_hash`. Validation
reads files only; it does not create a ledger. The following explicit operator command
records approval of **local scheduling allocations only**, not a live-research launch:

```sh
tools/lab campaign authorize --expected-hash REVIEWED_HASH \
  --inventory ~/.config/labloop/resources.json --policy /path/to/project/labloop.json

tools/lab budget status \
  --inventory ~/.config/labloop/resources.json --policy /path/to/project/labloop.json
```

`resources status` currently returns the same private project/account scheduling
summary as `budget status`, and requires an existing authorized allocation. Neither
command bootstraps a missing ledger. Printed output is private operator output, not
an input to `events.jsonl` or the website. Do not commit or publish it.

The CLI is intended for the operator; **there is not yet a separate worker OS identity
that makes this operator-only by construction**. The foundation cannot safely launch
untrusted workers until that boundary exists. Neither a role environment variable nor
a CLI flag is treated as proof of operator authority.

Ledger inventory and per-project authorization hashes are immutable in this slice.
If either changes, operations refuse rather than silently reinterpret the grant.
A reviewed migration/revision mechanism must be added before changing an activated
policy. Do not delete the ledger or change the project ID to work around rejection.

## Reservation/recovery semantics

The supervisor-side Python API exists for offline tests and later integration; no
public CLI exposes dispatch, cancellation, exit attestation, or arbitrary execution.

1. `reserve(stable_id, purpose)` opens an immediate SQLite transaction. It checks
   authorization, campaign deadline, pool concurrency, account/project UTC-day caps,
   and the purpose partition before recording an intent. A denial rolls back.
2. `mark_dispatched(id)` must commit **before** a future adapter launches anything.
   It records the bounded deadline and prevents cancellation as undispatched.
   If the reservation crosses UTC midnight before dispatch, cancel it and reserve a
   new ID against the new day. A stable-ID retry returns the existing state; it does
   not authorize re-execution of a settled/cancelled operation.
3. Crash or timeout after dispatch retains the account slot. `mark_uncertain(id)`
   makes this explicit; passage of time or heartbeat loss never releases it.
4. Only an undispatched reservation can be cancelled and release its slice. The
   trusted supervisor must establish process exit before `record_exit(id, code)`.
   An exit, including a failed/killed session, consumes one local slice. This API
   cannot itself prove exit; process-identity enforcement is a live-release blocker.
5. Settlement replaces the reservation. `reserved`, `uncertain` and `spent` are
   disjoint; they are never subtracted twice. A conflicting repeated exit is rejected.

Purpose partitions are deliberately rigid. With four campaign slices, one for
confirmation and one for finalization, exploration has exactly two. Unused protected
slices cannot be borrowed. `available_for_exploration` reports its remaining partition,
not an immediate admission promise: daily ceilings, occupied slots, deadlines and
unknown vendor allowance may still block work.

A reservation/active/uncertain session consumes its reservation day's local daily
ceiling. Campaign counts persist across day changes. Local slices are opportunities,
not guaranteed future subscription capacity. Protected worker slices do not reserve
CPU, API credits, confirmation datasets or vendor capacity; those separate resource
dimensions must be implemented before live confirmation can be considered affordable.

## Tests and downstream compatibility

```sh
python3 scripts/test_resources.py
python3 scripts/test_discovery.py
python3 scripts/test_preflight.py
python3 scripts/test_sandbox.py
bash scripts/acceptance.sh
```

The unchanged v1 resource suite has 23 passing tests. Current totals including the
new v2 extension are recorded in `docs/PLAN.md`; older runs below are historical.
The foundation's prior combined acceptance run reported 147 passing checks and 10 existing provenance
failures; the untouched base previously reproduced the same 10 failure labels (145
passes before the two new aggregate suites). The full legacy suite is not green in
this environment. Python compilation and `git diff --check` also pass.

Tests use synthetic time, private temporary inventories and temporary SQLite files.
A multiprocessing race uses two projects on the same ledger and admits exactly one.
Other checks cover account daily exhaustion, hash changes, protected partitions,
unknown usage after reopen, no implicit deadline/spend reset, cancellation rules,
private path checks, rejected paid/unknown configurations and CLI no-live eligibility.
They require neither a subscription nor any API credits.

The standalone synthetic demo retains its separate toy database. The new opt-in
[`campaign integrated-demo`](integration.md) uses this actual canonical v2 Ledger
with namespaced immutable audit evidence, fixed synthetic children and retained trusted
exit observations. It accepts only newly initialized exact fixtures, not real inventory.
Neither demo exercises a real provider. All suites are required. Legacy format 1.3,
`state.json`, `events.jsonl`, registered projects in `../index`, and the current
`../nullsilver.com` consumer remain untouched. See [discovery publication sequencing](discovery.md#downstream-publication-is-part-of-the-product).

## Explicit fresh v2: offline confirmation packets and cooperative leases

**Implemented offline, not live released.** Version-1 inventories, policies,
authorization hashes and APIs retain their meaning. The v1 examples above remain
unchanged. The separate `templates/resources.subscription.v2.example.json` and
`templates/labloop.discovery.v2.example.json` are **unactivated examples for fresh
configurations only**. Both inventory and policy must explicitly select version 2;
the new private ledger records version 2. The ledger path is intentionally the same
canonical path, not an alternate allowance ledger. Existing-ledger version/inventory
mismatch refuses before changing allocation/schema; migration is unsupported. Never
remove the ledger, select a new path/project ID, or reauthorize to refresh allocation.
No real configuration was authorized in this implementation.

The canonical synthetic integration adds no tables or schema changes. V2 resource
status now includes stable operation IDs, purposes, per-dimension costs, process/job
identities and generations; integrated reports use the same transactional snapshot.
The v1 status shape is unchanged. See [integration](integration.md) for the runnable
operator workflow and the explicit gate when the fixture enforcer loses exit evidence.

### Immutable local packet accounting (D)

The v2 allocation keeps explicit campaign/daily/confirmation/finalization worker
slice counts and adds exactly `local_packet`: `inference_unit`, `campaign`,
`confirmation`, `finalization`. Each purpose packet has exactly these positive
integer dimensions:

- `evaluator_runs`: local evaluator-run opportunities;
- `cpu_seconds`: local CPU-time **allotment**, not measured usage or an rlimit;
- `inference_units`, with the only supported unit `local_token`: explicit local
  token accounting, **not** actual subscription tokens/credits, cash, or entitlements;
- `wall_seconds`: local sequential wall-time allotment, including the remaining
  protected confirmation/finalization time check before the fixed deadline.

Each `reserve(id, purpose, lease=token, costs={...})` consumes exactly **one** explicit
local worker opportunity plus its separately specified positive costs in all four
dimensions, atomically in the existing grants/sessions/audit ledger. No separate
allowance/reset ledger exists. Exploration gets the campaign total minus the two
protected partitions in **each** dimension, never borrowing unused protected units.
The allocation, units, costs, IDs and deadline are immutable across reopen/retry.
Only an undispatched cancellation releases costs. Active/uncertain/settled work
charges its **entire reserved allotment**, including a failed/killed job; there is
no actual-usage refund or vendor-usage inference.

Admission and dispatch both recheck deadline feasibility of the proposed operation
and all remaining protected wall allotments. Waiting never renews the deadline.
Protected budgets must retain at least one unit of every dimension for each remaining
protected worker. At both admission and dispatch, remaining protected wall seconds
must also be no more than remaining workers times the configured slice ceiling.
For example, two confirmation workers with 1800 wall seconds at a 900-second ceiling
cannot reserve only one second for the first worker: 1799 seconds would not fit the
last worker. The final protected worker must consume the remaining wall allotment,
leaving zero protected wall when zero workers remain. Denials roll back all changes,
including for a persisted pre-fix intent rechecked at dispatch; they never rewrite
its immutable costs. This P1 review fix changes no v1 behavior or resource limits.
Known daily ceilings must leave enough local worker opportunities before deadline.
These are conservative necessary feasibility checks, not a promised future schedule:
other authorized projects, future waits, OS availability or vendor limits may still
prevent completion. Unused protected allocations remain unavailable to exploration.
Every unsupported/unknown field, cash route, inferred vendor unit and missing cost
dimension fails closed. The API does not launch workers or evaluators.

### Cooperative pool fencing and trusted exit seam (E)

V2 adds `leases` and `session_packets` **inside the same canonical private database**.
A pool lease binds an opaque stable supervisor owner and explicit process identity
(`host`, `boot_id`, `pid`, `start_id`) to a monotonically increasing generation.
Job IDs are unique and immutable; dispatched packets bind job, process and generation.
One lease applies to the configured pool across projects, scoped only to
**Labloop-managed research sessions**, not unrelated interactive use/devices/vendors.

Supervisor-only APIs (no CLI dispatch/exit/replacement interface):

1. `acquire_lease(owner, identity)` creates generation 1. Same owner+identity retry
   is idempotent, not renewal. `renew_lease(token)` records heartbeat/observational
   expiry. An expired/missing heartbeat **never** releases the lease or a slot.
2. All v2 `reserve`, `mark_dispatched`, `cancel_undispatched`, `mark_uncertain`,
   `record_exit`, and `renew_lease` mutations require the current exact token.
   Generation checks also run before idempotent settlement/cancellation returns.
   Dispatch binds `job=` and `process=` before any future adapter may allow work.
   A real trusted adapter must establish this identity using retained process/job
   handles and an inert pre-work boundary; no such runner is implemented here.
3. `Ledger(..., exit_verifier=trusted_callable)` is an explicit **trusted-supervisor
   dependency**, never a worker packet, public flag or CLI boolean. There is no
   default verifier. It receives `("supervisor", lease_snapshot)` or
   `("job", packet_snapshot)` with stable identity. Only an integer exit code means
   the trusted integration has independently established prior process/whole-job
   exit **and outcome**; `None`, boolean, exception or any uncertainty blocks.
   A worker's bare assertion must never be used to implement this callable.
4. Replacement first requires the old supervisor's verified exit, then every
   active/uncertain job's verified exit/outcome. Owner exit alone is insufficient.
   Undispatched intent can be cancelled only after owner exit, under the cooperative
   rule that no work begins before committed dispatch. Unknown jobs remain occupied.
   Verification runs **outside** write locks; the complete lease/pending snapshot is
   compared again atomically before settlement/replacement. Any changed generation,
   heartbeat or pending state denies without partial release. `record_exit` likewise
   verifies outside the lock then rechecks job identity and current generation.
5. Successful recovery settles known jobs once, cancels never-dispatched intents,
   records audit evidence and increments generation in one transaction. Old tokens
   cannot settle, cancel, renew, reserve or dispatch; new tokens cannot reuse old
   operation generations. There is no automatic replacement timer/service.

| Property | Classification and scope |
| --- | --- |
| Immutable allocation, multidimensional partitions and finite deadlines | **Enforced** by v2 local accounting transactions only |
| One unresolved managed session, monotonic generations and stale-token refusal | **Enforced** cooperatively in one canonical ledger |
| Heartbeat/expiry and recorded process/job identifiers | **Observed** supervisor bookkeeping, not liveness proof |
| Exit/outcome results supplied by trusted verifier | **Observed** through injected trusted seam; tests use synthetic callbacks, no production verifier |
| CPU/inference/wall limits and process-tree termination on real workers | **Not enforced** by this accounting API; no rlimit/hardware/vendor reservation claim |
| Actual billing route/overage controls | **Unverified**; any separate declaration remains **Operator-attested**, not provider proof |
| Live eligibility | **Enforced false**, including v2 and successful synthetic reconciliation |

Tokens and SQLite are **not** an adversarial same-UID security boundary. This does
not kill stale workers, verify actual process exit, provide remote exactly-once
execution or vendor account-wide exclusivity. Operator-only OS authority, trusted
whole-tree exit verification/enforcement, candidate/evaluator isolation, actual
identity/billing assurance and an authorized bounded live adapter remain release
gates. [Official authentication documentation](https://code.claude.com/docs/en/authentication#sign-in-without-an-api-key)
also supports Console OAuth from v2.1.242, so OAuth/no API key alone is not proof of
subscription billing. The official identity schema remains unsupported, never guessed.
See [preflight's cited public research and scoped signature verification](preflight.md#public-research-conclusions-and-scoped-publisher-verification);
verified publisher provenance for one binary is not identity or billing verification.

New focused commands: `python3 scripts/test_resource_packets.py` and
`python3 scripts/test_resource_leases.py`. Both are included in full acceptance.
Multiprocessing races are real synthetic local processes; exit callbacks are offline
fixtures, not observations about a real worker. See `docs/PLAN.md` for final counts
and validation artifacts. Existing v1 tests remain required and unchanged.
