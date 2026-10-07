#!/bin/bash
# usage: bash prep.sh ; python3 stdlib only
cd "$(dirname "$0")" && python3 - <<'PY'
import re, json, time, os, urllib.request, urllib.error
from html.parser import HTMLParser
class T(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "br", "div", "tr"}
    def __init__(s): super().__init__(); s.o = []; s.skip = 0; s.title = ""; s.in_title = False
    def handle_starttag(s, t, a):
        if t in s.SKIP: s.skip += 1
        if t == "title": s.in_title = True
        if t in s.BLOCK: s.o.append("\n")
    def handle_endtag(s, t):
        if t in s.SKIP and s.skip: s.skip -= 1
        if t == "title": s.in_title = False
        if t in s.BLOCK: s.o.append("\n")
    def handle_data(s, d):
        if s.in_title: s.title += d
        elif not s.skip: s.o.append(d)
def totext(h):
    p = T(); p.feed(h)
    lines = (re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in "".join(p.o).split("\n"))
    return " ".join(p.title.split()) + "\n" + "\n".join(l for l in lines if l) + "\n"
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
        html = get(u); open(ev, "w").write(html); time.sleep(3)
        tx = ev[:-5] + ".txt"; open(tx, "w").write(totext(html))
        f.write(json.dumps({"key": u, "source": src, "evidence": ev, "text": tx}) + "\n")
PY
