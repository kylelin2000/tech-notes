#!/bin/bash
# usage: LIMIT=N bash prep.sh  (rerun to resume after a 429; ~45 s per video) ; python3 stdlib only + yt-dlp (no cookies, no bot-check bypass)
cd "$(dirname "$0")" && python3 - <<'PY'
import re, json, time, os, glob, subprocess
NOTE = "../../../../../ai-agents/concepts/harness-engineering.md"
sec = open(NOTE, encoding="utf8").read().split("## 待讀清單", 1)[1]
items, prio = [], ""
for ln in sec.splitlines():
    if ln.startswith("### "): prio = re.sub(r"[（(].*", "", ln[4:]).strip(); continue
    ls = list(re.finditer(r"\[[^\]]*\]\(https://www\.youtube\.com/watch\?v=([\w-]+)\)", ln))
    if not ls: continue
    hint = ln[ls[-1].end():].lstrip("：").strip()
    items += [(m.group(1), hint, prio) for m in ls]
print(len(items), "entries:", " ".join(i[0] for i in items))
items = items[:int(os.environ.get("LIMIT") or len(items))]

def vtt2txt(path):
    tsre = re.compile(r"(?:(\d+):)?(\d+):(\d+)\.\d+ --> ")
    out, last, nextmark, cur = [], [], 0, 0
    for ln in open(path, encoding="utf8"):
        ln = ln.rstrip("\n"); m = tsre.match(ln)
        if m:
            h, mi, s = m.groups(); cur = int(h or 0) * 3600 + int(mi) * 60 + int(s); continue
        if not ln.strip() or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")): continue
        t = re.sub(r"<[^>]+>", "", ln).replace("&nbsp;", " ").replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").strip()
        if not t or t in last[-3:]: continue  # rolling auto-captions repeat lines
        last.append(t)
        if cur >= nextmark:
            out.append(f"[{cur//60:02d}:{cur%60:02d}]"); nextmark = cur - cur % 60 + 60
        out.append(t)
    return "\n".join(out) + "\n"

os.makedirs("evidence", exist_ok=True)
stop = None
for n, (v, hint, prio) in enumerate(items):
    if os.path.exists(f"evidence/{v}.txt"): continue
    if n: time.sleep(30)  # YouTube 429s the subtitle endpoint quickly
    YT = ["yt-dlp", "--skip-download", "-o", "evidence/%(id)s.%(ext)s"]
    BLOCK = r"Sign in|not a bot|HTTP Error 429|Too Many Requests"
    r = subprocess.run(YT + ["--write-info-json", "https://www.youtube.com/watch?v=" + v], capture_output=True, text=True)  # metadata only
    if re.search(BLOCK, r.stderr):
        stop = f"STOP at {v}: YouTube is blocking (sign-in/bot check/429). Not bypassing; rerun later. Done items kept."; break
    try: info = json.load(open(f"evidence/{v}.info.json"))
    except OSError: print("WARN", v, "yt-dlp failed:", r.stderr.strip()[-200:]); continue
    subs, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    man = [k for k in subs if k == "en" or k.startswith("en-")]
    lang = "en" if "en" in man else man[0] if man else None
    flag = "--write-subs"
    if not lang:
        flag, lang = "--write-auto-subs", next((k for k in ("en-orig", "en") if k in auto), None)
    f = None
    if lang:  # exactly one subtitle request: reuse the info.json instead of re-fetching the page
        print("TRACK", v, "manual" if flag == "--write-subs" else "auto", lang)
        r = subprocess.run(YT + ["--load-info-json", f"evidence/{v}.info.json", flag, "--sub-langs", lang,
            "--sub-format", "vtt", "--sleep-subtitles", "10"], capture_output=True, text=True)
        if re.search(BLOCK, r.stderr):
            os.remove(f"evidence/{v}.info.json")
            stop = f"STOP at {v}: YouTube is blocking (sign-in/bot check/429). Not bypassing; rerun later. Done items kept."; break
        f = next(iter(glob.glob(f"evidence/{v}.*.vtt")), None)
    if f:
        open(f"evidence/{v}.txt", "w", encoding="utf8").write(vtt2txt(f))
        json.dump({"id": v, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
            "upload_date": info.get("upload_date"), "duration": info.get("duration"),
            "chapters": [{"title": c["title"], "start_time": c["start_time"]} for c in info.get("chapters") or []],
            "description": (info.get("description") or "")[:500]},
            open(f"evidence/{v}.meta.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    else: print("WARN", v, "no English captions; left out of seed")
    os.remove(f"evidence/{v}.info.json")

with open("seed.jsonl", "w", encoding="utf8") as o:
    for v, hint, prio in items:
        if not os.path.exists(f"evidence/{v}.txt"): continue
        vtt = glob.glob(f"evidence/{v}.*.vtt")[0]
        o.write(json.dumps({"key": "https://www.youtube.com/watch?v=" + v, "evidence": vtt, "text": f"evidence/{v}.txt",
            "meta": f"evidence/{v}.meta.json", "hint": hint, "priority": prio}, ensure_ascii=False) + "\n")
if stop: raise SystemExit(stop)
PY
