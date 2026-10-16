"""PreToolUse hook：工具呼叫的輸入含有我的個人識別資訊時，改成要我親自核准。

識別資訊在執行時讀取，不寫進 repo：
- `git config user.email`
- `.claude/identity.local`（不進 git，選用）：一行一個要保護的字串，例如其他 email、電話、真實姓名

只讀本機檔案的工具（Read、Glob、Grep）不檢查。
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

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
        found.update(line.strip() for line in EXTRA.read_text(encoding="utf-8").splitlines())
    return {s.lower() for s in found if s and not s.startswith("#")}


def main():
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if event.get("tool_name") in LOCAL_ONLY:
        return
    blob = json.dumps(event.get("tool_input", {}), ensure_ascii=False).lower()
    hits = [s for s in identifiers() if s in blob or quote(s, safe="").lower() in blob]
    if not hits:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": "這個工具呼叫帶有使用者的個人識別資訊（email 等）。依 CLAUDE.md，未經使用者明確同意不得送出；"
                                    "改用不需身分的來源，或把該來源標記為拿不到。",
    }}))


if __name__ == "__main__":
    main()
