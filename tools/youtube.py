#!/usr/bin/env python3
"""抓 YouTube 英文字幕（手動字幕優先，沒有才用自動字幕），轉成每約 60 秒有 [mm:ss] 標記的純文字。

python3 tools/youtube.py URL或影片ID ...                       # 存進 tools/.cache/youtube/
python3 tools/youtube.py --from-note ai-agents/concepts/harness-engineering.md   # 讀筆記「## 待讀清單」裡的 YouTube 連結
python3 tools/youtube.py --out evidence --seed seed.jsonl ...  # 給 agent-runner：另外寫 seed（路徑相對於 seed 檔）
LIMIT=N 只抓前 N 支。需要 yt-dlp。

每支輸出 <id>.txt（逐字稿）、<id>.meta.json（標題、頻道、長度、章節）、<id>.<lang>.vtt（原始字幕）。
- 抓一次就存檔，<id>.txt 已存在的跳過，可續跑。
- YouTube 字幕端點很容易 429：每支只發一次字幕請求（先抓 info.json 挑軌，再用 --load-info-json 只下載那一條），每支間隔約 45 秒。
- 被擋（sign-in／bot check／429）就整批停下（exit 2），晚點重跑接續；不用 cookies、不繞過。
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache" / "youtube"
SPACING = 30  # 秒，加上 --sleep-subtitles 10，每支約 45 秒
BLOCK = re.compile(r"Sign in|not a bot|HTTP Error 429|Too Many Requests")
VID = re.compile(r"(?:v=|youtu\.be/|^)([\w-]{11})(?![\w-])")


def from_note(path, section):
    """筆記某一節裡的 YouTube 連結：回傳 [(id, hint, priority)]。### 標題當優先度，連結後面的文字當 hint。"""
    m = re.search(rf"^## {re.escape(section)}\n(.*?)(?=^## |\Z)", Path(path).read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        sys.exit(f"{path} 找不到「## {section}」")
    items, prio = [], ""
    for ln in m.group(1).splitlines():
        if ln.startswith("### "):
            prio = re.sub(r"[（(].*", "", ln[4:]).strip()
            continue
        ls = list(re.finditer(r"\]\(https://www\.youtube\.com/watch\?v=([\w-]+)\)", ln))
        if ls:
            hint = ln[ls[-1].end():].lstrip("：").strip()
            items += [(m.group(1), hint, prio) for m in ls]
    return items


def vtt2txt(path):
    tsre = re.compile(r"(?:(\d+):)?(\d+):(\d+)\.\d+ --> ")
    out, last, nextmark, cur = [], [], 0, 0
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        m = tsre.match(ln)
        if m:
            h, mi, s = m.groups()
            cur = int(h or 0) * 3600 + int(mi) * 60 + int(s)
            continue
        if not ln.strip() or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        t = re.sub(r"<[^>]+>", "", ln).replace("&nbsp;", " ").replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").strip()
        if not t or t in last[-3:]:  # 自動字幕是滾動的，同一行會重複出現
            continue
        last.append(t)
        if cur >= nextmark:
            out.append(f"[{cur // 60:02d}:{cur % 60:02d}]")
            nextmark = cur - cur % 60 + 60
        out.append(t)
    return "\n".join(out) + "\n"


def fetch(v, out):
    """抓一支；回傳 True 表示有字幕，False 表示沒有英文字幕或 yt-dlp 失敗。被擋就丟 SystemExit。"""
    yt = ["yt-dlp", "--skip-download", "-o", str(out / "%(id)s.%(ext)s")]
    info_path = out / f"{v}.info.json"
    r = subprocess.run(yt + ["--write-info-json", "https://www.youtube.com/watch?v=" + v], capture_output=True, text=True)  # 只抓 metadata
    if BLOCK.search(r.stderr):
        sys.exit(f"STOP at {v}：YouTube 擋下（sign-in／bot check／429），不繞過，晚點重跑接續。")
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except OSError:
        print("WARN", v, "yt-dlp 失敗：", r.stderr.strip()[-200:])
        return False
    subs, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    man = [k for k in subs if k == "en" or k.startswith("en-")]
    flag, lang = "--write-subs", "en" if "en" in man else man[0] if man else None
    if not lang:
        flag, lang = "--write-auto-subs", next((k for k in ("en-orig", "en") if k in auto), None)
    vtt = None
    if lang:  # 只發一次字幕請求：重用 info.json，不再抓一次頁面
        print("TRACK", v, "manual" if flag == "--write-subs" else "auto", lang, flush=True)
        r = subprocess.run(yt + ["--load-info-json", str(info_path), flag, "--sub-langs", lang,
                                 "--sub-format", "vtt", "--sleep-subtitles", "10"], capture_output=True, text=True)
        if BLOCK.search(r.stderr):
            info_path.unlink()
            sys.exit(f"STOP at {v}：YouTube 擋下（sign-in／bot check／429），不繞過，晚點重跑接續。")
        vtt = next(iter(glob.glob(str(out / f"{v}.*.vtt"))), None)
    info_path.unlink()
    if not vtt:
        print("WARN", v, "沒有英文字幕")
        return False
    (out / f"{v}.txt").write_text(vtt2txt(vtt), encoding="utf-8")
    meta = {"id": v, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
            "upload_date": info.get("upload_date"), "duration": info.get("duration"),
            "chapters": [{"title": c["title"], "start_time": c["start_time"]} for c in info.get("chapters") or []],
            "description": (info.get("description") or "")[:500]}
    (out / f"{v}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def write_seed(items, out, seed):
    """agent-runner 的 seed：key 是影片網址，evidence 是 .vtt，路徑相對於 seed 檔所在資料夾。"""
    rel = lambda p: os.path.relpath(p, seed.resolve().parent).replace(os.sep, "/")
    with open(seed, "w", encoding="utf-8") as o:
        for v, hint, prio in items:
            vtts = glob.glob(str(out / f"{v}.*.vtt"))
            if not (out / f"{v}.txt").exists() or not vtts:
                continue
            o.write(json.dumps({"key": "https://www.youtube.com/watch?v=" + v, "evidence": rel(vtts[0]), "text": rel(out / f"{v}.txt"),
                                "meta": rel(out / f"{v}.meta.json"), "hint": hint, "priority": prio}, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="*", help="影片網址或 11 碼 ID")
    ap.add_argument("--from-note", help="從這篇筆記的某一節讀 YouTube 連結")
    ap.add_argument("--section", default="待讀清單", help="--from-note 讀哪一節（預設：待讀清單）")
    ap.add_argument("--out", type=Path, default=CACHE, help=f"輸出資料夾（預設：{CACHE}）")
    ap.add_argument("--seed", type=Path, help="另外寫 agent-runner 的 seed.jsonl")
    a = ap.parse_args()

    items = from_note(a.from_note, a.section) if a.from_note else []
    for s in a.videos:
        m = VID.search(s)
        if not m:
            sys.exit(f"看不出影片 ID：{s}")
        items.append((m.group(1), "", ""))
    if not items:
        ap.error(f"「## {a.section}」裡沒有 YouTube 連結" if a.from_note else "沒有影片：給網址／ID 或 --from-note")
    items = list({v: (v, h, p) for v, h, p in items}.values())[:int(os.environ.get("LIMIT") or len(items))]
    print(len(items), "支：", " ".join(i[0] for i in items))

    if not shutil.which("yt-dlp"):
        sys.exit("需要 yt-dlp（例如 pip install yt-dlp）")
    a.out.mkdir(parents=True, exist_ok=True)
    fetched = False
    try:
        for v, _, _ in items:
            if (a.out / f"{v}.txt").exists():
                continue
            if fetched:
                time.sleep(SPACING)
            fetch(v, a.out)
            fetched = True
    except SystemExit as e:  # 被擋：已抓到的照樣寫進 seed，再停下
        if a.seed:
            write_seed(items, a.out, a.seed)
        print(e.code, file=sys.stderr)
        sys.exit(2)
    if a.seed:
        write_seed(items, a.out, a.seed)


if __name__ == "__main__":
    main()
