#!/usr/bin/env python3
"""Stand-in for a coding CLI, used to test run.py without any API. Reads the prompt on stdin
and drives ledger.py exactly like a real agent would. Behaviour via FAKE_MODE:
  normal  - discovery (3 pages x 4 items) then process batches
  stall   - does nothing
  crash   - exits 1
  slow    - sleeps 60s (to test timeouts)
  failall - normal discovery, then `fail` on every claimed item
  abort   - claims items, then reports a broken environment via `abort`
  tokens  - normal, but prints claude-style JSON usage (800 tokens per call) to test token limits
"""
import json, os, subprocess, sys

mode = os.environ.get("FAKE_MODE", "normal")
prompt = sys.stdin.read()
LEDGER = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "ledger.py")]


def L(*a):
    p = subprocess.run(LEDGER + list(a), capture_output=True, text=True)
    return json.loads(p.stdout) if p.stdout.strip() else {"err": p.stderr}


def emit(text):
    if mode == "tokens":
        print(json.dumps({"result": text, "is_error": False, "total_cost_usd": 0.05,
                          "usage": {"input_tokens": 500, "output_tokens": 300}}))
    else:
        print(text)


if mode == "crash":
    print("boom", file=sys.stderr); sys.exit(1)
if mode == "slow":
    import time; time.sleep(60)
if mode == "abort":
    L("claim", "5"); L("abort", "--reason", "pdftoppm missing"); emit("aborted"); sys.exit(0)
if mode == "stall":
    emit("did nothing"); sys.exit(0)

stats = L("stats")
if not stats["discovery_complete"]:
    cur = int(stats["meta"].get("discovery_cursor", "0"))
    for i in range(cur * 4, cur * 4 + 4):
        L("add", f"https://example.com/item/{i}")
    L("meta-set", "discovery_cursor", str(cur + 1))
    if cur + 1 >= 3:
        L("set-expected", "12"); L("discovery-complete")
    emit(f"discovered page {cur + 1}")
else:
    items = L("claim", "5")["items"]
    for it in items:
        k = it["key"]
        os.makedirs("evidence", exist_ok=True)
        ev = "evidence/" + k.rsplit("/", 1)[1] + ".html"
        open(ev, "w").write("<html>fake</html>")
        if mode == "failall":
            L("fail", k, "--error", "nope")
        elif k.endswith("/7"):
            L("blocked", k, "--reason", "403 forbidden")
        elif k.endswith("/9"):
            # first attempt: forget a required field, ledger must reject it
            r = subprocess.run(LEDGER + ["done", k, "--result", json.dumps({"title": "x"}), "--evidence", ev], capture_output=True, text=True)
            assert r.returncode == 2, "ledger should reject missing url"
            L("done", k, "--result", json.dumps({"title": "Item 9", "url": k}), "--evidence", ev)
        else:
            L("done", k, "--result", json.dumps({"title": "Item " + k.rsplit("/", 1)[1], "url": k}), "--evidence", ev)
    emit(f"processed {len(items)} items")
