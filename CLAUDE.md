# tech-notes 給 AI agent 的規則

這個 repo 是個人學習筆記，AI 的工作是蒐集**公開**資料、整理成中文摘要。整理流程與工具見 [tools/README.md](tools/README.md)。

## 權限邊界（優先於「把資料拿到」）

拿不到某個來源是可以接受的結果；越權拿到不行。遇到下列情況，停下來、把該來源標記為拿不到（寫明原因），改找其他公開來源，或在對話中問我，不要自己想辦法繞過。

- **不送出我的個人資訊**：email、姓名、帳號、電話、API key、token、cookie 都不能放進 URL 參數、HTTP header、User-Agent、表單、搜尋字串或任何送往外部服務的內容。包括「API 要求帶 email 才給較高額度」的情況（例如 Unpaywall `email=`、Crossref／OpenAlex `mailto=`）。需要的話先問我，由我決定要不要給、給哪個。唯一例外是 `tools/fetch.py` User-Agent 裡的公開 GitHub 帳號名稱，維持現狀，不要拿掉也不要加別的。
- **不替我註冊或登入**：不申請帳號、API key、試用方案，不使用瀏覽器裡我已登入的 session 去抓需要登入的內容。
- **不繞過存取限制**：登入牆、付費牆、CAPTCHA、401／403／429、robots.txt 禁止，一律視為拿不到。不換 User-Agent 偽裝、不用 cookies、不找鏡像站或盜版站（例如 Sci-Hub）取得付費論文。
- **不把個人資訊寫進 repo**：腳本、設定、筆記都不寫入我的 email 或其他識別資訊（`tools/fetch.py` 的 GitHub 帳號名稱例外，見上一條）。
- **不擴大範圍**：只做我要求的那件事。需要新工具、新帳號、新付費服務或對外發布（push、發 issue、留言）時先問我。

`.claude/hooks/guard_identity.py` 會在工具呼叫帶有我的 email 時強制跳出確認；被擋下時不要換個寫法（拆字串、編碼、變數拼接）再試，直接照上面的規則處理。
