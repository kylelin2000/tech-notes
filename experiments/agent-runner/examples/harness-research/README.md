# harness-research

用 agent-runner 研究「agent harness」的實務做法，每條來源各自一個工作目錄：

- `talks/`：harness-engineering 筆記「待讀清單」的 YouTube 演講，yt-dlp 抓英文字幕（多為自動字幕）轉純文字，依筆記章節整理；`LIMIT=N bash prep.sh` 可只抓前 N 支
- `blogs/`：Anthropic Engineering 最新 2 篇 + Simon Willison `ai-agents` tag 1 篇
- `github/`：GitHub 搜尋 agent harness 依 stars 挑 3 個 repo（README、AGENTS/CLAUDE 等文件、檔案樹）

```bash
cd talks && LIMIT=2 bash prep.sh   # 產生 seed.jsonl 與 evidence/（agent 不上網，只讀這些檔案）
uv run --python 3.12 ../../../run.py --config config.toml
```

talks 需要 yt-dlp。YouTube 字幕端點很容易 429：prep.sh 每支間隔約 45 秒，被擋就停下，之後重跑會從沒抓到的那支接續。

全量試跑（2026-10-07，claude sonnet）：talks 21/21 done，10 批、14 分鐘、$3.78；prep 約 15 分鐘、0 次 429。

學術論文（Semantic Scholar + arXiv）試過後拿掉：未帶 key 的 S2 API 幾乎一直 429，且重點是實務做法而非論文。
