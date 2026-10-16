# tools

撈資料、整理資料的程式都放這裡；整理出來的筆記直接放進對應的主題資料夾（例如 `ai-agents/concepts/`）。除了 agent-runner 需要 Python 3.11+，其餘只用 Python 標準函式庫；PDF 轉文字需要 `pdftotext`，YouTube 字幕需要 `yt-dlp`。

## 整理流程

1. **抓取**（不呼叫 LLM）：`python3 tools/sources/<主題>.py` 把來源抓一次存進 `tools/.cache/<主題>/`（不進 git），檔名就是筆記裡的 `[簡稱]`；演講用 `python3 tools/youtube.py <網址>` 抓逐字稿。
2. **整理**：在互動式 Claude Code session 讀快取寫筆記；來源多時用 subagent 逐篇摘要，再挑選、去重後合併。
3. **寫進筆記**：放進對應主題資料夾，來源表第一欄用和快取檔名相同的 `[簡稱]`。
4. **檢查**：`python3 tools/check.py <主題>`。

[agent-runner](agent-runner/README.md) 只在這些情況才用：項目上百筆、要無人值守跑好幾個小時或排 cron、要硬性的花費上限、或要換非 Claude 的後端。數十筆以內用上面的互動式流程就夠了。

## 檔案

| 路徑 | 用途 |
|---|---|
| [fetch.py](fetch.py) | 抓取的共用邏輯：抓一次存進快取、429 就整批停下、403／CAPTCHA 標記 blocked 不繞過 |
| [sources/](sources/) | 各主題的來源表，每個主題一支，只寫 `SOURCES` 和 `run()`；目前有 [ai-agents.py](sources/ai-agents.py) |
| [youtube.py](youtube.py) | 抓 YouTube 英文字幕轉成附 `[mm:ss]` 的逐字稿，存進 `tools/.cache/youtube/`；可從筆記某一節讀連結，也能產生 agent-runner 的 seed |
| [check.py](check.py) | 檢查每個 `[簡稱]` 都在該篇的來源表裡、筆記之間的連結與錨點都對得到。`python3 tools/check.py` 檢查整個 repo，加資料夾名稱只檢查該主題 |
| [agent-runner/](agent-runner/README.md) | 個人 PoC：讓 claude / codex / opencode CLI 或 OpenAI 相容 API 無人值守跑長時間資料整理任務（SQLite 帳本、預算／逾時／停滯護欄、完整 log），不保證穩定 |

新增主題：複製 `sources/ai-agents.py`，改 `SOURCES`、`CACHE` 的主題名稱與 `fetch.SPACING`，`run()` 依來源格式調整。

## 避免 429（實測經驗，2026-10）

- **抓一次、存檔、不重抓**：抓取腳本遇到已存在的輸出就跳過（可續跑）；API 搜尋結果存成檔案當快取。
- **測試也會吃額度**：可行性測試抓過的檔案直接拿去正式試跑，不要同一份資源再抓一次。
- **被 429 就停**：整批停下、晚點重跑接續；不要密集重試，不用 cookies，不繞過驗證。
- 各來源：
  - arXiv API：間隔 3 秒仍會 429，約 15 分鐘後恢復。
  - Semantic Scholar（未帶 key）：共用額度，幾乎一直 429。被 429 就標記為拿不到；要不要申請 key 由我決定，agent 不自己申請。
  - YouTube 字幕（yt-dlp）：抓幾支就 429，重抓同一支更快被擋。用 `--sleep-subtitles 10`、每支間隔約 30 秒；每支只抓一條字幕軌：先抓 info.json 挑軌，再用 `--load-info-json` 只下載那一條（實測連抓 21 支、間隔約 45 秒，0 次 429）。[youtube.py](youtube.py) 已照這個做法實作，結果記進 `status.json`：沒有英文字幕、需要登入（年齡限制、私人影片）的之後不重抓，其他失敗（例如斷網）下次重試；指令後面直接給網址一律重抓。
  - OpenReview：審稿回覆回 403 bot challenge，視為拿不到。
  - 目前沒問題：`gh` 登入後的 GitHub API、HN Algolia API、Anthropic Engineering、simonwillison.net（間隔 3 秒）。
