#!/bin/bash
cd "$(dirname "$0")" && python3 - <<'PY'
import json, time, os, subprocess
REPOS = ["openclaw/openclaw", "deepseek-ai/deepseek-harness", "ultraworkers/claw-code"]
# picked from: gh api 'search/repositories?q=agent+harness+in:name,description,readme&sort=stars&per_page=10'
def gh(*a, raw=False):
    for i in range(4):
        r = subprocess.run(["gh", "api", *a], capture_output=True, text=True)
        if r.returncode == 0: return r.stdout
        if "429" not in r.stderr and "rate limit" not in r.stderr.lower(): raise SystemExit(r.stderr)
        time.sleep(15 * 2**i)
    raise SystemExit("giving up " + a[0])
os.makedirs("evidence", exist_ok=True)
with open("seed.jsonl", "w") as f:
    for r in REPOS:
        stars = json.loads(gh("repos/" + r))["stargazers_count"]; time.sleep(3)
        safe = r.replace("/", "_")
        open(f"evidence/{safe}.md", "w").write(gh("-H", "Accept: application/vnd.github.raw+json", f"repos/{r}/readme")); time.sleep(3)
        tree = json.loads(gh(f"repos/{r}/git/trees/HEAD?recursive=1"))["tree"]
        open(f"evidence/{safe}.tree.txt", "w").write("\n".join(t["path"] for t in tree[:400]) + "\n"); time.sleep(3)
        f.write(json.dumps({"key": r, "stars": stars, "evidence": f"evidence/{safe}.md", "tree": f"evidence/{safe}.tree.txt"}) + "\n")
PY
