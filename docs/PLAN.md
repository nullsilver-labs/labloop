# Labloop delivery plan and remaining gates

## Goal and scope

Ship a small, tested state-transition system before a general research platform.
The governing plan is A–F below. Authentication, isolation, billing and supervision
are live-release gates, not guarantees inherited from the offline demo or SQLite.
No public-format migration, provider inference or live unattended research is
currently authorized. Preserve legacy state/protocol/event ownership and evidence.

## Current evidence

- Standalone deterministic demo retains its private toy SQLite ledger and one fake
  route. A separate explicit [integrated demo](integration.md) now connects the fixed
  workflow to the actual canonical v2 resource Ledger, packet reservations and lease
  generations, without a provider adapter or activation of real configuration.
- Private resource foundation: strict inventory/policy validation, hash-bound local
  allocations, atomic reservations, protected worker-slice partitions and contention
  tests. Local slices are opportunities, not guaranteed vendor allowance.
- Preflight feasibility: pinned binary contract, conservative conflicting-route
  rejection, opt-in private uninterpreted auth-status collection, expiring/bound
  billing-attestation structure, and a fixed opt-in Linux isolation probe.
- Real CLI version/help observed; parent independently verified publisher provenance
  for the exact 2.1.263 linux-x64 binary at 2026-09-06T18:52:08Z via the official
  signed manifest and matching installed hash/size. See [preflight](preflight.md)
  for citations and immutable evidence. Runtime preflight still checks only an
  operator-approved digest; identity schema, account status, routing and billing
  remain unverified.
- Sandbox argument/packet tests are offline fixtures. A subsequent real fixed host
  probe exited 1 with a generic fail-closed denial and produced no isolation evidence.
  Exact failed stage is unknown; no weaker retry was used. Adversarial host isolation
  remains unproven. See [host-isolation](host-isolation.md) for the attempt and gate
  failure: no state.json exists, so no gate could be persisted.
- Trusted-tool termination cleanup has independent review approval and real synthetic
  SIGTERM/SIGKILL regression tests. Parent-death protection covers the direct child
  while retained, not arbitrary grandchildren or an escaping process tree.
- Prior parent review ran 62 tests. Immediate-order #2 now passes 63 focused tests:
  22 preflight, 6 sandbox, 23 resources, 12 demo, including a real parent-delivered
  SIGKILL after committed measurement and before settlement/final worker reply.
  The new kill regression also passed 10 isolated repetitions. Fresh-interpreter
  recovery preserves evidence, evaluates each candidate once and regenerates reports.
- Full acceptance rerun: 149 passed, 10 failed. A fresh untouched-HEAD extraction
  reproduced the same 10 provenance failure labels (145 passed, 10 failed); no new
  failure or suppression. Python compilation, C syntax/warnings, shell syntax and
  tracked/actual untracked-delta whitespace checks pass; incoming work is preserved
  and nothing is staged. Exact labels and local logs are in [discovery](discovery.md).
  Independent review found no issues in this recovery slice (run
  `e85064b1-a77f-4796-bffc-66dca5136904`). Parent then independently reran all 12
  discovery tests and `git diff --check`: passed.
- Remaining offline A/C, D and E implemented; the initial 88 passing focused tests
  missed two P1 edge cases found by review. Corrections now pass **92 focused tests**
  (19 discovery, 23 unchanged v1 resources, 13 v2 packet, 9 v2 lease, 22 preflight,
  6 sandbox). Raw sums prevent underflow/rounded equality from changing the zero
  gate; remaining protected wall must fit remaining worker ceilings at admission
  and dispatch. Both new regressions failed before their fixes. Independent re-review
  found both P1 findings resolved with no new issues (run
  `9928be53-c221-460e-950a-c2d3767956ff`); parent independently reran all 92 focused
  tests, Python compilation, C/shell syntax and diff checks successfully.
  Full bounded acceptance: **151 passed / the same 10 known provenance failures**,
  versus supplied independently reproduced incoming 149/10 and untouched HEAD 145/10.
  Exact labels remain listed in discovery; no legacy fix or suppression.
- Canonical-ledger integration now passes **101 focused tests**, including 9 new
  integration tests. One actual fixed lease-owning child is externally SIGKILLed after
  committed measurement; the surviving fixture enforcer reaps it, reopens the Ledger,
  and permits generation replacement/reconciliation without reevaluation/double spend.
  Finalization charges its protected packet; unused confirmation stays partitioned.
  Losing that enforcer's trusted evidence gates recovery and retains unknown occupancy.
  Full bounded acceptance: **152 passed / the same 10 provenance failures**; a fresh
  starting-HEAD extraction reproduced 145/10. See [integration](integration.md) for
  runnable commands, transactional boundaries and evidence limits. Independent review
  found no issues (run `4dc61520-6f4b-41c0-ba6a-fa2036a53a51`, OK with scope notes).
  Parent independently reran all 101 focused tests, compilation and diff checks: passed.
- Live dispatch is always false. Work remains uncommitted; incoming work is preserved.

Details and evidence limits: [discovery](discovery.md), [resources](resources.md),
[preflight](preflight.md). Passing mocks must never be relabeled host verification.

## A. Milestone 0 — tiny end-to-end demonstrator

**Implemented and checked offline.** Keep the scripted worker, deterministic local
baseline/evaluator, private ledger, one fake subscription route and no public migration.

Recovery boundary checked offline: a test-only wrapper pauses a real child after
measurement commit, before settlement. Its parent waits for explicit bounded readiness,
sends SIGKILL and reaps it. Reopening shows one reserved operation, a durable baseline,
zero spent slices and no finding/outcome/final reply. A fresh interpreter reuses that
measurement; an fsynced call audit proves no duplicate evaluator call. Exact operations,
spend, event keys and unchanged evidence are asserted, as are pending/final report
regeneration and an unconfirmed-only outcome. Existing injected-exit tests remain.
This is the toy ledger, not shared resource integration or remote exactly-once execution.

Now checked: invalid/nonfinite/malformed/duplicate evaluator evidence, provenance and
leakage-marker mismatch never become promising. Invalid baseline makes comparison
inconclusive. All-poor, tie and nonzero improvement report honestly against the
unchanged measured trivial baseline and the existing square-grid-v1 zero-MSE gate.
The formerly unconditional successful campaign outcome is now evaluator-derived.
Following P1 review, comparisons use validated **raw error sums**, not divided MSE:
positive subnormal error cannot pass the zero gate, and distinct sums cannot become
a tie through rounded division. Reports show raw sums alongside presentation-only MSE.
Raw evidence is never replaced during validation/recovery; reports regenerate.
These fixtures are not proof of sealed-data separation for arbitrary candidates.

Additional integration now checked:
- `campaign integrated-demo init/run/status` is a fresh fixture-only canonical-v2
  entry point. It reuses evaluator/evidence/report logic with same-ledger intents,
  audit measurements and settlements; no new schema or allowance-reset ledger.
  Standalone `campaign demo` remains toy accounting. Neither exercises a live provider.
  The shared offline accounting gap is closed; account/OS/live-supervision gates below
  remain open. Independent integration review and parent revalidation are complete.

## B. Early authentication/isolation feasibility

**Offline seam implemented; real feasibility still unproven.**

Remaining gates, in order:
1. **Provenance observed complete for the exact pinned artifact/time above:** parent
   verified the signed manifest, installed hash and size using the published key
   fingerprint. See [preflight](preflight.md#public-research-conclusions-and-scoped-publisher-verification).
   Repeat provenance verification for any changed artifact; runtime does not do GPG.
   Supported auth-status identity schema remains a blocker; version output, OAuth and
   approved hashes do not establish identity/billing. No guessed identity fields.
2. Obtain explicit authorization for bounded real account inspection; verify supported
   native authentication and effective account identity without inference or secrets in
   logs. Test effective routing and helper/hook/config exclusions, not only argv mocks.
3. Establish supported account-side billing inspection or a dated, identity/config-bound
   operator attestation with explicit expiry and limitations. Attestation is not proof
   of zero spend, and cannot clear unknown real identity. Allowance remains unknown.
4. **Blocked by a real failed-closed host probe:** obtain authorization for bounded
   prerequisite diagnosis, with no weakened protections or OS policy changes. No
   successful namespace/denial evidence exists yet; see [host-isolation](host-isolation.md).
   Then test filesystem, environment, inherited FDs, process/proc and network denial
   with positive controls. Missing features or denied namespaces are blockers, never
   permission to weaken isolation.
5. Establish operator-only authority over credentials, ledger and sealed evaluator data.
   Candidate execution must pass through a supervisor-controlled OS sandbox; an ordinary
   subprocess of an authenticated harness is not credential-isolated. Same-UID private
   file modes are hygiene, not the required adversarial boundary.
6. Prove candidate/evaluator integrity and sealed-data separation before arbitrary
   candidate execution. A fixed probe pass is not an enduring general sandbox certificate.

No actual account invocation, namespace launch, privileged provisioning or weakening
of permissions is implied by offline development. Follow CLAUDE.md stop/gate rules.

## C. Recover despite abrupt termination

**Durable toy and canonical-v2 synthetic recovery checked; full live recovery absent.**

Require durable intent before dispatch; stable operation IDs; supervisor-recorded
completion; incremental checkpoints; recovery independent of a final model response.
The offline external-kill side-effect/acknowledgment regressions now pass (A), including
v2 replacement generations after actual fixture child exit verified by a surviving
enforcer. A fresh process without retained verifier evidence refuses recovery; passed
deadlines and committed measurements never establish exit. This is not whole-enforcer
crash survival or arbitrary descendant verification.
Before live use, handle unknown outcomes and preserve occupied capacity until process
exit and operation identity are reconciled. General crash-safe descendant ownership
and enforcement require an approved supervision mechanism; PDEATHSIG alone is not it.

## D. Multidimensional confirmation reserves

**Implemented and checked as explicit fresh-v2 local accounting only.**

Inventory/policy/ledger v2 is an opt-in strict schema; v1 behavior/hashes remain
unchanged. Existing-ledger mismatch refuses without migration/reset. One canonical
ledger stores immutable worker, evaluator-run, CPU-second, explicit `local_token`
inference-unit and wall-second partitions for confirmation/finalization/exploration.
Admission/dispatch recheck the entire remaining protected packet, local daily worker
opportunities and campaign deadline including waits. Full reserved allotments are
charged even on failure, not actual usage. Thirteen tests cover independent exhaustion,
remaining-worker feasibility, deadline waits, strict unknown/unit/type rejection,
atomic contention and immutable reopen. P1 follow-up preserves both protected wall
bounds: after each reservation/dispatch, remaining seconds must be at least remaining
workers and at most remaining workers times the slice ceiling. Zero remaining workers
therefore requires zero remaining protected wall, not an impossible leftover packet. No automatic real configuration activation.

Remaining live gate (not implied by offline accounting):

Pre-register an explicit minimum confirmation packet: authorized worker slice(s),
evaluator-run count, CPU time, any inference allocation/credits, and time remaining
before the campaign deadline. Reserve each constrained dimension separately. Deny
exploration when the packet cannot still be completed; never borrow protected reserves
silently. Test exhaustion independently in every dimension, including deadline waits.
Locally reserved opportunities cannot reserve actual subscription capacity.

## E. Account-pool lease and recovery protocol

**Implemented and checked as a cooperative fresh-v2 supervisor API only.**

Same-ledger pool ownership binds stable supervisor/job/process identity and monotonic
generation. Every v2 session mutation and renewal fences stale tokens, including
idempotent retries. Lease expiry/heartbeat loss never frees occupancy. Replacement
requires a trusted injected verifier to establish prior owner exit and every active
or uncertain job's exit/outcome; unknown stays occupied. Verification occurs outside
write locks, followed by atomic generation/pending-state recheck. No default verifier,
CLI worker assertion or live launcher exists. Nine tests include real synthetic
two-process competition, old job presumed alive, stale settlement/dispatch, restart
idempotency and verification/reconciliation races.

Remaining live gate:

Require one supervisor lease per applicable pool; stable job/process identity; lease
generation/fencing; reconciliation before replacement; no capacity release on heartbeat
loss alone; and two-supervisor simultaneous-start tests, including stale workers that
continue running. Bind settlement to the actual operation and process generation.
Scope the claim to **one active Labloop-managed research session**. Unrelated interactive
Claude usage, other devices and vendor-wide exclusivity cannot be enforced by this ledger.
A different inventory/ledger is not a legitimate way to reset account allocations.

## F. Honest configuration and release gates

**Strict small schemas and evidence classifications exist; extend only with enforcement.**

Classify each supported safety field as Enforced, Observed or Operator-attested, with
scope and freshness. Mark unsupported/unknown capabilities explicitly rather than
accepting protective-looking settings. Reject unsupported safety-critical settings.
Keep live eligibility false until all applicable real gates and bounded adapter checks
pass. Preserve immutable evidence, trivial baselines and preregistered verdict gates.

Offline evaluator invalid/all-poor tests, the explicit local packet, deterministic
toy finalization and canonical-v2 synthetic finalization/recovery are now checked. Before release require real evaluator integrity,
actual enforceable confirmation resources, live supervision and exact-state validation.
Publication is a separate later slice: compatible consumer/format, allowlisted private
export, durable outbox/retry and explicit deployment/registration authorization.

## Immediate execution order

1. Record this plan and preserve the existing dirty work (done by creating this file).
2. **Implemented, checked and reviewed:** external hard-kill
   regression; 63 focused tests pass; full acceptance 149 passed / 10 baseline
   provenance failures, independently reproduced on untouched HEAD. No legacy repair
   or suppression. See discovery validation for exact labels and local log references.
3. **Complete:** independent recovery review found no issues; parent reran all 12
   discovery tests successfully. Review approval is offline-only, not live authorization.
4. Exact-artifact publisher provenance is now observed verified by the parent;
   resolve B's official identity-schema gap, then request the specific account/host
   verification authorization needed. If blocked, stop that path rather than building
   around invented guarantees.
5. **Implemented offline:** invalid/all-poor fixtures and fresh-v2 D/E APIs. Supervisor
   approved this narrow schema/authority seam: no v1 migration, full allotment charges,
   no default verifier, no live eligibility. See resources for Enforced/Observed/
   Operator-attested classifications. Real evaluator/OS authority, resource enforcement,
   process-tree verification and bounded provider adapter remain deferred live gates.
6. **Integrated, checked and independently reviewed offline:** explicit fresh
   canonical-v2 scripted demo, fixed-child trusted exit registry, external SIGKILL,
   new-generation reconciliation and protected finalization. No real inventory is
   accepted by the integration entry point. Audit-only extension preserves v2 SQL
   schema. This completes the bounded offline integration, not account/OS/live gates.
7. Public-doc research notes keyless Console OAuth since CLI v2.1.242, plus profiles,
   federation and gateway precedence: native OAuth/no API key does not prove subscription
   billing. Identity schema stays unsupported. [Preflight](preflight.md#public-research-conclusions-and-scoped-publisher-verification)
   now records the parent's research conclusions with official citations and the
   scoped read-only signature/hash verification; no account inspection is implied.

### Remaining-slice validation artifacts

- Local logs and attribution: `/tmp/labloop-remaining/` (six suite logs,
  `acceptance.log`, compilation/check log, incoming untracked hashes, after hashes,
  and per-file incoming-vs-worker diffs). Durable copies accompany the implementation
  report in the supervisor's `remaining/evidence/` artifact directory.
- The incoming `README.md`, `tools/lab`, preflight/sandbox modules/tests, v1 templates
  and all other unaffected incoming files remain byte-identical to intake. The only
  additional tracked diff is two aggregate acceptance-suite lines. No staging,
  commit, provider/auth access, namespace launch, host installation/configuration,
  public migration, PROTOCOL/state/events/FORMAT edit or legacy hook/loop edit.
- Independent review and the targeted P1 re-review are complete with no outstanding
  findings. Checked offline implementation is not a claim of live D/E enforcement
  or scientific confirmation.

Update this document as evidence changes. A checked-off offline task is never implicit
approval for money, credentials access, OS reconfiguration, live execution or publication.


### P1 review follow-up

The initial offline review blocked on two genuine correctness defects, not live-gate
scope objections. The minimal fixes compare raw evaluator sums before the historical
zero gate, and preserve protected wall's remaining-worker upper bound as well as its
lower bound. Four new tests cover subnormal/rounded-equality verdicts, unchanged raw
evidence, atomic undersized packet rejection for both protected purposes, dispatch
of pre-fix immutable intents, and zero-worker leftovers. No allowance reset/migration,
new runner or live capability was added. Independent re-review approved both fixes;
parent independently reran all 92 focused tests successfully. Full acceptance is
still not green: the ten preexisting provenance failures remain disclosed.

Follow-up logs, red/green evidence, before/after hashes and fix-only diff are in
`/tmp/labloop-review-fixes/`, with durable copies in the managed
`remaining/review-fix-evidence/` artifact directory. Full acceptance remains 151/10,
with exactly the same ten disclosed labels as incoming 149/10 and untouched HEAD
145/10; no legacy fix or suppression. Parent's separate read-only provenance evidence
is `remaining/provenance-2.1.263/`, not an account/billing/host-isolation observation.
