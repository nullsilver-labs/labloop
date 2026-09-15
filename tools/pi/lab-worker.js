// lab-worker.js — the Pi extension a campaign worker session runs with.
//
// Loaded explicitly by tools/lab-worker-pi (`pi -e tools/pi/lab-worker.js`); never
// auto-discovered, so an operator's own Pi sessions are untouched. It gives a Pi
// session the two things `claude -p` gets from flags and hooks:
//
//   1. a turn budget — Pi has no --max-turns. Past LAB_WORKER_MAX_TURNS every tool
//      call is blocked with a terminating reason, which ends the agent run; from five
//      turns before that, every tool result carries a countdown so the model writes
//      summary.md in time.
//   2. the evidence guard — the same .claude/hooks/guard.sh Claude Code runs as a
//      PreToolUse hook, fed the same JSON it expects (tool_name Bash/Write/Edit,
//      tool_input, cwd). Exit 2 blocks the call with the guard's message. One guard,
//      two harnesses. Reads of the hidden labels are refused here as well.
//
// Bash calls get a timeout inside the remaining job budget when the model gave none;
// the watcher stays the wall-clock authority. Pi has no background execution of its
// own, and lab_process.py contains whatever a command detaches.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const LABELS_RE = /LAB_PRIVATE|labels\.json|\/labels(?:\/|$)/;
const WARN_TURNS = 5;

export default function (pi) {
  const env = process.env;
  const maxTurns = Math.max(1, parseInt(env.LAB_WORKER_MAX_TURNS || "40", 10) || 40);
  const wallSec = Math.max(1, parseInt(env.LAB_JOB_WALL_CLOCK_SEC || "600", 10) || 600);
  const startedAt = Date.now();
  const cwd = process.cwd();
  const guard = env.LAB_GUARD || path.join(cwd, ".claude", "hooks", "guard.sh");
  const haveGuard = existsSync(guard);
  let turns = 0;

  const remainingSec = () => Math.max(1, Math.floor(wallSec - (Date.now() - startedAt) / 1000));

  const runGuard = (toolName, toolInput) => {
    if (!haveGuard) return null;
    const payload = JSON.stringify({ tool_name: toolName, tool_input: toolInput, cwd });
    const r = spawnSync("bash", [guard], { input: payload, env, encoding: "utf8", timeout: 20000 });
    if (r.status === 2) return (r.stderr || "blocked by the evidence guard").trim();
    return null;
  };

  pi.on("turn_start", () => { turns += 1; });

  pi.on("tool_call", (event) => {
    if (turns > maxTurns) {
      return {
        block: true, terminate: true,
        reason: `lab: turn budget of ${maxTurns} turns reached; the session ends here. ` +
                `Whatever exists in the candidate dir is what gets evaluated.`,
      };
    }
    const input = event.input || {};
    let reason = null;
    if (event.toolName === "bash") {
      const t = Number(input.timeout);
      if (!Number.isFinite(t) || t <= 0 || t > remainingSec()) input.timeout = remainingSec();
      reason = runGuard("Bash", { command: String(input.command || ""), timeout: input.timeout });
    } else if (event.toolName === "write" || event.toolName === "edit") {
      const p = String(input.path || "");
      if (LABELS_RE.test(p)) reason = "a worker never touches labels; fitness comes from `lab eval`";
      else reason = runGuard(event.toolName === "write" ? "Write" : "Edit", { file_path: p });
    } else if (["read", "grep", "find", "ls"].includes(event.toolName)) {
      const p = String(input.path || input.pattern || "");
      if (LABELS_RE.test(p) || LABELS_RE.test(String(input.glob || "")))
        reason = "a worker never reads labels; fitness comes from `lab eval`, the only reader of the splits";
    }
    if (reason) return { block: true, reason };
    return undefined;
  });

  pi.on("tool_result", (event) => {
    const left = maxTurns - turns;
    if (left > WARN_TURNS || left < 0) return undefined;
    const note = left > 0
      ? `\n\n[lab] ${left} turn${left === 1 ? "" : "s"} of ${maxTurns} left and ${remainingSec()} s of wall clock: ` +
        `write summary.md now if it is not written, then stop.`
      : `\n\n[lab] this was the last turn of ${maxTurns}: write summary.md and stop; further tool calls are refused.`;
    const content = Array.isArray(event.content) ? [...event.content] : [];
    content.push({ type: "text", text: note });
    return { content };
  });
}
