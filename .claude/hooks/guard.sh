#!/usr/bin/env bash
# PreToolUse(Bash) hook — evidence is immutable, and the machine files have one writer.
# Denies commands that would delete or rewrite candidate dirs, population.json,
# LEDGER.md, REPORT.md or events.jsonl. Exit 2 blocks the call and shows stderr to
# the agent; the message names the `lab` subcommand it should have used.
set -uo pipefail

LAB_HOOK_INPUT=$(cat 2>/dev/null || echo '{}')
export LAB_HOOK_INPUT

python3 - <<'PY'
import fnmatch, json, os, re, shlex, sys

try:
    data = json.loads(os.environ.get("LAB_HOOK_INPUT", "{}"))
except Exception:
    sys.exit(0)

EVIDENCE = r"(candidates/|events\.jsonl|LEDGER\.md|population\.json|REPORT\.md)"
MACHINE = r"(events\.jsonl|population\.json|FORMAT\.json|fitness\.json|finding\.json|LEDGER\.md|experiments\.sqlite3)"

# The editing tools reach the same files without a shell: the machine files have one
# writer whichever tool is used, and a worker edits only its own candidate dir.
tool = data.get("tool_name")
WORKER = os.environ.get("LAB_ROLE") == "worker"
OWN_DIR = os.path.normpath(os.environ.get("LAB_CANDIDATE_DIR", "") or "") if os.environ.get("LAB_CANDIDATE_DIR") else ""
OWN = os.path.basename(OWN_DIR)


def readable_ids():
    """The candidates a worker may read: its own and the ones its job card names
    (contract.may_read: the parents). A missing or unreadable job.json leaves only its own."""
    ids = {OWN} if OWN else set()
    try:
        card = json.load(open(os.path.join(OWN_DIR, "job.json")))
        for rel in (card.get("contract") or {}).get("may_read") or []:
            m = re.fullmatch(r"(?:.*/)?candidates/(c\d{4})/?", str(rel))
            if m:
                ids.add(m.group(1))
    except (OSError, ValueError):
        pass
    # What `lab index` returned to this worker is its to open: the index finds the dir,
    # the shared filesystem holds the code. Every such read has a logged query before it.
    try:
        for line in open(os.path.join(OWN_DIR, "queries.jsonl")):
            for cid in json.loads(line).get("ids") or []:
                m = re.fullmatch(r"(?:[\w-]+:)?(c\d{4})", str(cid))
                if m:
                    ids.add(m.group(1))
    except (OSError, ValueError):
        pass
    return ids


def read_scope(text):
    """None when every candidates/... path in `text` is the worker's own or a parent's;
    otherwise the offending path. A glob, a variable or the bare directory is every
    candidate, so it is refused too."""
    ok = readable_ids()
    for m in re.finditer(r"candidates/([^\s/'\"`;|&)\\]*)", text):
        if m.group(1) not in ok:
            return m.group(0)
    if re.search(r"/candidates(?=$|[\s'\";|&)])", text):
        return "candidates"
    return None


# The textual check above only sees a path spelled out in full. What got past it (hsrc-v1
# Acrip c0009 read a sibling's summary once): a glob (`*/c0008`, `cand*`), a cd, a `..` hop
# from the own dir, a variable, a recursive search over the campaign root, a Glob or Grep
# without a path. So a worker's paths are also resolved against the session cwd, with
# symlinks, globs expanded on disk, and checked against the candidates dir itself.
# Still not a sandbox: a path built at run time by code the worker writes is not seen.
CAND = os.path.dirname(OWN_DIR) if OWN_DIR else ""
CWD = os.path.normpath(data.get("cwd") or os.getcwd())


def _forms(p):
    return {os.path.normpath(p), os.path.realpath(p)}


# A blind arm ([selection] blind; job.json "blind": true) also sees no scoreboard: the
# campaign's machine files, its .lab dir and its index hold every candidate's score.
SCOREBOARD = ("population.json", "LEDGER.md", "events.jsonl", "REPORT.md", "experiments.sqlite3")
ROOT = os.path.dirname(CAND) if CAND else ""


def _blind():
    try:
        return bool(json.load(open(os.path.join(OWN_DIR, "job.json"))).get("blind"))
    except (OSError, ValueError):
        return False


BLIND = WORKER and bool(OWN_DIR) and _blind()


def scoreboard(path):
    """Why a path is the campaign's scoreboard, for a blind worker, or None."""
    if not (BLIND and ROOT):
        return None
    for p in _forms(path):
        for r in _forms(ROOT):
            if p in {os.path.join(r, n) for n in SCOREBOARD}:
                return "the scoreboard (this arm is blind)"
            for d in (".lab", "index"):
                if p == os.path.join(r, d) or p.startswith(os.path.join(r, d) + os.sep):
                    return "the scoreboard (this arm is blind)"
    return None


def out_of_scope(path, ok, listing=True):
    """Why an absolute path is outside the read scope, or None. Inside the candidates dir
    only the readable ids; the dir itself is the list of every candidate (`listing`); any
    other campaign's candidates dir is out of scope whatever the id. Both the lexical path
    and the one through symlinks must pass. A blind worker's scope also excludes the
    scoreboard."""
    why = scoreboard(path)
    if why:
        return why
    for p in sorted(_forms(path)):
        inside = False
        for c in _forms(CAND):
            if p == c:
                if listing:
                    return "the candidates dir"
                inside = True
            elif p.startswith(c + os.sep):
                cid = p[len(c) + 1:].split(os.sep)[0]
                if cid not in ok:
                    return f"candidates/{cid}"
                inside = True
        if not inside and re.search(r"/candidates/c\d{4}(?:/|$)", p):
            return "another campaign's candidates"
    return None


def holds_candidates(path):
    """True when a recursive walk from `path` reaches the candidates dir."""
    return any(c == p or c.startswith(p.rstrip(os.sep) + os.sep)
               for p in _forms(path) for c in _forms(CAND))


GLOB = re.compile(r"[*?\[]")


def glob_scope(pattern, ok, listing=True):
    """Expand an absolute glob on disk and check every match. A `**` from a dir that holds
    the candidates is refused unexpanded: it reaches all of them."""
    import glob as _glob
    head = pattern.split("**")[0] if "**" in pattern else ""
    if head and holds_candidates(os.path.dirname(head.rstrip(os.sep) + os.sep + "x")):
        return f"`{pattern}` over every candidate"
    for i, m in enumerate(_glob.iglob(pattern, recursive=True)):
        why = out_of_scope(m, ok, listing)
        if why or i > 5000:
            return why or f"`{pattern}` (too many matches to check)"
    return None


def candidate_ids():
    try:
        return [n for n in os.listdir(CAND) if re.fullmatch(r"c\d{4}", n)]
    except OSError:
        return []


def braces(word, depth=0):
    m = re.search(r"\{([^{}]*,[^{}]*)\}", word)
    if not m or depth > 4:
        return [word]
    return [x for alt in m.group(1).split(",")
            for x in braces(word[:m.start()] + alt + word[m.end():], depth + 1)]


UNKNOWN = "\0"
# Commands that walk a tree: from a dir that holds the candidates dir they read every one.
REC_EXE = {"find", "rg", "ag", "ack", "fd", "fdfind", "tree", "rsync"}
REC_FLAG = {"grep": "rR", "egrep": "rR", "fgrep": "rR", "zgrep": "rR", "ls": "R", "cp": "rRa",
            "scp": "r", "diff": "r", "zip": "r", "chmod": "R", "chown": "R", "tar": "c"}
REC_CODE = re.compile(r"os\.walk|\.rglob\(|copytree|recursive\s*=\s*True|readdirSync|\bwalkdir\b"
                      r"|\bgit\b[^;&|\n]*\b(?:grep|archive)\b")
PATTERN_FIRST = {"grep", "egrep", "fgrep", "zgrep", "rg", "ag", "ack"}


def walks(exes, toks):
    """True when the command walks a tree: find, rg, grep -r, ls -R, cp -r, tar c..."""
    for k, e in enumerate(exes):
        if e in REC_EXE:
            return True
        flags = REC_FLAG.get(e)
        if not flags:
            continue
        args = toks[k + 1:k + 2] if e == "tar" else [t for t in toks[k + 1:] if t.startswith("-")]
        if any(t in ("--recursive", "--archive", "--create") or re.fullmatch(rf"-?[a-zA-Z]*[{flags}][a-zA-Z]*", t)
               for t in args):
            return True
    return False


def bash_read_scope(text):
    """The offending path of a worker's command, or None. Spelled out: `candidates` only
    as candidates/<readable id>, a candidate id only if readable. Resolved: every path
    word against the session cwd, following cd and the variables the command assigns,
    globs expanded on disk. Recursive: no walk from a dir that holds the candidates dir."""
    ok = readable_ids()
    if BLIND:
        m = re.search(r"(?<![\w.-])(?:population\.json|LEDGER\.md|events\.jsonl|REPORT\.md"
                      r"|experiments\.sqlite3)(?![\w.-])|(?<![\w.-])\.lab(?![\w-])", text)
        if m:
            return f"{m.group(0)} (the scoreboard; this arm is blind)"
    for m in re.finditer(r"(?<![\w.$-])candidates(?![\w-])(/c\d{4}(?=$|[/\s'\"`;|&)<>]))?", text):
        if not m.group(1) or m.group(1)[1:] not in ok:
            return text[m.start():m.end() + 12].split("\n")[0]
    for seg in re.split(r"[;&|\n]+", text):
        toks = seg.split()
        if toks and os.path.basename(toks[0]) == "lab":
            if BLIND and len(toks) > 1 and toks[1] in ("campaign", "index", "status", "report", "job"):
                return f"lab {toks[1]} (it shows other candidates; this arm is blind)"
            continue    # `lab index open cNNNN`: lab logs what it shows the worker
        m = re.search(r"(?<![\w-])c\d{4}(?![\w-])", seg)
        if m and m.group(0) not in ok:
            return m.group(0)
    # The shell's own state is the worker's shell's, not the hook's: $_, $OLDPWD and the dir
    # stack are tracked here from this command or unknown, never read from os.environ (the
    # hook's $_ is its own python3, which sent `mkdir -p d && cd $_` nowhere; pinf K2, 2026-10-17).
    env = {k: v for k, v in os.environ.items() if k not in ("_", "OLDPWD", "DIRSTACK")}
    cwd, oldpwd, prev, lost, doubt, ids = CWD, None, None, False, False, None
    subs = [a or b for a, b in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", text)]
    text = re.sub(r"\$\(\([^()]*\)\)", "0", text)
    text = re.sub(r"\$\([^()]*\)|`[^`]*`", UNKNOWN, text)
    parts = re.split(r"([;&|\n]+|\b(?:then|do|else)\b)", text)
    segs = [(parts[i], parts[i - 1] if i else "", parts[i + 1] if i + 1 < len(parts) else "")
            for i in range(0, len(parts), 2)] + [(s, "", "") for s in subs]
    for seg, sep, nxt in segs:
        # a cd into a dir that is not there yet holds only along its && chain: if it fails,
        # whatever comes after a `;`, `||` or newline runs where the shell already was
        if doubt and not re.fullmatch(r"&&\n*", sep):
            cwd, oldpwd, doubt = None, None, False
        for name, val in re.findall(r"(?:^|\s)(?:export\s+|local\s+)?([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|\S*)", seg):
            env[name] = val.strip("'\"")
        env["PWD"] = cwd or UNKNOWN
        env["OLDPWD"] = oldpwd or UNKNOWN
        # $_ is the last argument of the previous simple command, when that one ran in this
        # shell right before (`;`, `&&`, `||`, a newline) and was read without doubt
        env["_"] = prev if prev and re.fullmatch(r"(?:;|\n|&&|\|\|)+", sep) else UNKNOWN

        def subst(w):
            return re.sub(r"\$\{?([A-Za-z_]\w*)\}?|\$[\d@*#?!-]",
                          lambda v: env.get(v.group(1), UNKNOWN) if v.group(1) else UNKNOWN, w)

        def tilde(w):
            # ~- is $OLDPWD, ~+ is $PWD, ~N / ~+N / ~-N the dir stack
            t = re.match(r"~([+-]?)(\d*)(?=/|$)", w)
            if not t or (not t.group(1) and not t.group(2)):
                return os.path.expanduser(w)
            known = None if t.group(2) else (oldpwd if t.group(1) == "-" else cwd)
            return (known or UNKNOWN) + w[t.end():]
        try:
            toks = [subst(t) for t in shlex.split(seg)]
        except ValueError:
            # a cut inside quotes or a heredoc body: from here on the words are not aligned
            toks, lost = [subst(t) for t in seg.split()], True
        lost = lost or "<<" in seg
        while toks and re.fullmatch(r"[A-Za-z_]\w*=.*", toks[0]):
            toks.pop(0)
        prev = None if (lost or not toks or re.search(r"[<>()]", seg)
                        or toks[0] in ("!", "{", "}", "if", "elif", "while", "until", "for", "case",
                                       "select", "time", "coproc", "function", "fi", "done", "esac")
                        or re.search(r"[${}\0]", toks[-1]) or GLOB.search(toks[-1])) else toks[-1]
        resolved = []
        # the words as the shell joins them ("$d"/x is one) and as code quotes them (open('x'))
        raws = list(dict.fromkeys(toks + [subst(r) for r in re.split(r"[\s'\"()<>]+", seg)]))
        for raw in raws:
            # an id spelled out only once the variables are in (X=c000; cd ${X}0)
            sid = next((c for c in re.findall(r"(?<![\w-])c\d{4}(?![\w-])", raw) if c not in ok), None)
            if sid:
                return sid
            raw = re.sub(r"^(?:-[\w-]+|[A-Za-z_]\w*)=", "", raw)
            for w in [x for b in braces(raw) for x in re.split(r"[,:]", b)]:
                if not (w in (".", "..") or "/" in w or GLOB.search(w) or w.startswith("~")):
                    continue
                w = tilde(w)
                if UNKNOWN in w or cwd is None:
                    # an unknown prefix: no id is spelled out (checked above), so refuse only
                    # a wildcard component that could be another candidate's id
                    ids = candidate_ids() if ids is None else ids
                    for comp in w.split(UNKNOWN)[-1].split("/"):
                        if GLOB.search(comp) and any(fnmatch.fnmatchcase(i, comp) for i in ids if i not in ok):
                            return w.replace(UNKNOWN, "$…")
                    resolved.append(None)
                    continue
                full = os.path.normpath(os.path.join(cwd, w))
                # a glob that only matches the candidates dir names it, it does not list it
                why = glob_scope(full, ok, listing=False) if GLOB.search(w) else out_of_scope(full, ok)
                if why:
                    return f"{w} ({why})"
                resolved.append(full)
        exes = [os.path.basename(t) for t in toks]
        if exes and exes[0] in ("cd", "pushd", "popd"):
            # Only a plain `cd [-L|-P|-e|-@] [--] DIR` is followed. A failed cd stays put and a
            # CDPATH one goes elsewhere, so anything else leaves the dir unknown, not guessed.
            dests = toks[1:]
            while dests and dests[0].startswith("-") and dests[0] != "-":
                opt = dests.pop(0)
                if opt == "--":
                    break
                if not re.fullmatch(r"-[LPe@]+", opt):
                    dests = None
                    break
            if exes[0] == "popd" or dests is None or len(dests) > 1 or (exes[0] == "pushd" and not dests):
                new = None
            else:
                dest = dests[0] if dests else env.get("HOME", UNKNOWN)
                dest = (oldpwd or UNKNOWN) if dest == "-" else tilde(dest)
                if env.get("CDPATH") and not re.match(r"(?:/|\.\.?(?:/|$))", dest):
                    new = None
                else:
                    new = None if UNKNOWN in dest or (cwd is None and not dest.startswith("/")) \
                        else os.path.normpath(os.path.join(cwd or "/", dest))
            if re.search(r"(?<![|&])[|&](?![|&])|\|&", sep + " " + nxt):
                new = None      # a cd in a pipeline moves a subshell, not this shell
            doubt = doubt or (new is not None and not os.path.isdir(new))
            oldpwd, cwd = cwd, new
            continue
        code = bool(REC_CODE.search(seg))
        if not (code or walks(exes, toks)):
            continue
        pos = [t for t in toks[1:] if not t.startswith("-")]
        if exes[0] in PATTERN_FIRST and pos and not re.search(r"\s(?:-e|-f|--regexp)\b", seg):
            pos = pos[1:]
        targets = [None if UNKNOWN in t or cwd is None else os.path.normpath(os.path.join(cwd, os.path.expanduser(t)))
                   for t in pos if UNKNOWN in t or cwd is None or "/" in t or t in (".", "..")
                   or os.path.isdir(os.path.join(cwd, t))]
        if code:
            targets += [r for r in resolved if r is None or os.path.isdir(r)]
        for t in targets or [cwd]:
            if t is None or holds_candidates(t):
                return f"a recursive read of {t or 'an unresolved dir'}, which holds every candidate"
    return None


READ_WHY = ("that reads a candidate your job card does not list. A worker reads its own dir and "
            "the candidates its job card or its own `lab index` queries returned ({ids}).")

if WORKER and OWN and tool in ("Read", "Grep", "Glob", "LS"):
    inp = data.get("tool_input") or {}
    base = CWD
    ok = readable_ids()
    bad = None
    for key in ("file_path", "path", "pattern", "glob"):
        v = str(inp.get(key) or "").strip()
        if not v or (key == "pattern" and tool == "Grep"):
            continue        # a Grep pattern is text to find, not a path
        full = os.path.normpath(os.path.join(base, v))
        bad = bad or read_scope(full + ("/" if full.endswith("/candidates") else ""))
    # Resolved: the dir searched (the session cwd when no path is given), through symlinks;
    # a Glob's matches on disk; a Grep from a dir that holds the candidates reaches them all.
    where = os.path.normpath(os.path.join(base, str(inp.get("file_path") or inp.get("path") or "").strip() or "."))
    bad = bad or out_of_scope(where, ok, listing=tool != "Glob")
    if not bad and tool == "Grep" and holds_candidates(where):
        bad = f"a recursive search of {where}, which holds every candidate"
    pat = str(inp.get("glob" if tool == "Grep" else "pattern") or "").strip() if tool in ("Grep", "Glob") else ""
    if not bad and pat:
        bad = glob_scope(os.path.normpath(os.path.join(where, pat)), ok, listing=False)
    if bad:
        print(f"Blocked: {tool} {json.dumps(inp)[:200]} — `{bad}`: "
              + READ_WHY.format(ids=", ".join(sorted(ok))), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
    inp = data.get("tool_input") or {}
    fp = str(inp.get("file_path") or inp.get("notebook_path") or "")
    fp = fp.strip()
    if fp:
        # resolve against the tool's cwd, then lexically: candidates/c0004/../c0001/x is
        # c0001's, and ../c0001/x from inside c0004 is too
        fp = os.path.normpath(os.path.join(data.get("cwd") or os.getcwd(), fp))
    if re.search(rf"(?:^|/){MACHINE}$", fp):
        print(f"Blocked: {tool} {fp} — the machine files (population.json, LEDGER.md, "
              "fitness.json, finding.json, events.jsonl, FORMAT.json) have exactly one writer: "
              "`tools/lab`.", file=sys.stderr)
        sys.exit(2)
    if os.environ.get("LAB_ROLE") == "worker" and fp:
        own_dir = os.path.normpath(os.environ.get("LAB_CANDIDATE_DIR", "") or "")
        own = os.path.basename(own_dir)
        m = re.search(r"/candidates/(c\d{4})(?:/|$)", fp)
        inside_own = own_dir and (fp == own_dir or fp.startswith(own_dir + os.sep))
        if m and own and not inside_own:
            print(f"Blocked: {tool} {fp} — that writes into another candidate's dir. A worker "
                  f"writes only inside its own ({own}).", file=sys.stderr)
            sys.exit(2)
    sys.exit(0)
if tool != "Bash":
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command", "")
if not cmd:
    sys.exit(0)

START = r"(?:^|[;&|]\s*|\$\(\s*)"
NOSEP = r"[^;&|]*"

RULES = [
    (rf"{START}(?:sudo\s+)?(?:rm|rmdir|shred|unlink|trash)\b{NOSEP}{EVIDENCE}",
     "that deletes evidence. Candidate dirs, LEDGER rows, REPORT.md and events.jsonl are "
     "append-only history — a failed, killed or invalid candidate is data. If a candidate "
     "is misleading, say so in the next candidate's summary.md and in the report instead."),
    (rf"{START}(?:sudo\s+)?mv\b{NOSEP}{EVIDENCE}",
     "that moves evidence out from under its recorded path. Paths in LEDGER.md, "
     "population.json, config.json and the event feed must keep resolving."),
    (rf"{START}(?:sudo\s+)?git\s+(?:rm|clean|checkout\s+--|restore)\b{NOSEP}{EVIDENCE}",
     "that removes or reverts committed evidence."),
    (rf">{NOSEP}?\s*\.?/?{MACHINE}",
     "that writes the machine files directly. population.json, LEDGER.md, fitness.json and "
     "events.jsonl have exactly one writer: `tools/lab` (`lab run`, `lab eval`, `lab log`); "
     "FORMAT.json is generated by `lab format sync`."),
    (rf"{START}(?:tee|truncate|dd)\b{NOSEP}{MACHINE}",
     "that rewrites a machine file. Use `tools/lab log` / `tools/lab format sync`; the "
     "loop's own files are written by `lab run`."),
    (rf"{START}(?:sudo\s+)?(?:cp|install|mv|ln|rsync|touch)\b{NOSEP}{MACHINE}",
     "that creates or replaces a machine file by copying. population.json, LEDGER.md, "
     "fitness.json, finding.json, events.jsonl and FORMAT.json are written only by "
     "`tools/lab`; a finding.json a worker writes is quarantined at settlement, not adopted."),
    (rf"{START}(?:sudo\s+)?(?:sed|perl)\b{NOSEP}-[a-zA-Z]*i{NOSEP}{MACHINE}",
     "that edits a machine file in place. Events and ledger rows are never edited (append "
     "a correcting `lab log note` instead); fitness.json and finding.json are written only "
     "by `lab`."),
    (rf"curl{NOSEP}\|\s*(?:ba|z|)sh",
     "that pipes a download straight into a shell."),
]

# A worker session (LAB_ROLE=worker, launched by `lab run`) may touch only its own
# candidate dir and must never look for the hidden labels. The job card says so; this
# makes the attempt visible and blocked at the tool boundary as well.
if os.environ.get("LAB_ROLE") == "worker":
    inp = data.get("tool_input") or {}
    # A deliberately shallow guard, not a Bash parser. Skip conventional heredoc
    # bodies (including <<- and multiple documents), but inspect their headers and
    # commands after their delimiters. CLI controls and owned-process containment
    # enforce lifetime even for shell syntax this heuristic does not recognize.
    detached = inp.get("run_in_background")
    heredocs = []
    for line in cmd.splitlines():
        if heredocs:
            delimiter, strip_tabs = heredocs[0]
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                heredocs.pop(0)
            continue
        lexer = shlex.shlex(line, posix=False, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            # Do not interpret the remaining quoted body as shell commands. Only
            # this heuristic fails open; explicit background and RULES still apply.
            detached = inp.get("run_in_background")
            break
        for i, token in enumerate(tokens):
            if token == "<<" and i + 1 < len(tokens):
                word = tokens[i + 1]
                strip_tabs = word.startswith("-")
                word = word[1:] if strip_tabs else word
                if re.fullmatch(r"(?:[\w]+|'[\w]+'|\"[\w]+\")", word):
                    heredocs.append((word.strip("'\""), strip_tabs))
            if token in ("&", "&;"):
                detached = True
            # Executables only at simple command positions, never prose arguments.
            if i == 0 or tokens[i - 1] in (";", "&&", "||", "|", "&"):
                executable = os.path.basename(token.strip("'\""))
                if executable in ("nohup", "setsid", "disown"):
                    detached = True
                if executable == "lab" and tokens[i + 1:i + 3] in (["watch", "start"], ["watch", "_run"]):
                    detached = True
    if detached:
        print("Blocked: workers must run synchronously in the foreground with a bounded "
              "Bash timeout. No background tasks or nested watchers; wait for exit, "
              "check predictions, and write summary.md before ending the session.", file=sys.stderr)
        sys.exit(2)
    RULES.append((r"LAB_PRIVATE|labels\.json|/labels(?:/|\b)",
                  "a worker never reads labels. Fitness comes from `lab eval`, which is the "
                  "only reader of the search and final splits."))
    # Writes: only the destination counts. `cp candidates/<parent>/code/x candidates/<own>/code/`
    # reads the parent and writes the worker's own dir; the older rule matched either side
    # and cost improve workers turns (pi-engram read, 2026-09-17).
    def write_targets(command):
        out = [m.group(1) for m in re.finditer(r"(?:&>|>>?)\s*['\"]?([^\s'\";|&)]+)", command)]
        for seg in re.split(r"[;&|\n]+", command):
            try:
                toks = shlex.split(seg)
            except ValueError:
                toks = seg.split()
            while toks and re.fullmatch(r"\w+=.*", toks[0]):
                toks.pop(0)
            if not toks:
                continue
            exe, args = os.path.basename(toks[0]), [t for t in toks[1:] if not t.startswith("-")]
            if exe in ("cp", "install", "rsync", "ln"):
                t = re.search(r"(?:-t|--target-directory)[= ]\s*(\S+)", seg)
                out += [t.group(1)] if t else args[-1:]
            elif exe in ("mv", "rm", "rmdir", "shred", "unlink", "touch", "mkdir", "tee", "truncate", "chmod"):
                out += args
            elif exe in ("sed", "perl") and re.search(r"\s-[a-zA-Z]*i", seg):
                out += args
        return out

    if OWN:
        for target in write_targets(cmd):
            m = re.search(r"candidates/(c\d{4})", target)
            if m and m.group(1) != OWN:
                print(f"Blocked: `{cmd}` — that writes into another candidate's dir. A worker "
                      f"writes only inside {OWN_DIR}.", file=sys.stderr)
                sys.exit(2)
        # Reads: the text a file-writing heredoc carries (cat/tee <<EOF … a summary naming
        # an ancestor) is prose, not a path; an interpreter's heredoc is code and is read.
        scoped, skip = [], None
        for line in cmd.splitlines():
            if skip is not None:
                if line.strip() == skip:
                    skip = None
                continue
            scoped.append(line)
            h = re.search(r"(?:^|[;&|]\s*)(?:cat|tee)\b[^;&|]*<<-?\s*['\"]?(\w+)", line)
            if h:
                skip = h.group(1)
        bad = bash_read_scope("\n".join(scoped))
        if bad:
            hint = ("" if "/" in bad or not bad.startswith("candidates") else
                    " The word `candidates` reads as that dir here even as a code name: rename it, "
                    "or put the code in a file under your own dir.")
            print(f"Blocked: `{cmd}` — `{bad}`: " + READ_WHY.format(ids=", ".join(sorted(readable_ids()))) + hint,
                  file=sys.stderr)
            sys.exit(2)

for pattern, why in RULES:
    if re.search(pattern, cmd):
        print(f"Blocked: `{cmd}` — {why}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
PY
