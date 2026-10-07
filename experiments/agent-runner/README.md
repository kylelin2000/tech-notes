# agent-runner

> **狀態：個人 PoC / 實驗（2026-10-06）**
> 起因：想讓 AI agent 無人值守跑長時間的「窮舉並整理資料」工作，向 AI 詢問後得到的 draft，作為起點自行試用。
> 驗證程度：claude 後端已實跑（2026-10-07，Claude Code 2.1.292 + Sonnet）：[examples/harness-research](examples/harness-research/) 三個來源共 28 項全數完成，成本由 CLI 回報、非估算。codex / opencode / api 後端仍只用假 agent（`tests/fake_agent.py`）與 mock API（`tests/mock_api.py`）測過，旗標請先用 `--dry-run` 確認。
> 不是可上線的工具，之後可能改動或捨棄。

讓 claude / codex / opencode CLI、任意自訂指令，或直接打 OpenAI 相容 API，在**無人值守**下跑幾個小時的「窮舉並整理資料」工作。

核心想法：**「完成了沒」由程式判斷，不由模型說了算。** 進度存在 SQLite 帳本；runner 負責迴圈、預算、逾時、停滯偵測與 log；模型只負責每一批的內容工作。

```
run.py ──迴圈──▶ backend（claude -p / codex exec / opencode run / custom / 內建 API tool loop）
   │                    │ 每批只處理 batch_size 筆，結果寫進帳本
   ▼                    ▼
 預算/時間/停滯檢查   ledger.db（pending → in_progress → done / failed / blocked / not_found）
   │
   └─ finally：不論成功、失敗、被 kill，都寫 summary.json / report.md / results.jsonl / problems.jsonl
```

## 快速開始

```bash
cp config.example.toml config.toml     # 改 allowed_domains、required_fields、limits
cp task.example.md task.md             # 寫你的任務規格
python3 run.py --config config.toml --dry-run   # 先看會送出的 prompt 與指令，不會執行
python3 run.py --config config.toml             # 正式跑（Python 3.11+，無第三方套件）
```

換後端：`--backend claude|codex|opencode|api|custom`，或改 `[run].backend`。

重跑同一份 config 會**接續**（帳本還在）；要全新開始就換 `[run].db` 或刪掉 `state/`。

### cron

```cron
*/30 * * * *  cd /path/to/agent-runner && /usr/bin/python3 run.py --config config.toml >> cron.out 2>&1
```

有檔案鎖：上一輪還在跑時，新的那次會直接跳過（記在 `runs/skipped.log`，exit 75）。工作已完成時再跑，會立刻以 `completed` 結束。

## 怎麼確保「真的都有抓」

| 機制 | 做法 |
|---|---|
| 狀態在磁碟，不在 context | 每批都是全新 session；斷線、context 滿、重開機都能續跑 |
| 完整性可機械檢查 | `ledger.py check`：無 pending/in_progress、探索已標記完成、列舉數 ≥ 網站自報總數（`set-expected`） |
| 結果要過關才收 | `done` 會被帳本拒絕，除非有 `required_fields` 且附上存在的 `--evidence` 原始頁面 |
| 失敗不被吞掉 | 重試到 `max_attempts` 才轉 `failed`；擋牆轉 `blocked`；真的沒有轉 `not_found`；全部列在 `problems.jsonl` |
| 額外關卡 | `[verify].cmd`：帳本說完成後再跑你的腳本（抽樣重抓、schema 驗證…），exit 0 才算完成；失敗輸出會回饋給下一批 |
| 不會空轉 | 連續 N 批帳本都沒進展 → `stalled` 停止；連續 N 批失敗 → 停止 |

## 邊界與限制：哪些是硬的、哪些是盡力

| 限制 | 在哪裡生效 | 強度 |
|---|---|---|
| `max_wall_seconds` | 迴圈每次開始前；每批逾時會被縮短到剩餘時間 | 硬（整個 process group 會被殺掉） |
| `iteration_timeout_seconds` | 單批逾時 → kill process group | 硬 |
| 環境問題（缺工具、沒網路、認證失敗） | agent 呼叫 `ledger.py abort --reason`，整個 run 停止（exit 6）、該批 claim 的 attempts 退回；修好環境後重跑會自動清除 abort | 盡力（靠 agent 回報） |
| `max_iterations`、`max_consecutive_failures`、`max_stalled_iterations` | 批與批之間 | 硬 |
| `max_cost_usd_per_iteration` | claude：傳給 `--max-budget-usd`，由 CLI 在執行中強制 | 硬（claude） |
| `max_total_tokens` / `max_cost_usd` | **api 後端**：每次呼叫後檢查，批次中途就停。**CLI 後端**：批與批之間檢查 | api 硬；CLI 可能超出「一批」的量 |
| CLI 的 token / 成本數字 | claude：讀 JSON 的 `usage` 與 `total_cost_usd`。codex：讀 `--json` 的 `turn.completed.usage`。其他：解析不到就用字元數估算（報告會標 ESTIMATED） | 盡力 |

註：`max_wall_seconds` 用真實時間（time.time），包含系統睡眠；`iteration_timeout_seconds`（subprocess timeout）不計睡眠。

所以：**批量要小**（`batch_size`、`max_turns`），CLI 後端最多只會超出一批的量。真正的最後防線請在供應商那端設**每月/專案支出上限**或給 API key 額度，這是程式之外唯一不會被 bug 繞過的一層。

`count_cache_read_tokens = false`（預設）：agent 迴圈每回合都會重讀 context，cache read 會讓 token 數看起來很大；要控預算，成本（USD）通常比 token 數更準。

## Log 與產出（每次執行一個資料夾 `runs/<時間>/`）

- `run.log`：人看的時間軸（每批開始／結束、帳本進度、token、成本、錯誤）
- `events.jsonl`：同樣資訊的結構化版本（start / exec / iteration / final）
- `iter-NNN.prompt.md / .stdout / .stderr`：每批送出的完整 prompt 與原始輸出（API 後端則是 `.transcript.jsonl`）
- `summary.json`、`report.md`：結束狀態、原因、用量、帳本統計、前 50 個問題項目
- `results.jsonl`：完成的結果；`problems.jsonl`：failed / blocked / not_found / 未完成及原因
- 原始頁面快照在 `evidence/`

被 `kill`（SIGTERM/SIGINT/SIGHUP）、崩潰、達到上限時 `finally` 一樣會寫出上述檔案。`kill -9` 或機器斷電無法攔截，但 `run.log`、`events.jsonl` 與帳本是逐步寫入的，仍保有到當時為止的紀錄。

Exit code：`0` 完成｜`1` 錯誤｜`2` 達到上限｜`3` 停滯｜`4` 連續失敗｜`5` 完成但有 failed 項目｜`6` agent 回報環境壞掉（abort）｜`75` 已有另一個在跑｜`130` 被中斷

## 各後端注意事項

- **claude**：用 `claude -p --output-format json`，prompt 走 stdin。預設只允許 `Read, Write, Edit, WebFetch, WebSearch` 與「只能執行 ledger.py」的 Bash。無人值守時沒被允許的工具會直接被拒絕而不是卡住等確認；如果 log 裡看到一直 permission denied，調整 `[claude].allowed_tools`。不建議用 `--dangerously-skip-permissions`，除非跑在隔離的容器／VM。
- **codex**：`codex exec --json --full-auto --skip-git-repo-check`。它預設的 sandbox 會擋網路，需要在你的 Codex 設定中開啟，或用 `[codex].cmd` 覆寫整條指令。
- **opencode**：`opencode run --format json`。用量多半解析不到，會走估算；請以時間／批次數／供應商端上限為主。
- **custom**：`[custom].cmd = [...]`，可用 `{prompt} {prompt_file} {max_turns} {iter_budget_usd} {model}`，`prompt_via = "arg" | "stdin"`。
- **api**：內建的 tool loop，打 `/chat/completions`（OpenAI 相容，LiteLLM、OpenRouter 等也可）。內建 `fetch`（網域白名單、遵守 robots.txt、每站最小間隔、重新導向不得離開白名單、原始頁面存證）與全部帳本操作。**只處理靜態 HTML／JSON**；需要執行 JS 的網站請改用有瀏覽器能力的 CLI，或自己擴充 `Fetcher`。

> 各 CLI 的旗標會隨版本變動。我是依官方文件與社群資料設定預設值，若你的版本不同，先 `--dry-run` 看指令，必要時用 `[<backend>].cmd` 覆寫。

## 檔案

```
run.py                 主程式（迴圈、預算、log、backends、API tool loop）
ledger.py              帳本（CLI + 函式庫）
config.example.toml    設定範例（所有限制都在 [limits]）
task.example.md        任務規格範本
tests/fake_agent.py    不需 API 的假 agent，用來測 runner
tests/mock_api.py      假網站 + 假 LLM 端點，用來測 API 後端
```

自己驗證一次：

```bash
python3 tests/mock_api.py 8801 8802 &      # 另開終端也可
# 再用 config 指向 http://127.0.0.1:8802/v1、allowed_domains=["127.0.0.1"]、task.md 內寫 INDEX=http://127.0.0.1:8801/index.html
```

## 爬取的禮貌與合規

只抓你有權抓的內容；遵守網站條款與 robots.txt；`min_delay_seconds` 別設太小；遇到登入牆、CAPTCHA、403/429 是記錄為 `blocked`，不是繞過。

### 避免 429（實測經驗，2026-10）

- **抓一次、存檔、不重抓**：prep 腳本遇到已存在的輸出就跳過（可續跑）；API 搜尋結果存成檔案當快取。
- **測試也會吃額度**：可行性測試抓過的檔案直接拿去正式試跑，不要同一份資源再抓一次。
- **被 429 就停**：整批停下、晚點重跑接續；不要密集重試，不用 cookies，不繞過驗證。
- 各來源：
  - arXiv API：間隔 3 秒仍會 429，約 15 分鐘後恢復。
  - Semantic Scholar（未帶 key）：共用額度，幾乎一直 429；要用就申請免費 key。
  - YouTube 字幕（yt-dlp）：抓幾支就 429，重抓同一支更快被擋。用 `--sleep-subtitles 10`、每支間隔約 30 秒；每支只抓一條字幕軌：先抓 info.json 挑軌，再用 `--load-info-json` 只下載那一條（實測連抓 21 支、間隔約 45 秒，0 次 429）。
  - OpenReview：審稿回覆回 403 bot challenge，視為拿不到。
  - 目前沒問題：`gh` 登入後的 GitHub API、HN Algolia API、Anthropic Engineering、simonwillison.net（間隔 3 秒）。
