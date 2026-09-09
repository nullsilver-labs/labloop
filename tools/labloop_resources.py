"""Private subscription scheduling foundation; deliberately NO provider dispatch.

Local slice ceilings are not vendor quota or money. This module is supervisor-side
plumbing, not an OS authority boundary. Never give a future worker its filesystem
identity/access. CLI authorization here authorizes local scheduling allocations only.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time


class ResourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ResourceError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def object_keys(value, keys, label):
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == set(keys), f"{label}: missing or unsupported fields; expected {', '.join(keys)}")


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, f"{label} must be an integer in {low}..{high}")


def identifier(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value),
            f"invalid {label}")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    def invalid_constant(_):
        raise ResourceError("nonfinite JSON number")
    with Path(path).open("rb") as source:
        data = source.read(131073)
    require(len(data) <= 131072, "configuration exceeds 128 KiB")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


def private_path(path, directory=False):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode), "private resource path must not be a symlink")
    require(info.st_uid == os.getuid(), "private resource path must be owned by current operator")
    require(info.st_mode & 0o077 == 0, "private resource path permits group/other access")
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
            "wrong private resource path type")
    if not directory:
        require(info.st_nlink == 1, "private resource file must not have hard links")


def project_root(policy_path):
    parent = policy_path.resolve().parent
    return next((p for p in (parent, *parent.parents) if (p / ".git").exists()), parent)


def resolve(inventory_path, policy_path):
    """Strict v1 or explicitly opted-in fresh v2; no allocation migration."""
    inventory_path, policy_path = Path(inventory_path).expanduser(), Path(policy_path)
    private_path(inventory_path.parent, directory=True)
    private_path(inventory_path)
    inventory = load_json(inventory_path)
    policy = load_json(policy_path)
    object_keys(inventory, ("schema_version", "ledger_path", "new_cash_spending", "providers", "pools"), "inventory")
    integer(inventory["schema_version"], 1, 2, "inventory schema_version")
    cash = inventory["new_cash_spending"]
    object_keys(cash, ("enabled", "currency", "monthly_limit"), "new_cash_spending")
    require(cash["enabled"] is False and cash["monthly_limit"] == "0.00", "new cash spending must be disabled and zero")
    require(isinstance(cash["currency"], str) and re.fullmatch("[A-Z]{3}", cash["currency"]), "invalid currency")
    pools = inventory["pools"]
    require(type(pools) is dict and len(pools) == 1,
            "exactly one account subscription pool is supported; model aliases must share it")
    for pool_id, pool in pools.items():
        identifier(pool_id, "pool ID")
        object_keys(pool, ("kind", "max_parallel_sessions", "max_worker_slices_per_day",
                           "max_turns_per_slice", "max_slice_wall_seconds", "allow_paid_overage"), "pool")
        require(pool["kind"] == "subscription", "only subscription pools are implemented; prepaid/cash disabled")
        integer(pool["max_parallel_sessions"], 1, 1, "max_parallel_sessions")
        integer(pool["max_worker_slices_per_day"], 1, 100, "max_worker_slices_per_day")
        integer(pool["max_turns_per_slice"], 1, 100, "max_turns_per_slice")
        integer(pool["max_slice_wall_seconds"], 1, 3600, "max_slice_wall_seconds")
        require(pool["allow_paid_overage"] is False, "paid overage must be disabled")
    providers = inventory["providers"]
    require(type(providers) is dict and bool(providers), "at least one provider is required")
    for provider_id, provider in providers.items():
        identifier(provider_id, "provider ID")
        object_keys(provider, ("enabled", "adapter", "authentication", "pool", "models",
                               "allow_subagents", "allow_paid_features"), "provider")
        require(type(provider["enabled"]) is bool, "provider enabled must be boolean")
        require(provider["adapter"] == "claude_code_cli" and provider["authentication"] == "native_subscription",
                "only native subscription configuration is implemented")
        require(isinstance(provider["pool"], str) and provider["pool"] in pools, "provider references unknown pool")
        require(provider["allow_subagents"] is False and provider["allow_paid_features"] is False,
                "subagents and paid features must be disabled")
        models = provider["models"]
        require(type(models) is dict and bool(models), "model roles are required")
        for role, model in models.items():
            identifier(role, "model role")
            require(isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model),
                    "invalid model ID/alias")
    object_keys(policy, ("schema_version", "project_id", "mode", "mission_file", "routing",
                         "allocations", "max_campaign_wall_hours"), "project policy")
    integer(policy["schema_version"], 1, 2, "policy schema_version")
    require(policy["schema_version"] == inventory["schema_version"], "inventory/policy version mismatch")
    identifier(policy["project_id"], "project ID")
    require(policy["mode"] == "discovery", "resource foundation requires explicit discovery mode")
    integer(policy["max_campaign_wall_hours"], 1, 168, "max_campaign_wall_hours")
    object_keys(policy["routing"], ("research",), "routing")
    routes = policy["routing"]["research"]
    require(type(routes) is list and len(routes) == 1 and isinstance(routes[0], str), "exactly one research route required")
    parts = routes[0].split(":")
    require(len(parts) == 2, "route must be provider:role")
    provider_id, role = parts
    require(provider_id in providers, "route provider unknown")
    provider = providers[provider_id]
    require(provider["enabled"], "route provider disabled")
    require(role in provider["models"], "route model role unknown")
    pool_id = provider["pool"]
    object_keys(policy["allocations"], (pool_id,), "allocations")
    allocation = policy["allocations"][pool_id]
    allocation_keys = ("campaign_slices", "daily_slices", "confirmation_slices", "finalization_slices")
    object_keys(allocation, allocation_keys + (("local_packet",) if policy["schema_version"] == 2 else ()), "allocation")
    integer(allocation["campaign_slices"], 1, 10000, "campaign_slices")
    integer(allocation["daily_slices"], 1, pools[pool_id]["max_worker_slices_per_day"], "daily_slices")
    integer(allocation["confirmation_slices"], 0, allocation["campaign_slices"], "confirmation_slices")
    integer(allocation["finalization_slices"], 1, allocation["campaign_slices"], "finalization_slices")
    require(allocation["confirmation_slices"] + allocation["finalization_slices"] <= allocation["campaign_slices"],
            "protected slices exceed campaign allocation")
    if policy["schema_version"] == 2:
        integer(allocation["confirmation_slices"], 1, allocation["campaign_slices"], "confirmation_slices")
        packet = allocation["local_packet"]
        object_keys(packet, ("inference_unit", "campaign", "confirmation", "finalization"), "local_packet")
        require(packet["inference_unit"] == "local_token", "only explicit local_token accounting is supported; not vendor allowance")
        for purpose in ("campaign", "confirmation", "finalization"):
            object_keys(packet[purpose], DIMENSIONS, purpose + " packet")
            for dimension in DIMENSIONS:
                integer(packet[purpose][dimension], allocation[purpose + "_slices"], 10**9, dimension)
        for dimension in DIMENSIONS:
            require(packet["confirmation"][dimension] + packet["finalization"][dimension] <= packet["campaign"][dimension],
                    "protected packet exceeds campaign allocation")
        for purpose in ("confirmation", "finalization"):
            require(packet[purpose]["wall_seconds"] <= allocation[purpose + "_slices"] * pools[pool_id]["max_slice_wall_seconds"],
                    "protected wall packet cannot fit allocated worker slices")
        require(packet["campaign"]["wall_seconds"] <= policy["max_campaign_wall_hours"] * 3600,
                "packet wall allocation exceeds campaign duration")
    root = project_root(policy_path)
    require(not inventory_path.resolve().is_relative_to(root), "inventory must be outside the project repository")
    require(isinstance(inventory["ledger_path"], str), "ledger_path must be a string")
    ledger = Path(inventory["ledger_path"]).expanduser()
    require(ledger.is_absolute(), "ledger_path must be absolute (or ~/...) ")
    require(not ledger.resolve().is_relative_to(root), "ledger must be outside the project repository")
    # Bind the lexical path too: symlink files are rejected when opening the ledger.
    inventory["ledger_path"] = str(ledger)
    mission_name = policy["mission_file"]
    require(isinstance(mission_name, str) and bool(mission_name) and not Path(mission_name).is_absolute(), "mission_file must be relative")
    mission_path = (policy_path.resolve().parent / mission_name).resolve()
    require(mission_path.is_relative_to(root), "mission must stay inside project repository")
    with mission_path.open("rb") as source:
        mission = source.read(131073)
    require(0 < len(mission) <= 131072 and bool(mission.strip()), "mission must be nonempty and at most 128 KiB")
    resolved = {"inventory": inventory, "policy": policy, "project_root": str(root),
                "mission_hash": hashlib.sha256(mission).hexdigest(), "mission_text": mission.decode("utf-8")}
    return {**resolved, "authorization_hash": fingerprint(resolved), "inventory_hash": fingerprint(inventory),
            "pool": pool_id, "provider": provider_id, "model": provider["models"][role]}


@contextmanager
def transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()


DIMENSIONS = ("evaluator_runs", "cpu_seconds", "inference_units", "wall_seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS grants (
 project TEXT PRIMARY KEY, authorization_hash TEXT NOT NULL, mission_hash TEXT NOT NULL,
 pool TEXT NOT NULL, allocation TEXT NOT NULL, authorized_at REAL NOT NULL, deadline REAL NOT NULL,
 approved_config TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES grants(project), pool TEXT NOT NULL,
 purpose TEXT NOT NULL CHECK(purpose IN ('exploration','confirmation','finalization')),
 status TEXT NOT NULL CHECK(status IN ('reserved','active','uncertain','settled','cancelled')),
 day TEXT NOT NULL, reserved_at REAL NOT NULL, dispatched_at REAL, deadline REAL,
 finished_at REAL, exit_code INTEGER
);
CREATE TABLE IF NOT EXISTS audit (
 sequence INTEGER PRIMARY KEY, timestamp REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL
);
"""


V2_SCHEMA = """
CREATE TABLE leases (
 pool TEXT PRIMARY KEY, generation INTEGER NOT NULL, owner TEXT NOT NULL,
 identity TEXT NOT NULL, heartbeat REAL NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE session_packets (
 session TEXT PRIMARY KEY REFERENCES sessions(id), generation INTEGER NOT NULL,
 costs TEXT NOT NULL, job TEXT UNIQUE, process TEXT
);
"""


def process_identity(value):
    object_keys(value, ("host", "boot_id", "pid", "start_id"), "process identity")
    for key in ("host", "boot_id", "start_id"):
        identifier(value[key], key)
    integer(value["pid"], 1, 2**31 - 1, "pid")


def audit(db, kind, payload, now):
    db.execute("INSERT INTO audit(timestamp,kind,payload) VALUES (?,?,?)", (now, kind, canonical(payload)))


class Ledger:
    """Single-host allocation prototype. No connection, credentials or child launch."""
    def __init__(self, config, create=False, *, exit_verifier=None):
        # Freeze caller-owned dictionaries and catch accidental post-resolution edits.
        config = json.loads(canonical(config))
        approved = {key: config[key] for key in ("inventory", "policy", "project_root", "mission_hash", "mission_text")}
        require(config["authorization_hash"] == fingerprint(approved)
                and config["inventory_hash"] == fingerprint(config["inventory"]), "resolved configuration was modified")
        self.config = config
        self.version = config["inventory"]["schema_version"]
        # Trusted supervisor dependency, never worker-supplied evidence or CLI input.
        # Called outside write locks with frozen identity; None means unknown/alive.
        self.exit_verifier = exit_verifier
        path = Path(config["inventory"]["ledger_path"])
        if create:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_path(path.parent, directory=True)
        if create:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        private_path(path)
        self.db = sqlite3.connect(path.absolute().as_uri() + "?mode=rw", uri=True,
                                  isolation_level=None, timeout=10)
        try:
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA synchronous=FULL")
            exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone()
            if create and not exists:
                self.db.executescript(SCHEMA)
            with transaction(self.db):
                saved = self.db.execute("SELECT value FROM metadata WHERE key='inventory_hash'").fetchone()
                if saved is None and create:
                    self.db.execute("INSERT INTO metadata VALUES ('inventory_hash',?)", (config["inventory_hash"],))
                    self.db.execute("INSERT INTO metadata VALUES ('schema_version',?)", (str(self.version),))
                    if self.version == 2:
                        for statement in V2_SCHEMA.split(";"):
                            if statement.strip():
                                self.db.execute(statement)
                else:
                    require(saved is not None and saved[0] == config["inventory_hash"],
                            "inventory differs from authoritative ledger; migration is not implemented")
                version = self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                require(version is not None and version[0] == str(self.version), "unsupported ledger schema")
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def clock(self, now):
        now = time.time() if now is None else now
        if self.version == 2:
            require(type(now) in (int, float) and math.isfinite(now) and 0 <= now <= 253402000000,
                    "invalid supervisor timestamp")
        return now

    def authorize(self, expected_hash, now=None):
        now = self.clock(now)
        cfg = self.config
        require(expected_hash == cfg["authorization_hash"], "approval hash does not match resolved configuration/mission")
        p = cfg["policy"]
        with transaction(self.db):
            old = self.db.execute("SELECT * FROM grants WHERE project=?", (p["project_id"],)).fetchone()
            if old:
                require(old["authorization_hash"] == expected_hash, "project already authorized at a different hash; no implicit reset/revision")
                return dict(old)
            approved = {key: cfg[key] for key in ("inventory", "policy", "project_root", "mission_hash", "mission_text")}
            self.db.execute("INSERT INTO grants VALUES (?,?,?,?,?,?,?,?)",
                            (p["project_id"], expected_hash, cfg["mission_hash"], cfg["pool"],
                             canonical(p["allocations"][cfg["pool"]]), now,
                             now + p["max_campaign_wall_hours"] * 3600, canonical(approved)))
            audit(self.db, "allocation.authorized", {"project": p["project_id"], "hash": expected_hash}, now)
            return dict(self.db.execute("SELECT * FROM grants WHERE project=?", (p["project_id"],)).fetchone())

    def grant(self):
        row = self.db.execute("SELECT * FROM grants WHERE project=?", (self.config["policy"]["project_id"],)).fetchone()
        require(row is not None, "project allocation not authorized")
        require(row["authorization_hash"] == self.config["authorization_hash"], "configuration/mission changed since authorization")
        return row

    def reserve(self, session_id, purpose="exploration", now=None, *, lease=None, costs=None):
        """Atomically admit a local opportunity; unresolved work retains its slot.

        Stable IDs are idempotency keys. Retries after cancellation/settlement must
        use a new ID and a new reservation, never recycle old authorization.
        """
        identifier(session_id, "session ID")
        require(purpose in ("exploration", "confirmation", "finalization"), "unknown session purpose")
        now = self.clock(now)
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        with transaction(self.db):
            grant = self.grant()
            self.check_lease(lease)
            if self.version == 2:
                object_keys(costs, DIMENSIONS, "reservation costs")
                for dimension in DIMENSIONS:
                    integer(costs[dimension], 1, 10**9, dimension)
            else:
                require(costs is None and lease is None, "v1 does not support packets or leases")
            old = self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if old:
                require(old["project"] == grant["project"] and old["purpose"] == purpose,
                        "session ID already belongs to another operation")
                if self.version == 2:
                    saved = self.session_packet(session_id, lease)
                    require(saved["costs"] == canonical(costs), "immutable reservation costs differ")
                return dict(old)
            require(now < grant["deadline"], "campaign deadline reached")
            pool = self.config["inventory"]["pools"][grant["pool"]]
            allocation = json.loads(grant["allocation"])
            outstanding = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pool=? AND status IN ('reserved','active','uncertain')",
                                          (grant["pool"],)).fetchone()[0]
            require(outstanding < pool["max_parallel_sessions"], "pool has an unresolved session; reconcile before new admission")
            # UTC-day attribution is the reservation day, including uncertain use.
            account_daily = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pool=? AND day=? AND status!='cancelled'",
                                            (grant["pool"], day)).fetchone()[0]
            require(account_daily < pool["max_worker_slices_per_day"], "account daily slice ceiling reached")
            project_daily = self.db.execute("SELECT COUNT(*) FROM sessions WHERE project=? AND day=? AND status!='cancelled'",
                                            (grant["project"], day)).fetchone()[0]
            require(project_daily < allocation["daily_slices"], "project daily slice ceiling reached")
            limits = {"confirmation": allocation["confirmation_slices"], "finalization": allocation["finalization_slices"]}
            limits["exploration"] = allocation["campaign_slices"] - sum(limits.values())
            used = self.db.execute("SELECT COUNT(*) FROM sessions WHERE project=? AND purpose=? AND status!='cancelled'",
                                   (grant["project"], purpose)).fetchone()[0]
            require(used < limits[purpose], f"{purpose} slice allocation exhausted (protected partitions cannot be borrowed)")
            if self.version == 2:
                self.check_packet(purpose, costs, now)
            self.db.execute("INSERT INTO sessions VALUES (?,?,?,?,'reserved',?,?,NULL,NULL,NULL,NULL)",
                            (session_id, grant["project"], grant["pool"], purpose, day, now))
            if self.version == 2:
                self.db.execute("INSERT INTO session_packets VALUES (?,?,?,NULL,NULL)",
                                (session_id, lease["generation"], canonical(costs)))
            audit(self.db, "session.reserved", {"id": session_id, "project": grant["project"], "purpose": purpose}, now)
            return dict(self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def session(self, session_id):
        self.grant()
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        require(row is not None and row["project"] == self.config["policy"]["project_id"], "session not owned by project")
        return row

    def mark_dispatched(self, session_id, now=None, *, lease=None, job=None, process=None):
        now = self.clock(now)
        with transaction(self.db):
            self.check_lease(lease)
            row = self.session(session_id)
            if self.version == 2:
                self.session_packet(session_id, lease)
            require(row["status"] == "reserved", "only reserved sessions may dispatch")
            grant = self.grant()
            require(now < grant["deadline"], "campaign deadline reached")
            # Do not carry yesterday's admission into a fresh day's budget.
            require(datetime.fromtimestamp(now, timezone.utc).date().isoformat() == row["day"],
                    "reservation day changed; cancel and reserve again")
            bound = self.config["inventory"]["pools"][row["pool"]]["max_slice_wall_seconds"]
            if self.version == 2:
                identifier(job, "job ID")
                process_identity(process)
                costs = json.loads(self.session_packet(session_id, lease)["costs"])
                self.check_packet(row["purpose"], costs, now, existing=session_id)
                bound = costs["wall_seconds"]
                self.db.execute("UPDATE session_packets SET job=?, process=? WHERE session=?",
                                (job, canonical(process), session_id))
            else:
                require(job is None and process is None, "v1 does not support job identity")
            self.db.execute("UPDATE sessions SET status='active', dispatched_at=?, deadline=? WHERE id=?",
                            (now, min(now + bound, grant["deadline"]), session_id))
            audit(self.db, "session.dispatched", {"id": session_id}, now)

    def cancel_undispatched(self, session_id, now=None, *, lease=None):
        now = self.clock(now)
        with transaction(self.db):
            self.check_lease(lease)
            row = self.session(session_id)
            if self.version == 2:
                self.session_packet(session_id, lease)
            if row["status"] == "cancelled":
                return
            require(row["status"] == "reserved", "dispatched/uncertain usage cannot be cancelled")
            self.db.execute("UPDATE sessions SET status='cancelled', finished_at=? WHERE id=?", (now, session_id))
            audit(self.db, "session.cancelled_before_dispatch", {"id": session_id}, now)

    def mark_uncertain(self, session_id, now=None, *, lease=None):
        now = self.clock(now)
        with transaction(self.db):
            self.check_lease(lease)
            row = self.session(session_id)
            if self.version == 2:
                self.session_packet(session_id, lease)
            require(row["status"] in ("active", "uncertain"), "only dispatched sessions can have unknown usage")
            if row["status"] == "active":
                self.db.execute("UPDATE sessions SET status='uncertain' WHERE id=?", (session_id,))
                audit(self.db, "session.usage_unknown", {"id": session_id}, now)

    def record_exit(self, session_id, exit_code, now=None, *, lease=None):
        """Trusted supervisor must establish process exit before calling this.

        This accounting function is not proof that a process has exited. No public
        CLI exposes it; a future adapter needs process-identity/exit enforcement.
        """
        integer(exit_code, -255, 255, "exit_code")
        if self.version == 2:
            self.check_lease(lease)
            row = self.session(session_id)
            packet = dict(self.session_packet(session_id, lease))
            if row["status"] != "settled":
                require(row["status"] in ("active", "uncertain"), "only dispatched sessions may settle")
                observed = self.verify_exit("job", packet)
                require(observed == exit_code, "trusted exit observation differs")
        now = self.clock(now)
        with transaction(self.db):
            self.check_lease(lease)
            row = self.session(session_id)
            if self.version == 2:
                require(dict(self.session_packet(session_id, lease)) == packet, "job changed during verification")
            if row["status"] == "settled":
                require(row["exit_code"] == exit_code, "conflicting exit observation")
                return
            require(row["status"] in ("active", "uncertain"), "only dispatched sessions may settle")
            self.db.execute("UPDATE sessions SET status='settled', finished_at=?, exit_code=? WHERE id=?",
                            (now, exit_code, session_id))
            audit(self.db, "session.exit_observed", {"id": session_id, "exit_code": exit_code}, now)

    def check_lease(self, token):
        if self.version == 1:
            require(token is None, "v1 does not support leases")
            return
        object_keys(token, ("pool", "owner", "generation"), "lease token")
        integer(token["generation"], 1, 2**63 - 1, "lease generation")
        row = self.db.execute("SELECT * FROM leases WHERE pool=?", (self.config["pool"],)).fetchone()
        require(row is not None and all(row[k] == token[k] for k in token), "stale or foreign lease generation")

    def session_packet(self, session_id, token):
        row = self.db.execute("SELECT * FROM session_packets WHERE session=?", (session_id,)).fetchone()
        require(row is not None and row["generation"] == token["generation"], "session belongs to another lease generation")
        return row

    def packet_remaining(self):
        grant = self.grant()
        packet = json.loads(grant["allocation"])["local_packet"]
        remaining = {p: dict(packet[p]) for p in ("confirmation", "finalization")}
        remaining["exploration"] = {d: packet["campaign"][d] - sum(remaining[p][d] for p in remaining)
                                    for d in DIMENSIONS}
        for row in self.db.execute("SELECT purpose,costs FROM sessions JOIN session_packets ON id=session "
                                   "WHERE project=? AND status!='cancelled'", (grant["project"],)):
            for d, value in json.loads(row["costs"]).items():
                remaining[row["purpose"]][d] -= value
        return remaining

    def check_packet(self, purpose, costs, now, existing=None):
        grant = self.grant()
        allocation = json.loads(grant["allocation"])
        remaining = self.packet_remaining()
        if existing:
            # At dispatch the reservation is already counted. Recheck feasibility
            # including its unelapsed wall allotment, never charge it twice.
            for d in DIMENSIONS:
                remaining[purpose][d] += costs[d]
        for d in DIMENSIONS:
            require(costs[d] <= remaining[purpose][d], f"{purpose} {d} allocation exhausted")
        bound = self.config["inventory"]["pools"][grant["pool"]]["max_slice_wall_seconds"]
        require(costs["wall_seconds"] <= bound, "wall allotment exceeds slice ceiling")
        protected_workers = 0
        for protected in ("confirmation", "finalization"):
            used = self.db.execute("SELECT COUNT(*) FROM sessions WHERE project=? AND purpose=? AND status!='cancelled'",
                                   (grant["project"], protected)).fetchone()[0]
            workers_left = allocation[protected + "_slices"] - used
            if protected == purpose:
                workers_left -= 0 if existing else 1
            protected_workers += workers_left
            for d in DIMENSIONS:
                after = remaining[protected][d] - (costs[d] if protected == purpose else 0)
                require(after >= workers_left, f"remaining {protected} worker packet infeasible in {d}")
                if d == "wall_seconds":
                    require(after <= workers_left * bound,
                            f"remaining {protected} wall packet exceeds remaining worker slice ceilings")
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        account_used = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pool=? AND day=? AND status!='cancelled'",
                                       (grant["pool"], day)).fetchone()[0]
        project_used = self.db.execute("SELECT COUNT(*) FROM sessions WHERE project=? AND day=? AND status!='cancelled'",
                                       (grant["project"], day)).fetchone()[0]
        pool = self.config["inventory"]["pools"][grant["pool"]]
        today_left = min(pool["max_worker_slices_per_day"] - account_used, allocation["daily_slices"] - project_used)
        future_days = max(0, math.floor((grant["deadline"] - 1) / 86400) - math.floor(now / 86400))
        opportunities = today_left + future_days * allocation["daily_slices"]
        require(opportunities >= protected_workers + (0 if existing else 1),
                "deadline daily opportunities cannot fit remaining protected workers")
        protected_wall = sum(remaining[p]["wall_seconds"] for p in ("confirmation", "finalization"))
        needed_wall = protected_wall + (costs["wall_seconds"] if purpose == "exploration" else 0)
        require(now + needed_wall <= grant["deadline"], "deadline cannot fit remaining protected packet and operation")

    def verify_exit(self, kind, record):
        """Trusted integration seam, NOT evidence accepted from workers.

        The injected supervisor callable must verify stable host/boot/PID/start
        identity, whole-job exit and outcome using its own trusted observations.
        Return an integer exit code only once established, otherwise None. No
        default verifier exists; this module cannot prove process-tree termination.
        """
        require(callable(self.exit_verifier), "trusted supervisor exit verifier required")
        result = self.exit_verifier(kind, json.loads(canonical(record)))
        require(type(result) is int and -255 <= result <= 255, "process exit/outcome unknown; occupancy retained")
        return result

    def acquire_lease(self, owner, identity, *, now=None, lease_seconds=60):
        """Acquire/recover cooperative pool ownership; expiry never grants takeover."""
        require(self.version == 2, "leases require explicit fresh v2 configuration")
        identifier(owner, "supervisor owner")
        process_identity(identity)
        integer(lease_seconds, 1, 3600, "lease_seconds")
        now = self.clock(now)
        with transaction(self.db):
            self.grant()
            old = self.db.execute("SELECT * FROM leases WHERE pool=?", (self.config["pool"],)).fetchone()
            old = dict(old) if old else None
            pending = [dict(r) for r in self.db.execute(
                "SELECT sessions.*,session_packets.generation,session_packets.costs,session_packets.job,session_packets.process "
                "FROM sessions JOIN session_packets ON id=session WHERE pool=? AND status IN ('reserved','active','uncertain') ORDER BY id",
                (self.config["pool"],))]
            if old and old["owner"] == owner and old["identity"] == canonical(identity):
                return {k: old[k] for k in ("pool", "owner", "generation")}
        outcomes = {}
        if old:
            self.verify_exit("supervisor", old)
            for row in pending:
                if row["status"] != "reserved":
                    packet = {"session": row["id"], **{k: row[k] for k in ("generation", "costs", "job", "process")}}
                    outcomes[row["id"]] = self.verify_exit("job", packet)
        # Verifiers may block; compare the complete lease/pending snapshot again
        # under one write transaction. No partial settlements on failed recovery.
        with transaction(self.db):
            current = self.db.execute("SELECT * FROM leases WHERE pool=?", (self.config["pool"],)).fetchone()
            current = dict(current) if current else None
            current_pending = [dict(r) for r in self.db.execute(
                "SELECT sessions.*,session_packets.generation,session_packets.costs,session_packets.job,session_packets.process "
                "FROM sessions JOIN session_packets ON id=session WHERE pool=? AND status IN ('reserved','active','uncertain') ORDER BY id",
                (self.config["pool"],))]
            require(current == old and current_pending == pending, "lease/jobs changed during reconciliation; retry")
            for row in pending:
                code = outcomes.get(row["id"])
                status = "cancelled" if row["status"] == "reserved" else "settled"
                self.db.execute("UPDATE sessions SET status=?,finished_at=?,exit_code=? WHERE id=?",
                                (status, now, code, row["id"]))
                audit(self.db, "session.reconciled", {"id": row["id"], "status": status, "exit_code": code}, now)
            generation = old["generation"] + 1 if old else 1
            self.db.execute("INSERT INTO leases VALUES (?,?,?,?,?,?) ON CONFLICT(pool) DO UPDATE SET "
                            "generation=excluded.generation,owner=excluded.owner,identity=excluded.identity,"
                            "heartbeat=excluded.heartbeat,expires_at=excluded.expires_at",
                            (self.config["pool"], generation, owner, canonical(identity), now, now + lease_seconds))
            token = {"pool": self.config["pool"], "owner": owner, "generation": generation}
            audit(self.db, "lease.acquired", token, now)
            return token

    def renew_lease(self, lease, *, now=None, lease_seconds=60):
        require(self.version == 2, "leases require v2")
        integer(lease_seconds, 1, 3600, "lease_seconds")
        now = self.clock(now)
        with transaction(self.db):
            self.grant()
            self.check_lease(lease)
            self.db.execute("UPDATE leases SET heartbeat=?,expires_at=? WHERE pool=?",
                            (now, now + lease_seconds, self.config["pool"]))
            audit(self.db, "lease.renewed", lease, now)

    def status(self, now=None):
        now = self.clock(now)
        with transaction(self.db):
            return self._status(now)

    def _status(self, now):
        """Same-connection snapshot seam; caller must hold a read/write transaction."""
        require(self.db.in_transaction, "status snapshot requires transaction")
        grant = self.grant()
        allocation = json.loads(grant["allocation"])
        counts = {row[0]: row[1] for row in self.db.execute(
            "SELECT status, COUNT(*) FROM sessions WHERE project=? GROUP BY status", (grant["project"],))}
        outstanding = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pool=? AND status IN ('reserved','active','uncertain')",
                                      (grant["pool"],)).fetchone()[0]
        reserved = counts.get("reserved", 0) + counts.get("active", 0)
        uncertain, spent = counts.get("uncertain", 0), counts.get("settled", 0)
        purpose_used = {row[0]: row[1] for row in self.db.execute(
            "SELECT purpose, COUNT(*) FROM sessions WHERE project=? AND status!='cancelled' GROUP BY purpose",
            (grant["project"],))}
        remaining = {purpose: allocation[purpose + "_slices"] - purpose_used.get(purpose, 0)
                     for purpose in ("confirmation", "finalization")}
        exploration_remaining = (allocation["campaign_slices"] - allocation["confirmation_slices"]
                                 - allocation["finalization_slices"] - purpose_used.get("exploration", 0))
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        daily = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pool=? AND day=? AND status!='cancelled'",
                                (grant["pool"], day)).fetchone()[0]
        data = {"project": grant["project"], "pool": grant["pool"], "unit": "local_worker_slice",
                "authorized": allocation["campaign_slices"], "reserved": reserved, "uncertain": uncertain,
                "spent": spent, "remaining_total": allocation["campaign_slices"] - reserved - uncertain - spent,
                "protected_remaining": remaining, "available_for_exploration": exploration_remaining,
                "account_daily": {"day_utc": day, "used": daily,
                                  "limit": self.config["inventory"]["pools"][grant["pool"]]["max_worker_slices_per_day"]},
                "account_unresolved_sessions": outstanding, "deadline": grant["deadline"],
                "deadline_reached": now >= grant["deadline"], "vendor_capacity": "unknown", "live_dispatch_enabled": False}
        if self.version == 2:
            data["local_packet_remaining"] = self.packet_remaining()
            data["inference_unit"] = "local_token"
            data["accounting_only"] = True
            lease = self.db.execute("SELECT * FROM leases WHERE pool=?", (grant["pool"],)).fetchone()
            data["lease"] = dict(lease) if lease else None
            data["operations"] = []
            for row in self.db.execute(
                    "SELECT id,purpose,status,exit_code,generation,job,process,costs FROM sessions "
                    "JOIN session_packets ON id=session WHERE project=? ORDER BY id", (grant["project"],)):
                operation = dict(row)
                operation["costs"] = json.loads(operation["costs"])
                operation["worker_slices"] = 1
                data["operations"].append(operation)
        return data


def command(args):
    ledger = None
    try:
        config = resolve(args.inventory, args.policy)
        if args.resource_action == "authorize":
            # Hash check before even creating ledger/schema files.
            require(args.expected_hash == config["authorization_hash"], "approval hash does not match resolved configuration/mission")
            ledger = Ledger(config, create=True)
            grant = ledger.authorize(args.expected_hash)
            data = {key: grant[key] for key in ("project", "authorization_hash", "mission_hash", "pool", "authorized_at", "deadline")}
            data["live_dispatch_enabled"] = False
        elif args.resource_action in ("status", "budget"):
            ledger = Ledger(config)
            data = ledger.status()
        else:
            data = {"configuration_valid": True, "authorization_hash": config["authorization_hash"],
                    "mission_hash": config["mission_hash"], "pool": config["pool"],
                    "configured_route": {"provider": config["provider"], "requested_model": config["model"]},
                    "live_dispatch_enabled": False, "eligible_for_live_dispatch": False,
                    "blockers": ["native authentication/account overage not verified",
                                 "worker/credential/evaluator OS isolation not implemented",
                                 "bounded live session adapter not implemented"],
                    "vendor_capacity": "unknown"}
        print(json.dumps(data, sort_keys=True, indent=2))
    except (ResourceError, OSError, sqlite3.Error, ValueError) as exc:
        # Never echo configuration values or credential environment contents.
        raise SystemExit(f"resources: {exc}") from None
    finally:
        if ledger:
            ledger.close()


def options(parser, action):
    parser.add_argument("--inventory", type=Path, required=True, help="private operator inventory (mode 0600)")
    parser.add_argument("--policy", type=Path, required=True, help="versioned project policy")
    parser.set_defaults(func=command, resource_action=action)


def add_parsers(sub, campaigns):
    resources = sub.add_parser("resources", help="private subscription config; no inference")
    actions = resources.add_subparsers(dest="resources_cmd", required=True)
    options(actions.add_parser("validate"), "validate")
    options(actions.add_parser("status"), "status")
    budget = sub.add_parser("budget", help="private local slice ledger (not a monetary balance)")
    actions = budget.add_subparsers(dest="budget_cmd", required=True)
    options(actions.add_parser("status"), "budget")
    route = sub.add_parser("route", help="explain configured route without inference")
    actions = route.add_subparsers(dest="route_cmd", required=True)
    explain = actions.add_parser("explain")
    explain.add_argument("task", choices=("research",))
    options(explain, "explain")
    authorize = campaigns.add_parser("authorize", help="operator approval of local slice allocation only; no live dispatch")
    options(authorize, "authorize")
    authorize.add_argument("--expected-hash", required=True, help="reviewed hash from resources validate")
