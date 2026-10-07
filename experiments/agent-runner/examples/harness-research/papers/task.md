# Task: 讀有被引用的 agent harness 相關論文，整理成結構化摘要（含審稿意見）

## Item
帳本 key = arXiv ID。payload 有 citations、evidence（PDF），可能有 reviews（OpenReview 審稿 JSON，evidence/<ID>.reviews.json）。

## 怎麼讀
用 Read 讀 PDF，一次最多 20 頁；先讀 1–15 頁（正文），附錄只在需要時看。

## Fields
- arxiv_id, title（必填）
- problem：要解決什麼問題，1–2 句（必填）
- method：做法重點，2–3 句（必填）
- findings：主要結果，附關鍵數字（必填）
- limitations：作者自述或明顯的限制
- review_critique：若 payload 有 reviews，整理審稿人的主要質疑與作者回應，3–5 點；沒有就省略
- harness_takeaway：對設計 agent harness 有什麼可用的啟示，1–2 句

## Rules
- 不要上網，只讀 evidence/ 裡已下載的檔案（檔名見 item 的 payload.evidence）。
- 以繁體中文撰寫，專有名詞、title 保留原文。用自己的話寫，不要大段照抄。
- 讀不到的欄位留空，不要猜。檔案損壞或內容與 agent harness 完全無關 → not-found 並寫明原因。
- done 時附 --evidence <payload.evidence>。result 較長時先用 Write 寫到 results/<安全檔名>.json 再用 --result @results/<安全檔名>.json。
