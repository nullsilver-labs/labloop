# Lifecycle smoke audit — 2026-09-12

Campaign: `../labloop-m2-lifecycle-smoke-20260912`. Read its immutable `SMOKE.md`, `campaign.toml`, `snapshot.json`, `REPORT.md`, `population.json`, and candidate/watch artifacts. The snapshot used reviewed, uncommitted shared tooling; hashes include the new process helper. Historical campaign evidence was not changed.

## Results

- **Observed core lifecycle success:** baseline and both learned attempts completed with exit 0; no invalid, killed, deferred or failed candidates. Search accuracies .091/.7632/.7782 (n=5000). Both learned transcripts contain synchronous training results before summaries and end_turn, with no background or nested-watch calls. Wrapper logs say `contract met`.
- **Strict preregistered protocol failed:** SMOKE.md promised a five-minute final-execution cap. The operator mistakenly set `[eval].timeout`, which caps scoring. The final watcher instead inherited `job_wall_clock=15m`. Its actual 15-second execution does not repair this configuration mismatch. Neither config nor preregistration was retroactively changed.
- **Task accuracy not_supported:** final .7723 < fixed .90, n=10000. The final log records candidate-local weights loaded without retraining. One final watcher, one final fitness entry and one population final entry were observed; not an independent lifetime trace.
- All five watcher records are done/0 without cleanup errors; outer campaign watcher ended 14:09:17Z. Foreground learned jobs lasted 121s and 90s. Search prediction and summary mtimes precede job completion and scoring.
- Post-settlement process snapshots at 14:10:26 and 14:10:56 found only auditor processes matching the campaign; all ten recorded watcher/child PIDs were absent by 14:11:20. No GPU compute applications were reported. All 27 candidate files retained identical sizes, nanosecond mtimes and hashes across a 30-second window.

## Accounting and limits

Recorded search/candidate accounting: 226 GPU-seconds (.06278 hours), including baseline, excluding the final watch's 15 seconds. Including that final lease gives 241 seconds (.06694 hours). These are lease/wall intervals, not measured CUDA utilization. Wall to outer termination: 285 seconds. Agent usage: $0.5596814 list-price equivalent, 21 turns. Requested/served main model Sonnet-5; CLI 2.1.269; modelUsage also includes Haiku-4.5. No usage deferrals; governor uncalibrated and detection-only.

Process observations are snapshots, not birth-to-death tracing; some /proc entries were inaccessible (including six same-UID entries in the narrower scan). No exhaustive absence claim for escaped/reidentified inaccessible processes or writes outside the observation interval. Hooks are shallow guardrails; Linux containment is not hostile-user isolation. Data splits and environment were reused; labels were hidden by convention. This is not new generalization, comparative effectiveness, long-run reliability, or governor validation.

The tiny smoke trained each model for about ten seconds, so it does not prove long-running foreground behavior beyond the synthetic tests. For a strict follow-up smoke, include training lasting beyond the CLI's previous auto-background interval, not merely two short successful sessions.

## Other observed documentation deviations

Preserve rather than repair candidate evidence:

- c0001 summary claims peak validation epoch9=.773; transcript training output instead has epoch14=.7796.
- c0002 summary claims epoch13=.783; output shows .7789, and its gap comparison is arithmetically inconsistent.
- c0001 ran foreground search inference twice, though the job card says once; only the first invocation trained.

## Next action

Do not launch a full comparison yet. Define final execution cap and search/final resource accounting accurately before launch. A strict smoke pass requires a new preregistered identity, not a repaired historical record. Preserve original M2 thresholds and equal-resource comparison criteria. Fresh matched search/control runs must share repaired tools, data, models, seeds, budgets, memory and usage settings, differing only in selection.

The shared final synthetic suite passed 388 checks, with nine real-process lifecycle tests. Independent review found and the parent/worker corrected guard false positives for heredoc payloads, quoted prose and multiline quoted Python; the final focused/full suites passed again before the smoke snapshot.

## Follow-up sustained smoke — interrupted, not a pass

Fresh identity `../labloop-m2-lifecycle-smoke-long-20260912`, launched 14:19:35Z. Its frozen protocol correctly states job/final 15-minute caps, scorer five minutes, dispatch 35 minutes, outer 60 minutes, and an outer ten-minute stall check. That last operator setting proved unsuitable: controller state-file progress and detached candidate watcher logs/CPU do not advance the outer log/session CPU signal. Outer watcher `20260912T1419-campaign` killed the controller for stall at 14:29:37Z, despite active candidate progress. This was not wall-budget expiry. For this topology retain wall enforcement but omit outer idle-stall checks until they measure actual campaign progress. Candidate-specific deadlines remain necessary.

Both learned jobs genuinely trained in the foreground: c0001 200.005407s/21489 optimizer steps, c0002 200.008592s/21831 steps; each command envelope about 203.5s. Code and loss/step logs support real fresh optimizer work, not sleep or invented timing. Distinct weights and initial inherited-code listings support no inherited trained model. Both tools returned before end_turn. All three job watchers ended done/0 without cleanup errors. Baseline and c0001 settled (.091/.849 search); c0002 completed at 14:29:46Z but is stranded unscored in population because the controller had died. No final watcher, final score or REPORT exists. Stop was requested at 14:30:03Z, after c0002 completed; it did not kill that training.

Two scoped process snapshots at 14:31:06 and 14:31:37 found no training/controller process or GPU compute application. All 28 candidate files had stable size, mtime and SHA256 for 31 seconds. These are bounded snapshots, not exhaustive tracing, and c0002 is not settled. All 20 frozen manifest hashes matched. Source tools/hooks matched the previous tested smoke.

Recorded settled candidate lease time is 300s; completed but unbooked c0002 adds 300s. Observed total 600s=.166667h, final zero because not run; neither is CUDA utilization. Agent usage $0.560563 list-price equivalent, 29 turns. CLI 2.1.269, main served Sonnet-5; governor detection-only, no rate limits. Threshold claim remains untested; c0002's .867 is training holdout, not search accuracy.

Additional strict deviations: no explicit CUDA synchronization before either training timer starts (both synchronize elapsed checks/end); bounded Bash tool timeouts were used but the separately requested shell timeout was omitted. c0002 summary overstates explicit exit-status checking and unchanged holdout membership and omits an earlier harmless missing-python attempt. Preserve these findings, not repaired summaries. None negates the strong evidence of sustained foreground optimizer work, but do not claim full protocol compliance.

**Disposition: INCONCLUSIVE overall**, with positive sustained-execution evidence and a demonstrated false outer-stall failure. No automatic restart or comparison. The existing stop marker prevents new dispatch on a future resume, but `lab run --once` is not settlement-only: it reaps/evaluates c0002 then starts the first final before exiting. Any recovery needs explicit approval for evaluation and must remain labeled post-interruption recovery, never retroactive smoke PASS. No final has yet been read in this campaign. A broader atomic final-evaluation crash window remains outside this smoke's validation.

### Authorized recovery (14:37 UTC)

The user approved recovery with the existing stop marker. A new wall-clock-only
watcher `20260912T1437-recovery` (30-minute budget, stall 0) ran the unchanged
campaign, settling c0002 at 14:37:09Z and dispatching no new candidates or worker
sessions. Its first final execution loaded the original local weights without
retraining; final scored .8644 at 14:37:29Z, below .90. Recovery ended done/0 at
14:37:39Z. Three completed candidates now have search scores .091/.849/.8676;
REPORT exists. This is successful authorized recovery, not retroactive strict PASS.

Search lease accounting now books all 600s; final lease adds 15s, combined
615s=.170833h. Agent usage remains $0.560563. Original killed watcher, stop marker,
and all frozen manifest entries remain unchanged. Two post-recovery snapshots
31 seconds apart found all 30 candidate files stable and no visible candidate
processes. Access/snapshot limitations still apply. One final is present in the
recorded history, not proof of atomic final scoring under every crash.

The automated REPORT labels the upper middle turn count (19 for [10,19]) as
median; the conventional arithmetic median is 14.5. Preserve the report rather
than correcting generated historical evidence.

## Wall-only confirmation — lifecycle PASS (14:59 UTC)

Fresh `../labloop-m2-lifecycle-smoke-wall-20260912` completed uninterrupted.
Baseline plus two learned candidates settled with exit 0, no invalids, retries,
recovery or operator intervention. Controller runtime 911s; outer watcher done/0
at 14:59:05Z, beyond the former ten-minute stall point. Every job/final watcher
also ended done/0. Outer wall60min/stall0, job/final15min, scorer5min and job stall5min
matched the frozen protocol. Final wall lease had no stall threshold.

Actual fresh training: c0001 310.000733s / 45,710 steps, c0002 310.003602s /
41,841 steps. CUDA synchronized at start/end; code/logs and ~313.6s foreground
command envelopes support real optimizer work, not sleep or fake timers. Both
explicit Bash timeouts were480000ms; single search invocation per candidate,
successful tool results then artifact checks/summary before end_turn/settlement.
Extra shell timeout was optional in this preregistration. Different local weights,
source-only inheritance and fresh branches support no trained-weight reuse.

Search scores .091/.8564/.8958 (n5000); final .8914 (n10000), below .90, so task
claim `not_supported`. Exactly one recorded final loaded existing weights without
retraining. Search leases871s, final15s, combined886s=.246111h, not utilization.
Agent usage $0.6514438, 29 turns, served main Sonnet-5 and CLI2.1.269; detection-only
uncalibrated governor. Reused data remains unsuitable for fresh generalization claims.

All19 frozen manifest entries matched. At least31s post-settlement snapshots found
candidate/controller artifacts stable and no visible surviving training process;
GPU query was empty. Inaccessible/racing process entries mean this is not exhaustive
kernel tracing. Candidate provenance says no-git: exact dirty snapshot hashes,
not a committed release or full environment lock.

Reporting caveats preserved: c0001's summary omits a harmless guard denial for
training-label inspection; both summaries call a five-convolution network six-conv.
Successful tool results support exit success independently of misleading file-presence
check labels. Seed-dependent validation slices preclude treating c0002 as a controlled
augmentation ablation. Baseline reuses a historical interpreter path, not candidate
code/weights. REPORT's upper-middle turn count17 differs from arithmetic median14.5.
These defects do not negate the directly observed lifecycle criteria; summaries are
not sufficient evidence on their own. No policy/full-window/isolation claim follows.

User authorized fresh full matched comparisons after this pass. A capped pair is
in preflight; no new comparative run has launched at this writing.
