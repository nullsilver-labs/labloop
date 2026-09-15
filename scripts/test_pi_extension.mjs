#!/usr/bin/env node
// No LLM: loads tools/pi/lab-worker.js with a stub ExtensionAPI, fires the events Pi
// would, and checks the turn budget, the guard bridge and the label refusal. Run from
// the repo root (the guard is .claude/hooks/guard.sh there). Exit 1 on any failure.
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
process.chdir(SRC);
process.env.LAB_ROLE = "worker";
process.env.LAB_WORKER_MAX_TURNS = "3";
process.env.LAB_JOB_WALL_CLOCK_SEC = "100";
process.env.LAB_CANDIDATE_DIR = path.join(SRC, "candidates", "c0001");
process.env.LAB_GUARD = path.join(SRC, ".claude", "hooks", "guard.sh");

const { default: ext } = await import(path.join(SRC, "tools", "pi", "lab-worker.js"));
const handlers = {};
ext({ on: (name, fn) => (handlers[name] ??= []).push(fn) });
const fire = async (name, event) => {
  let out;
  for (const h of handlers[name] || []) out = (await h(event, {})) ?? out;
  return out;
};
let failed = 0;
const check = (desc, cond, extra = "") => {
  console.log(`  ${cond ? "ok  " : "FAIL"} ${desc}${cond ? "" : "  " + extra}`);
  if (!cond) failed += 1;
};
const call = (toolName, input) => fire("tool_call", { toolName, toolCallId: "t", input });

await fire("turn_start", { turnIndex: 0 });
let r = await call("bash", { command: "ls" });
check("a plain bash call passes", r === undefined, JSON.stringify(r));
const inp = { command: "sleep 1" };
await call("bash", inp);
check("a bash call without a timeout gets one inside the job budget", inp.timeout > 0 && inp.timeout <= 100, String(inp.timeout));
const inp2 = { command: "sleep 1", timeout: 5000 };
await call("bash", inp2);
check("a bash timeout above the remaining budget is clamped", inp2.timeout <= 100, String(inp2.timeout));
r = await call("bash", { command: "rm -rf events.jsonl" });
check("the guard blocks deleting evidence", r?.block === true && /evidence/.test(r.reason), JSON.stringify(r));
r = await call("bash", { command: "rm -rf candidates/c0000" });
check("the guard blocks touching another candidate", r?.block === true && /another candidate/.test(r.reason), JSON.stringify(r));
r = await call("bash", { command: "nohup python train.py &" });
check("the guard blocks a detached run", r?.block === true && /foreground/.test(r.reason), JSON.stringify(r));
r = await call("bash", { command: "cat $LAB_PRIVATE/m/labels.json" });
check("the guard blocks a look for labels", r?.block === true && /labels/.test(r.reason), JSON.stringify(r));
r = await call("read", { path: "data/search/labels.json" });
check("a read of labels is refused", r?.block === true && /labels/.test(r.reason), JSON.stringify(r));
r = await call("grep", { pattern: "x", path: "/private/labels/" });
check("a grep under a labels dir is refused", r?.block === true, JSON.stringify(r));
r = await call("write", { path: "candidates/c0002/summary.md", content: "x" });
check("a write into another candidate's dir is blocked", r?.block === true && /another candidate/.test(r.reason), JSON.stringify(r));
r = await call("write", { path: "candidates/c0001/summary.md", content: "x" });
check("a write into the own candidate dir passes", r === undefined, JSON.stringify(r));
r = await call("edit", { path: "population.json", oldText: "a", newText: "b" });
check("an edit of a machine file is blocked", r?.block === true && /one writer/.test(r.reason), JSON.stringify(r));

await fire("turn_start", { turnIndex: 1 });
r = await fire("tool_result", { toolName: "bash", content: [{ type: "text", text: "out" }] });
check("a countdown note is appended near the turn budget", Array.isArray(r?.content) && /\[lab\] 1 turn of 3 left/.test(r.content.at(-1).text), JSON.stringify(r));
await fire("turn_start", { turnIndex: 2 });
r = await call("bash", { command: "ls" });
check("the last turn still runs tools", r === undefined, JSON.stringify(r));
r = await fire("tool_result", { toolName: "bash", content: [{ type: "text", text: "out" }] });
check("the last turn's results say so", /last turn of 3/.test(r?.content?.at(-1)?.text || ""), JSON.stringify(r));
await fire("turn_start", { turnIndex: 3 });
r = await call("bash", { command: "ls" });
check("past the budget every tool call is blocked and terminates the run", r?.block === true && r?.terminate === true && /turn budget of 3/.test(r.reason), JSON.stringify(r));
r = await call("write", { path: "candidates/c0001/summary.md", content: "x" });
check("… even a write", r?.block === true && r?.terminate === true, JSON.stringify(r));

console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
