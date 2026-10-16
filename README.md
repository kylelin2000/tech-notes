# tech-notes

個人技術學習筆記，多數內容由 AI agent 協助蒐集公開資料後整理成中文摘要。各篇筆記附有來源索引，細節請以原始來源為準。

## 工具

各主題共用的腳本放在 [tools/](tools/)，只用 Python 標準函式庫：

- [fetch.py](tools/fetch.py)：抓來源的共用邏輯（抓一次存進 `.cache/`、429 就整批停下、403／CAPTCHA 標記 blocked 不繞過）。主題的 `prep.py` 只寫自己的來源表和 `run()`，目前有 [ai-agents/prep.py](ai-agents/prep.py)。
- [check.py](tools/check.py)：檢查每個 `[簡稱]` 都在該篇的來源表裡、筆記之間的連結與錨點都對得到。`python3 tools/check.py` 檢查整個 repo，加資料夾名稱只檢查該主題。

## 授權

筆記內容（Markdown、SVG 圖表等）採用 [CC BY 4.0](LICENSE) 授權：可自由分享與改作，但須署名並附上授權連結。

所有程式碼（`.py`、`.sh` 等腳本，包括 experiments/agent-runner/、tools/ 和 ai-agents/prep.py）採用 [MIT](experiments/agent-runner/LICENSE) 授權。

本授權僅適用於本 repo 的原創內容。筆記中摘要、引用的論文、演講、指引與網頁，著作權仍屬原作者或出版者，請依各來源自身的授權使用。
