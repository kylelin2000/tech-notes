# Agent Evals：持續改進與評估

本篇從 [harness-engineering.md](harness-engineering.md) 的「持續改進與評估 (evals)」章節拆出，內容逐條照搬。內文的 [簡稱]（如 [Schmid-Evals]）對應文末「來源」表，完整索引見原筆記的來源索引。

## 做法

- Trace mining：讓 agent 讀其他 agent 的 trace，找情緒不佳的互動，壓縮後是否變笨，反事實（換模型會如何）；大型 trace 當外部物件查詢；dense feedback 優於單純通過/失敗。[Trivedy]
- 每次失敗都是 harness bug：修 harness 而不是修產出；每週一天 (garbage collection day) 把重複出現的 slop 轉為文件，lint 或 review agent。[Nisi] [Lopopolo]
- 可驗證的持續學習：失敗轉成可重播環境，修補前後有量測差異，並對舊環境做回歸測試；修補層級 (model, harness, memory) 取最小的耐久變更。[Feizi]
- Skill eval 實作：JSON 測試案例（prompt，should_trigger，預期檢查） + 簡單 runner；多以 regex 斷言，複雜時用 LLM judge；隔離工作區，多次重複，測結果不測路徑，跨 harness，每次修改都跑，保留 eval 即使 skill 退役。[Schmid-Evals]
- 自動優化：GEPA 之類最佳化器直接調整被標記的 prompt。[Bhargava] [Feizi]
- 日常除錯：最有效的是親自讀 trace；其次把 transcript 丟給另一個 agent 找問題；觀察 evaluator 判斷與人類分歧處再調 prompt。[Prabaker]
- 現有 benchmark 缺乏對維護性的懲罰（SWE-Marathon，DeepSWE，Frontier Code 為較新嘗試）。[Horthy-SF]
- Eval flywheel：production 與離線研究環境跑逐位元組相同的 agent、同一種 trace 格式；每個 production 的失敗（與成功）都轉成離線 eval task；agent 設定寫成 YAML 以便大量產生變體並行測；評分本身最花時間，也要驗證評分的穩健性。[Aysola]
- Benchmark 實戰（Cline，Terminal Bench 89 題從約 43% 起步 (@14:01)）：每題隔離環境、全部平行跑；派 agent 讀每個失敗 run 的 trace 標註原因；改進分三區：明顯缺陷（crash、被 rate limit）要修、針對模型家族的細調最關鍵、過擬合衝分是危險區。進步多半來自容器資源、timeout、thinking 行為與模型家族專屬 prompt，而不是換模型；hill climbing 與 vibe check 兩個都要。[Khan]
- Eval calcification：系統會變，靜態 benchmark 與手工資料集遲早失效。改以意圖 / 終態定義 eval、從 trace 自動長出測試集；約 80% 穩定部分 + 20% 持續變動由 agent 維護（比例為舉例）；做成 always-on 的線上評測。[Koc]
- 讓 agent 讀過去的 session，建議該新增哪些 automation、subagent 或 rule。[Codex-MC] [Zakariasson]
- 新模型推出時先拿掉既有 skills / markdown，用裸模型重新驗證：不同模型偏好不同（例如對全大寫強調的反應相反）。[LoopsDebate]
- 把一次表現極佳的 "golden session" 交給 agent 拆成可重用的 workflow。[Weitekamp]
- Harness 變更要當成模型變更來發布（Claude Code 品質事件）：三個 harness 層變更（預設 effort、清除舊 thinking 的 bug、system prompt 加字數限制）疊加後看起來像模型退化，API 與推論層其實沒動；code review、單元與 e2e 測試、dogfooding、原有 eval 都沒抓到。改進：每次 system prompt 變更跑跨模型的廣泛 eval 並逐行 ablation（這樣才看到 3% 的下降）、與特定模型相關的調整綁定該模型、soak period 加漸進 rollout、內部人員使用與公開版相同的 build。[Anthropic-PM]

## 相關筆記

- [harness-engineering.md](harness-engineering.md)：Harness 實作做法總覽與完整來源索引
- [agent-security.md](agent-security.md)：沙箱、權限與憑證

## 來源

### 演講與影片

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Trivedy | [Improving Agents is a Data Mining Problem (LangChain)](https://www.youtube.com/watch?v=CvRngaQZQ3Y) | 全文 |
| Nisi | [How I deleted 95% of my agent skills (WorkOS)](https://www.youtube.com/watch?v=vy7o1g2iHY8) | 全文 |
| Lopopolo | [Harness Engineering: How to Build Software When Humans Steer, Ryan Lopopolo (OpenAI)](https://www.youtube.com/watch?v=am_oeAoUhew) | 全文 (含 Q&A) |
| Feizi | [Continual Learning for AI Agents (RELAI)](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | 全文 (廠商性質) |
| Schmid-Evals | [Don't Ship Skills Without Evals (Google DeepMind)](https://www.youtube.com/watch?v=0vphxNt4wyk) | 全文 |
| Bhargava | [What if the harness mattered more than the model? (Etsy)](https://www.youtube.com/watch?v=2e9ANoOEn28) | 全文 |
| Prabaker | [Anthropic Workshop: Build Agents That Run for Hours](https://www.youtube.com/watch?v=mR-WAvEPRwE) | 部分 (關鍵字段落 + 資訊欄) |
| Horthy-SF | [Why Software Factories Fail, Dex Horthy](https://www.youtube.com/watch?v=Ib5GBkD555M) | 全文 |
| Aysola | [How We Built an Agent That Improves Itself, Zubin Aysola (Weights & Biases)](https://www.youtube.com/watch?v=XyV6bSMyq-I) | 全文 (agent 摘要，廠商性質) |
| Khan | [Evals Are Broken, Use Them Anyway, Ara Khan (Cline)](https://www.youtube.com/watch?v=QuuIywMG4s8) | 全文 (agent 摘要) |
| Koc | [Malleable Evals, Vincent Koc (OpenClaw / Comet)](https://www.youtube.com/watch?v=4VhbYlfC7Gs) | 全文 (agent 摘要) |
| Codex-MC | [OpenAI Codex Masterclass, Vaibhav Srivastav & Katia Gil Guzman (OpenAI)](https://www.youtube.com/watch?v=MhHEGMFCEB0) | 全文 (agent 摘要，廠商性質) |
| Zakariasson | [Building your own software factory, Eric Zakariasson (Cursor)](https://www.youtube.com/watch?v=rnDm57Py54A) | 全文 (agent 摘要，廠商性質) |
| LoopsDebate | [The Great Loops Debate, Dex Horthy, Geoff Huntley, Ian Livingstone, Greg Pstrucha](https://www.youtube.com/watch?v=c35YoMdnI78) | 全文 (agent 摘要) |
| Weitekamp | [Recursive Coding Agents, Raymond Weitekamp (OpenProse)](https://www.youtube.com/watch?v=3hXJI2q0Jz8) | 全文 (agent 摘要) |

### 文章與程式庫

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-PM | [An update on recent Claude Code quality reports (Anthropic Engineering)](https://www.anthropic.com/engineering/april-23-postmortem) | 全文 (agent 摘要) |
