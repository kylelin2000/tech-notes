# harness-research

用 agent-runner 研究「agent harness」的三條來源，各自一個工作目錄：

- `blogs/`：Anthropic Engineering 最新 2 篇 + Simon Willison `ai-agents` tag 1 篇
- `github/`：GitHub 搜尋 agent harness 依 stars 挑 3 個 repo（README + 檔案樹）
- `papers/`：Semantic Scholar 依引用數挑 3 篇 arXiv 論文；OpenReview 審稿目前被 bot challenge 擋（403），不繞過

```bash
cd blogs && bash prep.sh   # 產生 seed.jsonl 與 evidence/（agent 不上網，只讀這些檔案）
uv run --python 3.12 ../../../run.py --config config.toml
```

papers 需要 poppler（`brew install poppler`）。`papers/s2_search.json` 是快取，刪掉會重新查 S2（未帶 key 很容易 429）。

首次試跑（2026-10-07，claude sonnet）：三個來源各 1 批、9/9 done，共 $1.31。
