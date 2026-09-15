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
//   2. a continuation when a response is cut at the output token limit (Pi ends the
//      run on stopReason "length"; up to LAB_LENGTH_NUDGES follow-ups, default 2).
//   3. the evidence guard — the same .claude/hooks/guard.sh Claude Code runs as a
//      PreToolUse hook, fed the same JSON it expects (tool_name Bash/Write/Edit,
//      tool_input, cwd). Exit 2 blocks the call with the guard's message. One guard,
//      two harnesses. Reads of the hidden labels are refused here as well.
//
// Tool results are clipped to LAB_TOOL_RESULT_MAX_CHARS (16000) so a log dump cannot
// overflow a small context in one step. Bash calls get a timeout inside the remaining job
// budget when the model gave none;
// the watcher stays the wall-clock authority. Pi has no background execution of its
// own, and lab_process.py contains whatever a command detaches.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const LABELS_RE = /LAB_PRIVATE|labels\.json|\/labels(?:\/|$)/;
const WARN_TURNS = 5;
// Every tool result is clipped to this many characters (head and tail kept). An open
// model on a 32k context has no room for a 50 KB training log or a file dump: the first
// probe lost two sessions to a 40k-token request after their work was done. Claude Code
// does its own clipping; Pi's is per tool and generous.
const RESULT_MAX = Math.max(2000, parseInt(process.env.LAB_TOOL_RESULT_MAX_CHARS || "16000", 10) || 16000);

export default function (pi) {
  const env = process.env;
  const maxTurns = Math.max(1, parseInt(env.LAB_WORKER_MAX_TURNS || "40", 10) || 40);
  const wallSec = Math.max(1, parseInt(env.LAB_JOB_WALL_CLOCK_SEC || "600", 10) || 600);
  const startedAt = Date.now();
  const cwd = process.cwd();
  const guard = env.LAB_GUARD || path.join(cwd, ".claude", "hooks", "guard.sh");
  const haveGuard = existsSync(guard);
  let turns = 0;
  let lastStop = null;
  let nudges = 0;
  // A response cut at the output token limit ends a Pi run (stopReason "length");
  // Claude Code continues past its own. Up to this many times the session is nudged
  // on with a follow-up message instead of ending with the work undone.
  const MAX_NUDGES = Math.max(0, parseInt(env.LAB_LENGTH_NUDGES || "2", 10) || 0);

  const remainingSec = () => Math.max(1, Math.floor(wallSec - (Date.now() - startedAt) / 1000));

  const runGuard = (toolName, toolInput) => {
    if (!haveGuard) return null;
    const payload = JSON.stringify({ tool_name: toolName, tool_input: toolInput, cwd });
    const r = spawnSync("bash", [guard], { input: payload, env, encoding: "utf8", timeout: 20000 });
    if (r.status === 2) return (r.stderr || "blocked by the evidence guard").trim();
    return null;
  };

  pi.on("turn_start", () => { turns += 1; });

  pi.on("message_end", (event) => {
    const m = event.message;
    if (m && m.role === "assistant") lastStop = m.stopReason || null;
    return undefined;
  });

  pi.on("agent_end", () => {
    if (lastStop !== "length" || turns >= maxTurns || nudges >= MAX_NUDGES) return undefined;
    nudges += 1;
    pi.sendMessage({
      customType: "lab-nudge", display: true,
      content: `[lab] Your last response was cut off at the output token limit (continuation ${nudges} of ${MAX_NUDGES}). ` +
               `Do not repeat it. Continue in short steps: small tool calls, brief reasoning, no long file dumps. ` +
               `Run code/run.sh, check the predictions, write summary.md, then stop.`,
    }, { deliverAs: "followUp", triggerTurn: true });
    return undefined;
  });

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
    let content = Array.isArray(event.content) ? [...event.content] : [];
    let changed = false;
    content = content.map((b) => {
      if (!b || b.type !== "text" || typeof b.text !== "string" || b.text.length <= RESULT_MAX) return b;
      changed = true;
      const head = Math.floor(RESULT_MAX * 0.6), tail = RESULT_MAX - head;
      const cut = b.text.length - RESULT_MAX;
      return { ...b, text: b.text.slice(0, head) +
        `\n\n[lab] ${cut} characters elided from the middle of this tool result to keep the session inside ` +
        `the model's context; narrow the command (head, tail, grep) if you need them.\n\n` + b.text.slice(-tail) };
    });
    const left = maxTurns - turns;
    if (left <= WARN_TURNS && left >= 0) {
      const note = left > 0
        ? `\n\n[lab] ${left} turn${left === 1 ? "" : "s"} of ${maxTurns} left and ${remainingSec()} s of wall clock: ` +
          `write summary.md now if it is not written, then stop.`
        : `\n\n[lab] this was the last turn of ${maxTurns}: write summary.md and stop; further tool calls are refused.`;
      content.push({ type: "text", text: note });
      changed = true;
    }
    return changed ? { content } : undefined;
  });
}
