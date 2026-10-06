#!/usr/bin/env python3
"""Regression tests (stdlib only). Run from agent-runner/:  python3 -m unittest discover -s tests -v"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from ledger import Ledger, LedgerError  # noqa: E402


def make_ws(limits="", seed=True, n_items=2, claim_timeout=1800):
    d = Path(tempfile.mkdtemp())
    (d / "task.md").write_text("task")
    (d / "seed.txt").write_text("".join(f"https://example.com/item/{i}\n" for i in range(n_items)))
    (d / "config.toml").write_text(f"""
[run]
backend = "custom"
{'seed_file = "seed.txt"' if seed else ''}
[limits]
{limits}
[ledger]
required_fields = ["title", "url"]
claim_timeout_seconds = {claim_timeout}
[custom]
cmd = ["{sys.executable}", "{HERE / 'fake_agent.py'}"]
prompt_via = "stdin"
""")
    return d


def run(d, *extra, mode="normal"):
    p = subprocess.run([sys.executable, str(ROOT / "run.py"), "--config", str(d / "config.toml"), *extra],
                       capture_output=True, text=True, env={**os.environ, "FAKE_MODE": mode}, timeout=120)
    return p


def last_summary(d):
    return json.loads(sorted((d / "runs").iterdir())[-1].joinpath("summary.json").read_text())


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.L = Ledger(str(Path(tempfile.mkdtemp()) / "l.db"))

    def test_transitions_require_in_progress(self):
        self.L.add("a")
        for fn in (lambda: self.L.done("a", {"x": 1}), lambda: self.L.blocked("a", "r"), lambda: self.L.not_found("a")):
            with self.assertRaises(LedgerError):
                fn()
        self.L.claim(1)
        self.L.done("a", {"x": 1})
        with self.assertRaises(LedgerError):  # terminal items are not overwritten
            self.L.blocked("a", "r")

    def test_release_in_progress(self):
        for k in "abc":
            self.L.add(k)
        self.L.claim(3)
        self.L.done("a", {})
        self.assertEqual(self.L.release_in_progress(), 2)
        self.assertEqual(self.L.stats()["counts"]["pending"], 2)

    def test_release_exhausted_attempts_fail(self):
        self.L.add("a")
        for _ in range(3):
            self.L.claim(1)
            self.L.release_in_progress()
        self.assertEqual(self.L.stats()["counts"]["failed"], 1)

    def test_add_lines_single_transaction(self):
        with self.assertRaises(Exception):
            self.L.add_lines(["k1", "k2", "{bad json"])
        self.assertEqual(self.L.stats()["total"], 0)
        self.assertEqual(self.L.add_lines(["k1", "# c", '{"key": "k2", "u": 1}']), 2)


class RunnerTests(unittest.TestCase):
    def test_zero_means_unlimited(self):
        d = make_ws("max_consecutive_failures = 0\nmax_stalled_iterations = 0\niteration_timeout_seconds = 0")
        p = run(d)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        self.assertEqual(last_summary(d)["status"], "completed")

    def test_complete_on_last_allowed_iteration(self):
        d = make_ws("max_iterations = 1")
        p = run(d)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        self.assertEqual(last_summary(d)["status"], "completed")

    def test_startup_releases_stale_claims(self):
        d = make_ws(seed=False)
        L = Ledger(str(d / "state" / "ledger.db"))
        L.add_lines(["https://example.com/item/0", "https://example.com/item/1"])
        L.meta_set("discovery_complete", "1")
        L.claim(10)  # simulate a previous run killed mid-iteration
        L.db.close()
        p = run(d)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])

    def test_dry_run_touches_nothing(self):
        d = make_ws()
        p = run(d, "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        self.assertEqual(sorted(x.name for x in d.iterdir()), ["config.toml", "seed.txt", "task.md"])


if __name__ == "__main__":
    unittest.main()
