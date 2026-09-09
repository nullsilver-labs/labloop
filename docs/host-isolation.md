# Host isolation feasibility: failed-closed attempt

Recorded 2026-09-06T20:26:53Z, following the operator's instruction to continue.
This is a real host-probe attempt, not a passing mocked test or a live release.

## Attempt and result

```text
tools/lab sandbox probe --operator-run-host-probe \
  --evidence /tmp/labloop-host-probe.rpqgok/evidence.json

exit code: 1
stderr: sandbox: denied; host isolation not established; no fallback
stdout: empty
```

No `evidence.json` was produced. The command was bounded by a 60-second outer tool
limit and the probe's existing compilation/execution limits. Only the fixed bundled
synthetic probe was eligible for execution. No account inspection, credentials read,
provider inference, installation or persistent host configuration change was attempted.

The CLI intentionally withholds raw subprocess diagnostics. This result does **not**
establish which stage failed: compilation, configured resource bounds, namespace
creation, probe checks or another prerequisite. In particular, do not label AppArmor
as the proven cause based on the observations below. Successful namespace creation
and filesystem/process/network denial have **not** been demonstrated.

No weaker namespace set, alternative launcher, permission change or retry was used.

## Read-only prerequisite observations

- `/usr/bin/cc` is present.
- `/usr/bin/bwrap --version` reports `bubblewrap 0.9.0`.
- Bubblewrap help advertises the required user-namespace-disable/assert, cgroup,
  parent-death, new-session and read-only-remount options.
- `kernel.unprivileged_userns_clone = 1`.
- `kernel.apparmor_restrict_unprivileged_userns = 1`.
- `user.max_user_namespaces = 255146`.

These are observations, not a capability test or proof that the probe can run.
Local logs: `/tmp/labloop-host-probe.rpqgok/` (`stdout.log`, `stderr.log`, `exit-code`).

## Gate and next decision

Attempted the prescribed gate request:

```text
tools/lab gate request --type isolation --question \
  "Fixed host-isolation probe failed closed. Approve diagnosis of host prerequisites without weakening sandbox protections?"

lab: error: state.json not found — run `lab init` first
```

**No gate was persisted.** This is an ad-hoc development repository without initialized
project state. Do not initialize/move the research state machine merely to record a
development permission request. This document records the blocker without pretending
the gate command succeeded.

Required operator decision: authorize bounded diagnosis of the failed prerequisite,
keeping raw diagnostic artifacts private and all existing isolation/resource protections
unchanged. Actual OS policy/provisioning changes require a separate explicit decision;
no approval to weaken the sandbox, access accounts or launch live research is implied.

Live dispatch stays disabled. Official identity-schema/account/billing assurance,
credential/evaluator authority separation and durable whole-enforcer supervision remain
open independently of this failure. See [PLAN.md](PLAN.md) and [preflight.md](preflight.md).
