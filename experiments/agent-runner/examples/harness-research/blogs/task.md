# Task: 讀 AI 公司工程部落格與實務者文章，整理 agent harness 的實際做法

背景：agent harness = 驅動 LLM agent 的外層程式——迴圈、工具定義、context 管理、權限、評測、長時間任務的狀態保存。

## Item
帳本 key = 文章 URL。payload 有 source、evidence（已下載的 HTML）。

## Fields
- url, title, source（必填）
- key_ideas：文章核心主張，2–4 點（必填）
- harness_practices：可直接照做的具體做法（工具設計、context 壓縮、子 agent、驗證…），條列（必填）
- tradeoffs：作者提到的代價或不適用情境
- relevance：和 agent harness 的關聯程度 high / medium / low，附一句理由

## Rules
- 不要上網，只讀 evidence/ 裡已下載的檔案（檔名見 item 的 payload.evidence）。
- 以繁體中文撰寫，專有名詞、title 保留原文。用自己的話寫，不要大段照抄。
- 讀不到的欄位留空，不要猜。檔案損壞或內容與 agent harness 完全無關 → not-found 並寫明原因。
- done 時附 --evidence <payload.evidence>。result 較長時先用 Write 寫到 results/<安全檔名>.json 再用 --result @results/<安全檔名>.json。
