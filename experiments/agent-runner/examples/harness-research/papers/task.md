# Task: 讀有被引用的 agent harness 相關論文，整理成結構化摘要（含審稿意見）

## Item
帳本 key = arXiv ID。payload 有 citations、evidence（PDF 原檔）、text（pdftotext 轉出的純文字），可能有 reviews（OpenReview 審稿 JSON，evidence/<ID>.reviews.json）。

## 怎麼讀
用 Read 讀 payload.text（純文字）；用 offset/limit 分段往下讀，直到正文結束為止。參考文獻跳過；附錄只在需要時才看。
PDF 只在文字遺失圖表/表格、而你需要其內容時才開（Read 以圖片渲染，貴，一次最多 20 頁，只開需要的頁）。

## Fields
- arxiv_id, title（必填）
- problem：要解決什麼問題，1–2 句（必填）
- method：做法重點，2–3 句（必填）
- findings：主要結果，附關鍵數字（必填）
- limitations：作者自述或明顯的限制
- review_critique：若 payload 有 reviews，整理審稿人的主要質疑與作者回應，3–5 點；沒有就省略
- harness_takeaway：對設計 agent harness 有什麼可用的啟示，1–2 句
- notes：閱讀備註；若沒讀完整個正文，寫明跳過的章節

## Rules
- 若沒讀完整個正文，必須在 notes 欄位寫明跳過了哪些章節。
- 不要上網，只讀 evidence/ 裡已下載的檔案（檔名見 item 的 payload.evidence）。
- 以繁體中文撰寫，專有名詞、title 保留原文。用自己的話寫，不要大段照抄。
- 讀不到的欄位留空，不要猜。檔案損壞或內容與 agent harness 完全無關 → not-found 並寫明原因。
- done 時附 --evidence <payload.evidence>。result 較長時先用 Write 寫到 results/<安全檔名>.json 再用 --result @results/<安全檔名>.json。
