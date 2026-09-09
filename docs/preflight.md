# Authentication and OS-isolation feasibility (no live release)

This is the bounded second slice, after the deterministic demo and local resource
foundation. It adds **no worker, provider inference, dispatch, account allowance,
publication, or new scheduling authority**. The tiny demo remains the starting point.

## Evidence and authority

| Safety field | Classification | What this slice establishes |
| --- | --- | --- |
| Live eligibility | Enforced | Always false, including after an attestation or probe |
| Account inspection | Enforced | Explicit opt-in; static status reads no account/config files |
| Binary contract | Enforced | Native Linux ELF, absolute resolved path, operator-approved SHA-256, exact `2.1.263 (Claude Code)` version output; no PATH wrapper |
| Official binary provenance | Observed, publisher signature verified for exact artifact | Parent independently verified the 2.1.263 linux-x64 signed manifest and installed binary hash/size at 2026-09-06T18:52:08Z; not an automatic runtime GPG check |
| Authentication identity | Unsupported | Official status output can be collected privately, but its JSON identity schema is not established; inventory aliases never become verified identities |
| Provider settings/env exclusion | Enforced, conservatively | Conflicting variable presence denies; nonempty settings/opaque sources deny; clean subprocess environment and fixed command |
| Billing controls | Operator-attested only, offline structure | Explicit dated identity/config/version-bound declaration, **not provider verification or proof of zero-spend** |
| Vendor remaining allowance | Unknown | Never inferred from local slices, CLI presence, login or attestation |
| OS boundary | Host unverified | Offline fixtures pass; subsequent real probe failed closed with no isolation evidence; see [host attempt](host-isolation.md) |
| Session/account exclusivity | Local foundation only | Labloop-managed sessions sharing one ledger, not all users/devices/account activity |

All account/status/billing evidence belongs outside the repository in an existing
operator-owned 0700 directory, new files 0600. Evidence is never overwritten or
exported. Raw output and error diagnostics are not printed. Private path checks
are hygiene, **not protection against an adversarial process with the same UID**.
Do not give candidates the harness OS identity, inventory or ledger.

## Pinned Claude contract and actual observations

Safe help/version inspection in an empty temporary working directory with a clean
environment observed:

- Native installed path: `/home/marco/.local/share/claude/versions/2.1.263`.
- `--version`: `2.1.263 (Claude Code)`.
- SHA-256 of that observed local binary:
  `26d020351e8112f4006790f3cfce43b4c9df0c1bb1d0e542364d64151b81d5ba`.
- `auth --help`: `status` is “Show authentication status”.
- `auth status --help`: `--json` is supported and default.
- Root help documents `--setting-sources`, `--settings`, `--strict-mcp-config`
  and `--mcp-config`. `--bare` explicitly excludes OAuth/keychain and requires
  API-key/helper auth; **it is not used as a subscription safety switch**.

The help/version observations alone were not publisher authentication. A subsequent
read-only publisher-signature verification by the parent is recorded below, scoped
to this exact installed binary and observation time. Runtime preflight still checks
an operator-approved digest/version, **not automatic GPG validation**. No binary was
installed or downloaded, and version drift fails closed. The status invocation with
all global isolation options is **not exercised against a real account**.

A bounded public GET of `https://code.claude.com/docs/en/cli-reference.md` returned
HTTP 403; no credentialed/alternate-access retry was made. Help does not establish
JSON identity fields. Per the approved feasibility decision, **there is no
speculative official-identity parser**. Native OAuth/no API key cannot establish
subscription billing: [official authentication documentation](https://code.claude.com/docs/en/authentication#sign-in-without-an-api-key)
also supports keyless Console OAuth from v2.1.242, and profiles/federation/gateway
precedence need effective-route verification. No guessed identity fields or parser
are added. Actual `auth status` was never invoked; only its `--help` was. No actual
credentials/settings/account inventory were read.

### Public research conclusions and scoped publisher verification

The parent's managed `remaining/auth-research.md` records official public research,
not a supported identity schema or account observation. Its source-backed conclusions:

- The [official CLI reference](https://code.claude.com/docs/en/cli-reference) describes
  JSON status and login exit codes (search-index evidence); the official
  [changelog snapshot](https://github.com/anthropics/claude-code/blob/a3d9426e3e183d1fdc560fcc8a69e9d854f040c9/CHANGELOG.md)
  records auth subcommands in 2.1.41. Neither establishes JSON identity property
  names/types, effective-account semantics or exact-2.1.263 schema compatibility.
  Identity remains **unsupported**, never guessed from a sample or interactive `/status`.
- [Official authentication docs](https://code.claude.com/docs/en/authentication)
  explicitly support Console OAuth with **no API key** since 2.1.242. Named profiles,
  federation and gateways create additional effective-routing risks; not every
  precedence detail has a version bound. Login-method/organization settings alone
  are not proof of subscription routing or the resulting Console organization.
- [Personal-plan usage-credit controls](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans)
  cover Pro/Max and both Claude and Claude Code; Settings > Usage can disable paid
  usage credits. This is not a Team/Enterprise assurance. Existing paid credits and
  auto-reload are distinct spending paths; disabling replenishment alone is insufficient.
- [Console billing documentation](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage)
  separately describes credits, auto-reload and invoiced organizations. Research did
  **not establish** a supported non-inference API/CLI read of current overage and
  auto-reload settings; that is not proof none exists. Correct-account UI inspection
  and an expiring bound declaration remain **Operator-attested**, not provider proof
  of zero spend, current identity or remaining allowance.
- [Official installation documentation](https://code.claude.com/docs/en/installation#binary-integrity-and-code-signing)
  specifies a signed SHA-256 manifest for native Linux (binaries are not individually
  signed). The [official setup page](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing)
  states signatures are available from 2.1.89 (targeted search-index evidence).
  Current mutable docs are not themselves an exact-version runtime certificate.

**Observed provenance check complete for this exact artifact:** at
**2026-09-06T18:52:08Z**, the parent independently matched the published signing
fingerprint `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`, verified the detached signature
with isolated GPG, and matched the installed **2.1.263 linux-x64** binary's hash and
size to the authenticated manifest:

- Binary SHA-256: `26d020351e8112f4006790f3cfce43b4c9df0c1bb1d0e542364d64151b81d5ba`.
- Binary size: **215662064 bytes**.
- Manifest SHA-256: `96f64bb75b98b1ca93008826a2028cb8b7d0f41727cdf188cf316a275328116a`.
- Trust anchor: fingerprint published in [official installation docs](https://code.claude.com/docs/en/installation).
  Public assets: [key](https://downloads.claude.ai/keys/claude-code.asc),
  [exact manifest](https://downloads.claude.ai/claude-code-releases/2.1.263/manifest.json),
  [detached signature](https://downloads.claude.ai/claude-code-releases/2.1.263/manifest.json.sig).

Only these public assets were downloaded (under 5 KiB total); GPG used an isolated
temporary homedir with `--no-options`, `--no-autostart` and `--no-auto-key-retrieve`.
There was no CLI execution, account/credential access, installation or host
configuration. Durable parent evidence is in the managed artifact directory
`remaining/provenance-2.1.263/` (`verification.json`, manifest/signature/key, fetch URLs
and GPG logs), alongside `remaining/auth-research.md` and the implementation report.
This observation neither automatically authenticates future binary changes nor
changes runtime preflight's digest-only contract. Identity schema, billing/routing,
host isolation and live release remain blocked; eligibility is still false.

## Default and opt-in interfaces

Safe defaults, with no account inspection or namespace creation:

```sh
tools/lab preflight status
tools/lab sandbox plan
python3 scripts/test_preflight.py
python3 scripts/test_sandbox.py
```

`preflight inspect-account` requires **all** of `--operator-inspect-account`,
`--inventory`, `--policy`, `--binary`, `--binary-sha256`, `--native-home`, and
`--evidence`. Do not run it without explicit account-inspection authorization.
It does not authorize spending or inference. No live dispatch command exists.

Inspection first rejects conflicting environment names (including empty/false
values), settings in user/project/ancestor/local and Linux managed locations,
helpers/hooks/provider environment overrides, symlinks and malformed JSON. For
this small slice, **every nonempty settings object is denied**, not just known paid
fields. `~/.claude.json` and `managed-settings.d` are opaque and denied by presence,
never opened: they may contain sensitive/unsupported configuration. This can
refuse ordinary installations. Do not delete/move configuration or credentials to
work around a refusal; additional supported configuration shapes need review.
Python never opens `.credentials.json` or tries to identify subscriptions from it.

The exact non-inference command contract is:

```text
ABSOLUTE_APPROVED_ELF --setting-sources '' --settings '{"disableAllHooks":true}' \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' auth status --json
```

Only explicit native HOME, fixed PATH/LANG and updater/nonessential-traffic-disable
settings reach the subprocess. The working directory is a new private empty temp
directory, stdin is closed, inherited FDs are closed, output is limited to 64 KiB,
wall time to 10 seconds per command. CPU/address-space/file-size/FD/process rlimits
are conservative feasibility bounds; they may reject this CLI on a host (notably
native runtime address-space reservation). **No weakened retry/fallback** exists.
The trusted-tool helper requires the single-threaded Linux main thread. On
completion, timeout, output/error failure, or ordinary SIGTERM/SIGINT/SIGHUP, it
kills the child's process group and reaps the direct child. Signal handlers record
termination during `Popen` construction instead of losing the cleanup handle;
termination is checked at bounded polling intervals after construction, including
when output pipes have closed. Previous handlers are restored after cleanup.

Before exec, Linux `PR_SET_PDEATHSIG(SIGKILL)` arms direct-child termination if the
supervisor dies abruptly. Comparing the parent PID with the supervisor PID captured
**before fork** closes the parent-dies-before-registration race. Setup failure
denies execution. This is **not whole-tree crash enforcement**: PDEATHSIG is not
inherited across fork, can be cleared by credential-changing exec or the trusted
tool itself, and does not kill compiler/tool grandchildren when the supervisor is
SIGKILLed or crashes. A process leaving the original group also escapes ordinary
group cleanup. Surviving grandchildren are not claimed to be reaped by this helper.
A kernel-stuck preexec/child or malicious tool is outside its bounded trusted-tool
assumption. Full crash-safe descendant ownership needs a separately approved
supervisor/cgroup design before live workers; no general worker runner is added.

Settings/binary snapshots are rechecked after inspection. Successful collection
stores bounded uninterpreted raw status privately, a configuration/mission hash,
binary contract, native-home/settings context hash and a five-minute expiry. The
validator rejects stale, future, conflicting or falsely “verified” observations.
Even fresh evidence returns unsupported identity and false live eligibility.
Same-user file races, remote account changes, provider routing behavior and actual
hook/helper exclusion under this CLI remain **unproven**, not release guarantees.

## Billing attestation seam

No supported official non-inference command for verifying account-side overage or
auto-replenishment has been established. The module therefore offers only an
offline structural validator, not an attestation that silently enables accounts.
There is no default attestation, allowance estimate or real-account attestation
created in this work. Unknown identity cannot be cleared with a declaration.

`validate_attestation` accepts exactly:

- `schema_version: 1`, `kind: operator_attestation_not_provider_verification`;
- `overage_disabled: true` and `auto_replenishment_disabled: true` explicitly;
- integer `issued_at` and `expires_at`, currently valid, at most 24 hours apart;
- an exact binding containing `declared_identity_sha256`, `authorization_hash`,
  `binary_sha256`, `cli_version`, `context_hash`, `status_evidence_sha256`.

The declared identity is explicitly **operator-declared, not CLI/provider-verified**.
Any changed identity, policy/mission/inventory, binary/version, environment/settings
context or evidence invalidates the matching binding. Output is classified
operator-attested, provider verification false, identity verification false, live
eligibility false. This validates a declaration's structure and freshness, **not
its truth, tamper resistance or continuing account-side configuration**. Operator
ownership/signing and real identity acquisition remain future integration work.

## Fixed Linux probe: no arbitrary worker runner

`sandbox probe --operator-run-host-probe --evidence NEW_PRIVATE_PATH` is the explicit
host-probe entry point. It was not run during implementation. A subsequent operator-directed
attempt **failed closed**, with the failed stage unknown; see [host-isolation.md](host-isolation.md).
Further diagnosis is awaiting authorization; do not weaken or retry around the refusal.
It uses existing root-owned non-setuid `/usr/bin/cc` and `/usr/bin/bwrap`; no install,
root/sudo, OS configuration changes, broad host mounts or unshare/host fallback.
Missing static toolchain, unsupported flags or denied namespaces are a refusal.

Only the bundled fixed `tools/labloop_probe.c` is compiled statically. There is no
source/binary/command override or user workload input. The child sees just a
read-only probe ELF, read-only otherwise-empty root, new procfs and private writable
`/tmp`. It does not mount host `/usr`, `/lib`, `/etc`, `/dev`, home, repo, credentials,
evaluator or authoritative state. All user/pid/net/ipc/uts/cgroup namespaces are
required, capabilities dropped, nested user namespaces disabled, environment empty,
inherited FDs closed. User namespaces/kernel security remain part of the TCB.

The fixed probe first requires different mount/network/PID namespaces, before
attempting adversarial I/O. It checks missing credential/evaluator/state paths,
proc-root and symlink escapes, read/write denial, empty environment, FDs, UID/GID,
visible processes, and fresh network namespace interfaces plus unreachable
loopback/external documentation-range addresses. Writable `/tmp` is a positive
control. Only an exact all-true packet with exit zero is accepted. The temporary
host secret is synthetic and never mounted. A pass is scoped to this fixed probe,
source/binary/kernel observation, not arbitrary candidates or an enduring host
certification. No mechanism consumes it to enable dispatch.

## Validation and remaining blockers

- New suites: **22 preflight tests, 6 sandbox tests**, all passed.
- Existing foundation suites: **23 resource tests, 11 discovery tests**, all passed.
- Python compilation, C syntax/warnings check and `git diff --check` passed.
- Actual host execution tested only bounded synthetic Python subprocesses:
  environment/FD exclusion, timeout, excessive output, diagnostic/nonzero failure,
  descendants holding a pipe after parent exit, ordinary supervisor termination
  (SIGTERM/SIGINT/SIGHUP, with open and closed output pipes), termination during
  `Popen`, abrupt SIGKILL after exec, and parent death before PDEATHSIG registration.
  Termination/race tests use real synthetic processes, process-local subreaper
  adoption/reaping and pidfds for exit evidence and cleanup. The pre-registration
  race inserts a test-only pause; actual PDEATHSIG and parent-PID checks run unmocked.
  These tests establish direct-child behavior, **not whole-tree crash cleanup**.
  The older descendant-timeout test mocks only
  `RLIMIT_NPROC` because that limit counts unrelated same-UID host processes; the
  production ceiling stays unchanged and may deny tools on a busy host. No provider
  operation involved. An intermediate test run failed on fixture file permissions
  and this host-dependent process limit; fixtures were corrected, not production
  safety limits relaxed.
- Auth output and identity/billing bindings are synthetic/mocked. Sandbox namespace,
  filesystem/process/network denial packets and argument checks are offline fixtures,
  **not tested host OS isolation**. C compiled for syntax only, not executed.
- New suites are wired into `scripts/acceptance.sh`. The legacy aggregate was not
  rerun in this slice; its prior **10 provenance failures** remain documented in
  `docs/resources.md`/`docs/discovery.md`. No unrelated legacy fix or suppression.

Live blockers: fresh provenance for any changed binary (the exact observation above
is complete, not automatic runtime verification) and supported identity schema; actual native auth
and paid-route exclusion; account-side billing assurance (attestation alone cannot
prove zero spending); approved host adversarial isolation test and operator-only
OS ownership; candidate/evaluator integrity and sealed data; bounded live session
adapter; actual multidimensional resource enforcement; trusted account-pool process identity,
exit verification and whole-tree supervision. Strict fresh-v2 local packets and
cooperative lease/fencing/reconciliation are now tested offline (see resources),
not proof of these real live gates. Recovery must not rely
on a final worker response. Existing SQLite reservations and leases cover only Labloop-managed
local scheduling, never account-wide vendor exclusivity or capacity. Publication
and downstream format migration remain separately gated. No live release claim.
