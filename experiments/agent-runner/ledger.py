#!/usr/bin/env python3
"""Tiny SQLite ledger: the single source of truth for "what has been done".

Why this exists: an LLM saying "I covered everything" is not evidence. The ledger
makes completeness mechanically checkable (no pending items, discovery marked
complete, counts match the site's own total, every result has required fields).

Used two ways:
  * as a CLI by CLI agents (claude / codex / opencode):  python3 ledger.py claim 10
  * as a library by run.py (and by the built-in API backend's tools)

Config via environment (run.py sets these for the agent subprocess):
  LEDGER_DB               path to the sqlite file            (default state/ledger.db)
  LEDGER_MAX_ATTEMPTS     attempts before an item is failed  (default 3)
  LEDGER_REQUIRED_FIELDS  comma list; `done` is rejected if any is missing/empty
  LEDGER_REQUIRE_EVIDENCE 1 = `done` must carry an existing --evidence file
  LEDGER_CLAIM_TIMEOUT    seconds before an abandoned claim is released (1800)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

TERMINAL = ("done", "failed", "blocked", "not_found")
STATUSES = ("pending", "in_progress") + TERMINAL

SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  key        TEXT PRIMARY KEY,
  payload    TEXT,
  status     TEXT NOT NULL DEFAULT 'pending',
  attempts   INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  result     TEXT,
  evidence   TEXT,
  claimed_at REAL,
  updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


class LedgerError(Exception):
    """Raised for caller mistakes (bad key, missing fields...). Message is meant to be read by the agent."""


class Ledger:
    def __init__(self, path=None, max_attempts=None, required_fields=None, claim_timeout=None):
        self.path = path or os.environ.get("LEDGER_DB", "state/ledger.db")
        self.max_attempts = int(max_attempts or os.environ.get("LEDGER_MAX_ATTEMPTS", 3))
        rf = required_fields if required_fields is not None else os.environ.get("LEDGER_REQUIRED_FIELDS", "")
        if isinstance(rf, str):
            rf = [x.strip() for x in rf.split(",") if x.strip()]
        self.required = list(rf)
        self.claim_timeout = int(claim_timeout or os.environ.get("LEDGER_CLAIM_TIMEOUT", 1800))
        self.require_evidence = os.environ.get("LEDGER_REQUIRE_EVIDENCE", "0") == "1"
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    # ---- plumbing -------------------------------------------------------
    @contextlib.contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def _get(self, key):
        row = self.db.execute("SELECT * FROM items WHERE key=?", (key,)).fetchone()
        if row is None:
            raise LedgerError(f"unknown key: {key!r} (use `add` first)")
        return row

    # ---- writes ---------------------------------------------------------
    def _add(self, key, payload=None) -> bool:
        key = str(key).strip()
        if not key:
            raise LedgerError("empty key")
        cur = self.db.execute(
            "INSERT OR IGNORE INTO items(key,payload,updated_at) VALUES(?,?,?)",
            (key, json.dumps(payload, ensure_ascii=False) if payload is not None else None, time.time()),
        )
        return cur.rowcount == 1

    def add(self, key, payload=None) -> bool:
        with self._tx():
            return self._add(key, payload)

    def add_lines(self, lines) -> int:
        """Each line is a bare key, or a JSON object with a "key" field (rest becomes payload)."""
        n = 0
        with self._tx():  # one transaction for the whole batch (all-or-nothing)
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("{"):
                    obj = json.loads(line)
                    key = obj.pop("key")
                    n += self._add(key, obj or None)
                else:
                    n += self._add(line)
        return n

    def release_in_progress(self) -> int:
        """Give back every in_progress item (attempts exhausted -> failed). Only call when no agent can be running
        (run.py holds the runner lock, so after startup or after an iteration has ended this is safe)."""
        now = time.time()
        with self._tx():
            self.db.execute(
                "UPDATE items SET status='failed', last_error='interrupted, attempts exhausted', updated_at=? "
                "WHERE status='in_progress' AND attempts>=?", (now, self.max_attempts))
            return self.db.execute(
                "UPDATE items SET status='pending', updated_at=? WHERE status='in_progress'", (now,)).rowcount

    def _require_in_progress(self, key):
        row = self._get(key)
        if row["status"] != "in_progress":
            raise LedgerError(f"{key!r} is {row['status']}, not in_progress (claim it first; finished items cannot be changed)")

    def claim(self, n=10):
        """Take up to n pending items. Claiming counts as an attempt, so a poison item that
        crashes the agent every time cannot loop forever."""
        now = time.time()
        with self._tx():
            stale = self.db.execute(
                "SELECT key, attempts FROM items WHERE status='in_progress' AND claimed_at < ?",
                (now - self.claim_timeout,),
            ).fetchall()
            for r in stale:
                if r["attempts"] >= self.max_attempts:
                    self.db.execute(
                        "UPDATE items SET status='failed', last_error='claim timed out, attempts exhausted', updated_at=? WHERE key=?",
                        (now, r["key"]),
                    )
                else:
                    self.db.execute("UPDATE items SET status='pending', updated_at=? WHERE key=?", (now, r["key"]))
            rows = self.db.execute(
                "SELECT key,payload,attempts,last_error FROM items WHERE status='pending' ORDER BY rowid LIMIT ?",
                (int(n),),
            ).fetchall()
            out = []
            for r in rows:
                self.db.execute(
                    "UPDATE items SET status='in_progress', attempts=attempts+1, claimed_at=?, updated_at=? WHERE key=?",
                    (now, now, r["key"]),
                )
                out.append(
                    {
                        "key": r["key"],
                        "payload": json.loads(r["payload"]) if r["payload"] else None,
                        "attempt": r["attempts"] + 1,
                        "last_error": r["last_error"],
                    }
                )
            return out

    def done(self, key, result, evidence=None):
        if not isinstance(result, dict):
            raise LedgerError("result must be a JSON object")
        missing = [f for f in self.required if result.get(f) in (None, "", [], {})]
        if missing:
            raise LedgerError(f"missing/empty required fields: {missing}. Fix the result and call done again.")
        if evidence:
            if not Path(evidence).exists():
                raise LedgerError(f"evidence file does not exist: {evidence}")
        elif self.require_evidence:
            raise LedgerError("evidence is required: save the raw page to ./evidence/ and pass --evidence PATH")
        with self._tx():
            self._require_in_progress(key)
            self.db.execute(
                "UPDATE items SET status='done', result=?, evidence=?, last_error=NULL, updated_at=? WHERE key=?",
                (json.dumps(result, ensure_ascii=False), evidence, time.time(), key),
            )

    def fail(self, key, error):
        """Retryable failure. Becomes terminal `failed` once attempts are exhausted."""
        with self._tx():
            row = self._get(key)
            status = "failed" if row["attempts"] >= self.max_attempts else "pending"
            self.db.execute(
                "UPDATE items SET status=?, last_error=?, updated_at=? WHERE key=?",
                (status, str(error)[:1000], time.time(), key),
            )
        return status

    def _terminal(self, key, status, reason):
        with self._tx():
            self._require_in_progress(key)
            self.db.execute(
                "UPDATE items SET status=?, last_error=?, updated_at=? WHERE key=?",
                (status, str(reason)[:1000], time.time(), key),
            )

    def blocked(self, key, reason):
        self._terminal(key, "blocked", reason)

    def not_found(self, key, reason="not found on site"):
        self._terminal(key, "not_found", reason)

    # ---- meta -----------------------------------------------------------
    def abort(self, reason):
        """The environment is broken, so no item can succeed (missing tool, no network, bad auth). Stops the run without
        burning attempts: claims made this batch are handed back and refunded. run.py clears the flag on its next start."""
        now = time.time()
        with self._tx():
            self.db.execute("UPDATE items SET status='pending', attempts=MAX(attempts-1,0), updated_at=? WHERE status='in_progress'", (now,))
            self.db.execute("INSERT INTO meta(key,value) VALUES('abort_reason',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (reason,))

    def meta_set(self, k, v):
        with self._tx():
            self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))

    def meta_get(self, k, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (k,)).fetchone()
        return row["value"] if row else default

    # ---- reads ----------------------------------------------------------
    def stats(self):
        counts = {s: 0 for s in STATUSES}
        for r in self.db.execute("SELECT status, COUNT(*) c FROM items GROUP BY status"):
            counts[r["status"]] = r["c"]
        meta = {r["key"]: r["value"] for r in self.db.execute("SELECT key,value FROM meta")}
        exp = meta.get("expected_total")
        return {
            "total": sum(counts.values()),
            "counts": counts,
            "terminal": sum(counts[s] for s in TERMINAL),
            "discovery_complete": meta.get("discovery_complete") == "1",
            "expected_total": int(exp) if exp and exp.isdigit() else None,
            "meta": meta,
        }

    def check(self, tolerance_pct=0.0):
        """Mechanical completeness check. complete == True only if every reason below is clear."""
        s = self.stats()
        reasons = []
        if s["total"] == 0:
            reasons.append("ledger is empty")
        if not s["discovery_complete"]:
            reasons.append("discovery not marked complete (run `discovery-complete` after enumeration is exhaustive)")
        open_n = s["counts"]["pending"] + s["counts"]["in_progress"]
        if open_n:
            reasons.append(f"{open_n} items still pending/in_progress")
        exp = s["expected_total"]
        if exp and s["total"] < exp * (1 - tolerance_pct / 100.0):
            reasons.append(f"only {s['total']} items listed but site reports {exp} (tolerance {tolerance_pct}%)")
        return {"complete": not reasons, "reasons": reasons}

    def rows(self, statuses):
        q = ",".join("?" * len(statuses))
        return self.db.execute(f"SELECT * FROM items WHERE status IN ({q}) ORDER BY rowid", tuple(statuses)).fetchall()

    def export_jsonl(self, path, statuses=("done",)):
        n = 0
        with open(path, "w", encoding="utf-8") as f:
            for r in self.rows(statuses):
                rec = {"key": r["key"], "status": r["status"], "attempts": r["attempts"], "evidence": r["evidence"]}
                rec["result"] = json.loads(r["result"]) if r["result"] else None
                if r["status"] != "done":
                    rec["reason"] = r["last_error"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
        return n


# ---------------------------------------------------------------------------
def _json_arg(s):
    if s.startswith("@"):
        return json.loads(Path(s[1:]).read_text(encoding="utf-8"))
    return json.loads(s)


def main(argv=None):
    ap = argparse.ArgumentParser(description="progress ledger")
    ap.add_argument("--db", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add"); p.add_argument("key"); p.add_argument("--payload")
    p = sub.add_parser("add-file"); p.add_argument("file")
    p = sub.add_parser("claim"); p.add_argument("n", nargs="?", type=int, default=10)
    p = sub.add_parser("done"); p.add_argument("key"); p.add_argument("--result", required=True); p.add_argument("--evidence")
    p = sub.add_parser("fail"); p.add_argument("key"); p.add_argument("--error", required=True)
    p = sub.add_parser("blocked"); p.add_argument("key"); p.add_argument("--reason", required=True)
    p = sub.add_parser("not-found"); p.add_argument("key"); p.add_argument("--reason", default="not found on site")
    p = sub.add_parser("abort"); p.add_argument("--reason", required=True)
    sub.add_parser("stats")
    p = sub.add_parser("check"); p.add_argument("--tolerance-pct", type=float, default=0.0)
    p = sub.add_parser("meta-set"); p.add_argument("key"); p.add_argument("value")
    p = sub.add_parser("meta-get"); p.add_argument("key")
    sub.add_parser("discovery-complete")
    p = sub.add_parser("set-expected"); p.add_argument("n", type=int)
    p = sub.add_parser("export"); p.add_argument("--out", required=True); p.add_argument("--all", action="store_true")

    a = ap.parse_args(argv)
    try:
        L = Ledger(a.db)
        if a.cmd == "add":
            out = {"added": L.add(a.key, json.loads(a.payload) if a.payload else None)}
        elif a.cmd == "add-file":
            out = {"added": L.add_lines(Path(a.file).read_text(encoding="utf-8").splitlines())}
        elif a.cmd == "claim":
            out = {"items": L.claim(a.n)}
        elif a.cmd == "done":
            L.done(a.key, _json_arg(a.result), a.evidence); out = {"ok": True}
        elif a.cmd == "fail":
            out = {"status": L.fail(a.key, a.error)}
        elif a.cmd == "blocked":
            L.blocked(a.key, a.reason); out = {"ok": True}
        elif a.cmd == "not-found":
            L.not_found(a.key, a.reason); out = {"ok": True}
        elif a.cmd == "abort":
            L.abort(a.reason); out = {"ok": True}
        elif a.cmd == "stats":
            out = L.stats()
        elif a.cmd == "check":
            out = L.check(a.tolerance_pct)
            print(json.dumps(out, ensure_ascii=False))
            return 0 if out["complete"] else 1
        elif a.cmd == "meta-set":
            L.meta_set(a.key, a.value); out = {"ok": True}
        elif a.cmd == "meta-get":
            out = {a.key: L.meta_get(a.key)}
        elif a.cmd == "discovery-complete":
            L.meta_set("discovery_complete", "1"); out = {"ok": True}
        elif a.cmd == "set-expected":
            L.meta_set("expected_total", a.n); out = {"ok": True}
        elif a.cmd == "export":
            out = {"written": L.export_jsonl(a.out, STATUSES if a.all else ("done",))}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except (LedgerError, json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        print(f"ledger error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
