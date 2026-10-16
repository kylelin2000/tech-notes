"""PreToolUse hook：工具呼叫的輸入含有我的個人識別資訊時，改成要我親自核准。

識別資訊在執行時讀取，不寫進 repo：
- `git config user.email`
- `.claude/identity.local`（不進 git，選用）：一行一個要保護的字串，例如其他 email、電話、真實姓名

只讀本機檔案的工具（Read、Glob、Grep）不檢查。
hook 本身出錯時一律要我確認（fail closed），不讓工具呼叫在沒檢查的情況下放行。
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, quote_plus

LOCAL_ONLY = {"Read", "Glob", "Grep"}
EXTRA = Path(__file__).resolve().parent.parent / "identity.local"


def identifiers():
    found = set()
    try:
        out = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True, timeout=5).stdout
        found.add(out.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    if EXTRA.exists():
        # utf-8-sig：PowerShell 5.1 的 Out-File／Set-Content -Encoding utf8 會寫 BOM
        found.update(line.strip() for line in EXTRA.read_text(encoding="utf-8-sig").splitlines())
    return {s.lower() for s in found if s and not s.startswith("#")}


def forms(s):
    """原字串，以及放進 URL path（%20）和 query／form（+）時的編碼形式。"""
    return {s, quote(s, safe="").lower(), quote_plus(s).lower()}


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}))


def main():
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if event.get("tool_name") in LOCAL_ONLY:
        return
    blob = json.dumps(event.get("tool_input", {}), ensure_ascii=False).lower()
    hits = [s for s in identifiers() if any(f in blob for f in forms(s))]
    if not hits:
        return
    ask("這個工具呼叫帶有使用者的個人識別資訊（email 等）。依 CLAUDE.md，未經使用者明確同意不得送出；"
        "改用不需身分的來源，或把該來源標記為拿不到。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        ask(f"guard_identity.py 執行失敗（{type(e).__name__}），沒有檢查這個工具呼叫是否帶有個人識別資訊，請親自確認。")
