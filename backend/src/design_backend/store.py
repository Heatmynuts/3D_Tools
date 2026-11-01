"""SQLite persistence. Versions are immutable: a new answer always creates a new
version whose parent is the current head; moving the head back never deletes
anything, it simply starts a new branch from there."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    initial_prompt TEXT NOT NULL,
    head_version_id TEXT,
    branch TEXT NOT NULL DEFAULT 'principale',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    parent_id TEXT,
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,              -- concept | plan
    label TEXT NOT NULL,
    branch TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    concept_json TEXT NOT NULL,
    next_json TEXT,                  -- pending question / checkpoint (concept versions)
    change_summary TEXT NOT NULL DEFAULT '',
    diff_json TEXT,
    plan_json TEXT,
    validated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id),
    version_id TEXT,
    role TEXT NOT NULL,              -- user | assistant | event
    kind TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    payload_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,          -- one A/B turn = one batch of candidates
    project_id TEXT NOT NULL REFERENCES projects(id),
    parent_version_id TEXT,          -- head when the batch was produced
    slot TEXT NOT NULL,              -- A | B
    label TEXT NOT NULL,
    model TEXT NOT NULL,
    position INTEGER NOT NULL,       -- display order (shuffled for blind comparison)
    ok INTEGER NOT NULL,
    error TEXT,
    turn_json TEXT,
    spec_json TEXT,
    concept_json TEXT,
    diff_json TEXT,
    input_json TEXT NOT NULL,        -- the user input both models answered
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    chosen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,             -- one model's own design thread in parallel mode
    project_id TEXT NOT NULL REFERENCES projects(id),
    slot TEXT NOT NULL,              -- A | B
    label TEXT NOT NULL,
    model TEXT NOT NULL,             -- model id requested for this thread
    fork_version_id TEXT,            -- version both threads started from
    head_version_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',   -- open | chosen | abandoned
    created_at TEXT NOT NULL,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    kind TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    ok INTEGER NOT NULL,
    error TEXT,
    response_text TEXT,
    created_at TEXT NOT NULL
);
"""

JSON_FIELDS = {"spec_json", "concept_json", "next_json", "diff_json", "plan_json", "payload_json", "turn_json",
               "input_json"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if key in JSON_FIELDS:
            out[key.removesuffix("_json")] = json.loads(value) if value else None
        else:
            out[key] = value
    return out


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        # Columns added after the first release.
        for table, col, decl in (
            ("versions", "author", "TEXT"), ("versions", "turn_id", "TEXT"),
            ("llm_calls", "turn_id", "TEXT"), ("llm_calls", "cost_usd", "REAL"),
            ("llm_calls", "cost_is_estimate", "INTEGER"), ("llm_calls", "cache_read_tokens", "INTEGER"),
            ("llm_calls", "cache_write_tokens", "INTEGER"), ("candidates", "requested_model", "TEXT"),
        ):
            if col not in {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.db.commit()
        self.lock = threading.Lock()

    # ------------------------------------------------------------ projects

    def create_project(self, title: str, prompt: str) -> str:
        pid = uuid.uuid4().hex[:12]
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO projects (id, title, initial_prompt, created_at, updated_at) VALUES (?,?,?,?,?)",
                (pid, title, prompt, _now(), _now()),
            )
        return pid

    def delete_project(self, pid: str) -> None:
        with self.lock, self.db:
            for table in ("messages", "versions", "llm_calls", "candidates"):
                self.db.execute(f"DELETE FROM {table} WHERE project_id = ?", (pid,))
            self.db.execute("DELETE FROM projects WHERE id = ?", (pid,))

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM versions v WHERE v.project_id = p.id) AS n_versions "
            "FROM projects p ORDER BY updated_at DESC"
        ).fetchall()
        return [_row(r) for r in rows]  # type: ignore[misc]

    def get_project(self, pid: str) -> dict[str, Any] | None:
        return _row(self.db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone())

    def update_project(self, pid: str, **fields: Any) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self.lock, self.db:
            self.db.execute(
                f"UPDATE projects SET {cols}, updated_at = ? WHERE id = ?", (*fields.values(), _now(), pid)
            )

    # ------------------------------------------------------------ versions

    def add_version(
        self,
        pid: str,
        parent_id: str | None,
        kind: str,
        spec: dict,
        concept: dict,
        change_summary: str = "",
        next_step: dict | None = None,
        diff: dict | None = None,
        plan: dict | None = None,
        author: str | None = None,
        turn_id: str | None = None,
        move_head: bool = True,
        branch: str | None = None,
    ) -> dict[str, Any]:
        project = self.get_project(pid)
        assert project is not None
        vid = uuid.uuid4().hex[:12]
        with self.lock, self.db:
            seq = self.db.execute(
                "SELECT COUNT(*) FROM versions WHERE project_id = ? AND kind = ?", (pid, kind)
            ).fetchone()[0]
            label = f"Concept V{seq}" if kind == "concept" else f"Plan v{seq + 1}"
            self.db.execute(
                "INSERT INTO versions (id, project_id, parent_id, seq, kind, label, branch, spec_json, concept_json,"
                " next_json, change_summary, diff_json, plan_json, author, turn_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    vid, pid, parent_id, seq, kind, label, branch or project["branch"],
                    json.dumps(spec, ensure_ascii=False), json.dumps(concept, ensure_ascii=False),
                    json.dumps(next_step, ensure_ascii=False) if next_step else None,
                    change_summary,
                    json.dumps(diff) if diff else None,
                    json.dumps(plan, ensure_ascii=False) if plan else None,
                    author,
                    turn_id,
                    _now(),
                ),
            )
            if move_head:
                self.db.execute(
                    "UPDATE projects SET head_version_id = ?, updated_at = ? WHERE id = ?", (vid, _now(), pid)
                )
            else:
                self.db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (_now(), pid))
        return self.get_version(vid)  # type: ignore[return-value]

    def get_version(self, vid: str) -> dict[str, Any] | None:
        return _row(self.db.execute("SELECT * FROM versions WHERE id = ?", (vid,)).fetchone())

    def list_versions(self, pid: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, parent_id, seq, kind, label, branch, change_summary, validated, created_at, diff_json, author "
            "FROM versions WHERE project_id = ? ORDER BY created_at, rowid",
            (pid,),
        ).fetchall()
        return [_row(r) for r in rows]  # type: ignore[misc]

    def set_validated(self, vid: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE versions SET validated = 1 WHERE id = ?", (vid,))

    def lineage(self, vid: str | None) -> list[dict[str, Any]]:
        """Versions from root to `vid` (inclusive)."""
        chain: list[dict[str, Any]] = []
        while vid:
            v = self.get_version(vid)
            if v is None:
                break
            chain.append(v)
            vid = v["parent_id"]
        return list(reversed(chain))

    # ------------------------------------------------------------ messages

    def add_message(
        self, pid: str, version_id: str | None, role: str, kind: str, text: str, payload: dict | None = None
    ) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO messages (project_id, version_id, role, kind, text, payload_json, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (pid, version_id, role, kind, text, json.dumps(payload, ensure_ascii=False) if payload else None, _now()),
            )

    def messages_for(self, pid: str, version_ids: list[str]) -> list[dict[str, Any]]:
        if not version_ids:
            return []
        marks = ",".join("?" * len(version_ids))
        rows = self.db.execute(
            f"SELECT * FROM messages WHERE project_id = ? AND version_id IN ({marks}) ORDER BY id",
            (pid, *version_ids),
        ).fetchall()
        return [_row(r) for r in rows]  # type: ignore[misc]

    # ------------------------------------------------------------ A/B candidates

    def add_candidate(self, **c: Any) -> None:
        for key in ("turn", "spec", "concept", "diff", "input"):
            c[f"{key}_json"] = json.dumps(c.pop(key), ensure_ascii=False) if c.get(key) is not None else None
        c.setdefault("created_at", _now())
        cols = ", ".join(c)
        with self.lock, self.db:
            self.db.execute(f"INSERT INTO candidates ({cols}) VALUES ({','.join('?' * len(c))})", tuple(c.values()))

    def get_candidate(self, cid: str) -> dict[str, Any] | None:
        return _row(self.db.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone())

    def pending_batch(self, pid: str, parent_version_id: str | None) -> list[dict[str, Any]]:
        """Latest unresolved batch produced from the given head (empty if none)."""
        row = self.db.execute(
            "SELECT batch_id FROM candidates WHERE project_id = ? AND parent_version_id IS ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (pid, parent_version_id),
        ).fetchone()
        if row is None:
            return []
        rows = self.db.execute(
            "SELECT * FROM candidates WHERE batch_id = ? ORDER BY position", (row[0],)
        ).fetchall()
        batch = [_row(r) for r in rows]
        return [] if any(c["chosen"] for c in batch) else batch  # type: ignore[index]

    def mark_chosen(self, cid: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE candidates SET chosen = 1 WHERE id = ?", (cid,))

    def mark_batch_parallel(self, batch_id: str) -> None:
        """Both proposals continue as parallel threads (not a choice: excluded from A/B picks)."""
        with self.lock, self.db:
            self.db.execute("UPDATE candidates SET chosen = 2 WHERE batch_id = ?", (batch_id,))

    # ------------------------------------------------------------ parallel threads

    def add_track(self, pid: str, slot: str, label: str, model: str, fork_version_id: str | None,
                  head_version_id: str) -> str:
        tid = uuid.uuid4().hex[:12]
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO tracks (id, project_id, slot, label, model, fork_version_id, head_version_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (tid, pid, slot, label, model, fork_version_id, head_version_id, _now()),
            )
        return tid

    def get_track(self, tid: str) -> dict[str, Any] | None:
        return _row(self.db.execute("SELECT * FROM tracks WHERE id = ?", (tid,)).fetchone())

    def open_tracks(self, pid: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM tracks WHERE project_id = ? AND status = 'open' ORDER BY slot", (pid,)).fetchall()
        return [_row(r) for r in rows]  # type: ignore[misc]

    def set_track_head(self, tid: str, vid: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE tracks SET head_version_id = ? WHERE id = ?", (vid, tid))

    def close_tracks(self, pid: str, chosen_tid: str | None) -> None:
        with self.lock, self.db:
            self.db.execute(
                "UPDATE tracks SET status = CASE WHEN id = ? THEN 'chosen' ELSE 'abandoned' END, closed_at = ?"
                " WHERE project_id = ? AND status = 'open'", (chosen_tid, _now(), pid))

    def track_stats(self, pid: str | None = None) -> list[dict[str, Any]]:
        where, args = ("WHERE status != 'open'", ())
        if pid:
            where, args = ("WHERE status != 'open' AND project_id = ?", (pid,))
        rows = self.db.execute(
            f"SELECT label, COUNT(*) AS threads, SUM(status = 'chosen') AS chosen FROM tracks {where} GROUP BY label",
            args).fetchall()
        return [dict(r) for r in rows]

    def discard_batch(self, batch_id: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE candidates SET chosen = -1 WHERE batch_id = ? AND chosen = 0", (batch_id,))

    def ab_stats(self, pid: str | None = None) -> list[dict[str, Any]]:
        """Per-model tally over resolved batches (a batch counts once a candidate was chosen)."""
        where = "WHERE batch_id IN (SELECT batch_id FROM candidates WHERE chosen = 1)"
        args: tuple = ()
        if pid:
            where += " AND project_id = ?"
            args = (pid,)
        rows = self.db.execute(
            f"SELECT label, model, COUNT(*) AS proposed, SUM(chosen = 1) AS chosen, SUM(ok = 0) AS failed, "
            f"CAST(AVG(CASE WHEN ok = 1 THEN latency_ms END) AS INTEGER) AS avg_latency_ms, "
            f"CAST(AVG(CASE WHEN ok = 1 THEN output_tokens END) AS INTEGER) AS avg_output_tokens "
            f"FROM candidates {where} GROUP BY label, model ORDER BY label",
            args,
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ llm log

    def log_llm_call(self, pid: str | None, kind: str, provider: str, model: str, *, ok: bool,
                     latency_ms: int | None = None, input_tokens: int | None = None,
                     output_tokens: int | None = None, error: str | None = None,
                     response_text: str | None = None, turn_id: str | None = None,
                     cost_usd: float | None = None, cost_is_estimate: bool = False,
                     cache_read_tokens: int | None = None, cache_write_tokens: int | None = None) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO llm_calls (project_id, kind, provider, model, latency_ms, input_tokens, output_tokens,"
                " ok, error, response_text, created_at, turn_id, cost_usd, cost_is_estimate, cache_read_tokens,"
                " cache_write_tokens) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, kind, provider, model, latency_ms, input_tokens, output_tokens, int(ok), error,
                 response_text, _now(), turn_id, cost_usd, int(cost_is_estimate), cache_read_tokens,
                 cache_write_tokens),
            )

    def usage(self, pid: str) -> dict[str, Any]:
        """LLM spend of a project, per step (one interview turn, A/B turn or plan) and per model."""
        calls = [dict(r) for r in self.db.execute(
            "SELECT turn_id, kind, provider, model, ok, latency_ms, input_tokens, output_tokens, cache_read_tokens,"
            " cost_usd, cost_is_estimate, created_at FROM llm_calls WHERE project_id = ? ORDER BY id", (pid,))]
        labels = {r[0]: (r[1], r[2]) for r in self.db.execute(
            "SELECT turn_id, label, author FROM versions WHERE project_id = ? AND turn_id IS NOT NULL", (pid,))}
        steps: dict[str, dict[str, Any]] = {}
        for c in calls:
            key = c["turn_id"] or f"hors-étape-{c['created_at']}"
            label, author = labels.get(c["turn_id"], (None, None))
            step = steps.setdefault(key, {
                "turn_id": c["turn_id"], "label": label, "kept": author, "phase": "CAO" if c["kind"] == "cad" else "Plan" if c["kind"] == "plan" else "Concept",
                "started_at": c["created_at"], "cost_usd": 0.0, "estimate": False, "calls": 0, "repairs": 0,
                "failed": 0, "by_model": {},
            })
            if c["kind"] == "plan":
                step["phase"] = "Plan"
            step["calls"] += 1
            step["repairs"] += c["kind"] == "repair"
            step["failed"] += not c["ok"]
            m = step["by_model"].setdefault(c["model"], {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0,
                                                         "cache_read_tokens": 0, "unpriced": 0})
            if c["cost_usd"] is None:
                m["unpriced"] += c["ok"]
            else:
                m["cost_usd"] += c["cost_usd"]
                step["cost_usd"] += c["cost_usd"]
            step["estimate"] |= bool(c["cost_is_estimate"])
            for k in ("input_tokens", "output_tokens", "cache_read_tokens"):
                m[k] += c[k] or 0
        for s in steps.values():
            if s["label"] is None:
                s["label"] = "Tour comparé non retenu" if s["phase"] == "Concept" else ("CAO" if s["phase"] == "CAO" else "Plan (non enregistré)")
        by_model: dict[str, float] = {}
        by_phase: dict[str, float] = {}
        for s in steps.values():
            by_phase[s["phase"]] = by_phase.get(s["phase"], 0.0) + s["cost_usd"]
            for model, m in s["by_model"].items():
                by_model[model] = by_model.get(model, 0.0) + m["cost_usd"]
        return {"steps": list(steps.values()), "by_model": by_model, "by_phase": by_phase,
                "total_usd": sum(by_phase.values())}

    def spend_since(self, provider: str, since_iso: str) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE provider = ? AND created_at >= ?",
            (provider, since_iso)).fetchone()
        return float(row[0])

    # ------------------------------------------------------------ duplication

    def duplicate(self, pid: str, upto_version_id: str) -> str:
        """Copy a project's lineage up to a version into a new, independent project."""
        project = self.get_project(pid)
        assert project is not None
        chain = self.lineage(upto_version_id)
        new_pid = self.create_project(f"{project['title']} (copie)", project["initial_prompt"])
        id_map: dict[str, str] = {}
        for v in chain:
            nv = self.add_version(
                new_pid, id_map.get(v["parent_id"]) if v["parent_id"] else None, v["kind"], v["spec"], v["concept"],
                v["change_summary"], v["next"], v["diff"], v["plan"], v.get("author"),
            )
            if v["validated"]:
                self.set_validated(nv["id"])
            id_map[v["id"]] = nv["id"]
            for m in self.messages_for(pid, [v["id"]]):
                self.add_message(new_pid, nv["id"], m["role"], m["kind"], m["text"], m["payload"])
        return new_pid
