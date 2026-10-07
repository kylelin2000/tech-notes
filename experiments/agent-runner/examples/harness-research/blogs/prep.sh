#!/bin/bash
# usage: bash prep.sh ; python3 stdlib only
cd "$(dirname "$0")" && python3 - <<'PY'
import re, json, time, os, urllib.request, urllib.error
UA = "harness-research-prep/0.1 (+https://github.com/kylelin2000/tech-notes)"
def get(u):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode()
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(10 * 2**i)
    raise SystemExit("429 giving up " + u)
os.makedirs("evidence", exist_ok=True)
idx = get("https://www.anthropic.com/engineering"); time.sleep(3)
slugs = list(dict.fromkeys(re.findall(r'/engineering/([a-z0-9-]+)', idx)))[:2]  # index order = newest first
items = [("https://www.anthropic.com/engineering/" + s, "anthropic-engineering") for s in slugs]
feed = get("https://simonwillison.net/tags/ai-agents.atom"); time.sleep(3)
# fixed pick: substantive (non-"Quoting") entry from the feed
items.append(("https://simonwillison.net/2026/Jan/25/the-browser-is-the-sandbox/", "simonwillison"))
assert items[-1][0] in feed
with open("seed.jsonl", "w") as f:
    for u, src in items:
        ev = "evidence/" + re.sub(r'[/:]', '_', u) + ".html"
        open(ev, "w").write(get(u)); time.sleep(3)
        f.write(json.dumps({"key": u, "source": src, "evidence": ev}) + "\n")
PY
