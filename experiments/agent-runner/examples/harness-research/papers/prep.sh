#!/bin/bash
cd "$(dirname "$0")" && python3 - <<'PY'
import json, time, os, re, subprocess, urllib.request, urllib.error, urllib.parse
UA = "harness-research-prep/0.1 (+https://github.com/kylelin2000/tech-notes)"
def get(u, raw=False):
    for i in range(6):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(30 * 2**i)
    raise SystemExit("429 giving up " + u)
# s2_search.json = saved S2 /paper/search?query=LLM+agent+harness&fields=title,year,citationCount,externalIds,venue&limit=100 (429-prone)
# Chosen by hand from S2 search "LLM agent harness" (ArXiv-id'd, clearly harness papers, top by citationCount;
# skipped SkillsBench 291 and HAL 89: benchmarks, not harness design)
IDS = ["2606.09498", "2604.08224", "2605.27922"]
os.makedirs("evidence", exist_ok=True)
if not os.path.exists("s2_search.json"):  # cached: unauthenticated S2 is 429-prone
    json.dump(get("https://api.semanticscholar.org/graph/v1/paper/search?query=LLM+agent+harness&fields=title,year,citationCount,externalIds,venue&limit=100"), open("s2_search.json", "w"))
    time.sleep(4)
S2 = {x["externalIds"]["ArXiv"]: x for x in json.load(open("s2_search.json"))["data"] if "ArXiv" in (x.get("externalIds") or {})}
norm = lambda s: re.sub(r'\W+', ' ', s).lower().strip()
with open("seed.jsonl", "w") as f:
    for a in IDS:
        p = S2[a]
        safe = re.sub(r'[/:]', '_', a); ev = f"evidence/{safe}.pdf"
        open(ev, "wb").write(get(f"https://arxiv.org/pdf/{a}", raw=True)); time.sleep(4)
        item = {"key": a, "citations": p["citationCount"], "evidence": ev}
        q = urllib.parse.urlencode({"term": p["title"], "source": "forum", "limit": 10})
        for n in get("https://api2.openreview.net/notes/search?" + q)["notes"]:
            if norm(n["content"]["title"]["value"]) == norm(p["title"]) and n["id"] == n["forum"]:
                time.sleep(3)
                try: notes = get("https://api2.openreview.net/notes?forum=" + n["id"] + "&limit=1000")["notes"]
                except urllib.error.HTTPError as e: print("openreview replies blocked", e.code, n["id"]); break  # 403 = bot challenge; not bypassed
                if len(notes) > 1:  # DBLP-imported stubs have only the paper note, no replies
                    rv = f"evidence/{safe}.reviews.json"; json.dump(notes, open(rv, "w"), indent=1); item["reviews"] = rv; break
        time.sleep(3)
        f.write(json.dumps(item) + "\n")
PY
