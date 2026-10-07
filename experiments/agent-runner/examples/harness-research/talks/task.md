# Task: 讀研討會演講逐字稿，整理成可併入 harness-engineering 筆記的重點

背景：agent harness = 驅動 LLM agent 的外層程式——迴圈、工具定義、context 管理、權限、評測、長時間任務的狀態保存。
輸出會由人工併入 `ai-agents/concepts/harness-engineering.md`，所以請照該筆記的章節分類。

## Item
帳本 key = YouTube URL。payload：
- text：逐字稿純文字（evidence/<id>.txt），每約 60 秒有 `[mm:ss]` 標記
- meta：標題、頻道、長度、章節（evidence/<id>.meta.json）
- evidence：原始字幕檔（.vtt），done 時附這個
- hint：筆記待讀清單對這支影片的一句預期（可能不準，以內容為準）

逐字稿多為**自動字幕**：有口語贅詞、人名與產品名可能聽錯（以 meta 的標題、章節名稱校正）。整份讀完再寫，不要只讀開頭。

## Fields
- url, title（必填，title 用 meta 原文）
- speaker：講者與所屬公司（必填）
- summary：核心主張 2–3 句（必填）
- practices：可直接照做的具體做法，條列，每點結尾附出處時間 `[mm:ss]`（必填）
- by_section：物件，key 只能用以下筆記章節名稱，只放有內容的章節，每章節 1–3 點，每點附 `[mm:ss]`（必填）
  設計原則與取捨、Agent loop 與控制流、Context engineering、工具與 Skills、驗證與品質關卡、記憶、沙箱權限與安全、狀態可靠性與可觀測、長時間非同步與組織級、成本與模型選擇、持續改進與評估、反例風險與爭議
- numbers：演講中提到的具體數據（附 `[mm:ss]`；自動字幕的數字可能聽錯，標「待核對」）
- disagreements：與常見做法相反或有爭議的主張
- vendor：是否帶產品宣傳性質，none / light / heavy，附一句理由
- caption_caveats：疑似聽錯的專有名詞與你的校正

## Rules
- 不要上網，只讀 payload 列出的檔案。
- 以繁體中文撰寫，專有名詞保留原文。用自己的話寫，不要大段照抄；直接引用原話時加引號並附時間。
- 逐字稿沒講的不要補，不要用你自己的知識填空。
- 逐字稿檔案不存在或幾乎是空的 → not-found 並寫明原因。
- result 較長，先用 Write 寫到 results/<id>.json 再用 --result @results/<id>.json，done 時附 --evidence <payload.evidence>。
