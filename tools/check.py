#!/usr/bin/env python3
"""檢查筆記：

1. 正文裡每個 [簡稱] 都在同一篇的來源表（標題「## 來源」或「## 來源索引」）第一欄找得到。
2. 筆記之間的相對連結（含 #錨點）都能跳轉：檔案存在、錨點對得到標題（GitHub 規則）。

python3 tools/check.py              # 整個 repo；有問題就列出並 exit 1
python3 tools/check.py ai-agents    # 只檢查一個資料夾（相對 repo 根目錄，在哪裡執行都一樣）
"""
import re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / (sys.argv[1] if len(sys.argv) > 1 else ".")
LABELS = {"指引", "SR/MA", "RCT", "觀察", "質性", "專家", "自倡", "在地"}


def slug(heading):
    """GitHub 標題錨點：小寫、去標點（保留字母、數字、-、_），空白換成 -。"""
    s = heading.strip().lower()
    s = "".join(c for c in s if c in "-_ " or unicodedata.category(c)[0] in "LNM")
    return s.replace(" ", "-")


assert slug("兩條路徑") == "兩條路徑"
assert slug("範圍與方法（本筆記的限制）") == "範圍與方法本筆記的限制"
assert slug("MCP 與 A2A：比較") == "mcp-與-a2a比較"


def anchors(path):
    seen, out = {}, set()
    for line in strip_code(path.read_text(encoding="utf-8")).splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            s = slug(m.group(1))
            n = seen.get(s, 0)
            out.add(s if n == 0 else f"{s}-{n}")
            seen[s] = n + 1
    return out


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def index_keys(text):
    """「來源索引」標題下面那張表的第一欄。"""
    m = re.search(r"^## 來源(?:索引)?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return None
    rows = re.findall(r"^\|\s*([^|]+?)\s*\|", m.group(1), re.M)
    return {r for r in rows if r not in ("簡稱",) and not set(r) <= set("-: ")}


def check(path):
    errs, raw = [], path.read_text(encoding="utf-8")
    text = strip_code(raw)
    keys = index_keys(text)
    body = re.split(r"^## 來源(?:索引)?\n", text, flags=re.M)[0]
    refs = set(re.findall(r"(?<![!\]])\[([^\[\]\n]+)\](?![(\[])", body)) - LABELS
    if keys is None and refs:  # 來源表標題不是「## 來源」或「## 來源索引」就沒辦法檢查
        errs.append(f"有 [簡稱] 引用但找不到「## 來源」或「## 來源索引」：{' '.join(sorted(refs)[:5])}")
    for key in sorted(refs - keys) if keys is not None else ():
        errs.append(f"[{key}] 不在來源索引")
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target):
            continue
        file, _, frag = target.partition("#")
        dest = (path.parent / file).resolve() if file else path
        if not dest.exists():
            errs.append(f"連結檔案不存在：{target}")
        elif frag and dest.suffix == ".md" and frag not in anchors(dest):
            errs.append(f"錨點對不到：{target}")
    return errs


def main():
    if not ROOT.is_dir():
        sys.exit(f"{ROOT} 不是資料夾")
    bad = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".cache" in path.parts:
            continue
        for e in check(path):
            print(f"{path.relative_to(ROOT)}: {e}")
            bad += 1
    print("OK" if not bad else f"{bad} 個問題")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
