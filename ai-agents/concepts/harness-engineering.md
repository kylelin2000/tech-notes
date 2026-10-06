# Harness Engineering 實作筆記

整理自 YouTube 頻道 AI Engineer (@aiDotEngineer) 搜尋 "harness" 的結果，目的是萃取對實作 agent harness 有用的做法，並標註每項資訊的來源影片。

- 整理日期：2026-10-06
- 性質：個人學習筆記，非官方內容。內容為對公開演講的中文摘要與歸納，版權屬原講者與 AI Engineer，細節與數據請以原影片為準。
- 相關筆記：概念脈絡見 [prompt-to-graph.md](prompt-to-graph.md)（Prompt → Context → Harness → Loop → Graph 的發展史），本篇聚焦 Harness 層的實作做法。
- 使用方式：內文中的 [講者簡稱] 對應文末「來源索引」表，可直接點連結回原影片。部分影片來自廠商 (Oracle, Docker, Cast AI, RELAI)，帶宣傳性質，已在索引標註。閱讀範圍與限制見文末「範圍與方法」。

---

## 定義與基本觀念

- Harness = Agent 去掉模型後剩下的全部（loop，tools，context 管理，guardrails，memory，驗證，沙箱，觀測）。[Chambers] [Martinez] [Kumar]
- 容易混淆：ML 領域的 "eval harness" (lm-eval-harness) 是測試框架，與 agent harness 不同。[Kumar]
- Harness 不等於 agent loop，是包在 loop 外面的東西，甚至可以是 loop 外面再一層 loop。[Kumar]
- 為什麼要有：模型是租來的黑盒，會被換版、context 受限、行為不穩；harness 提供可靠性與控制，讓便宜或舊模型也能做事（GPT-3.5 示範，全程沒改 prompt）。[Kumar] [Martinez]
- 兩種 agent：我們使用的（Claude Code，Cursor，Kiro；harness 是 memory，skills，MCP，團隊標準）與我們建造的（還需要 loop 管理，擴展，身分，付款，執行環境，可觀測與評估）。[Chambers]
- 抽象層級演進：Messages API（自己寫 loop） → Agent SDK（打包 Claude Code harness） → Managed Agents（連同託管基礎設施一起給）。[Bhat&He] [L.Martin]
- Harness 也是一個「共同演化」的東西：模型釋出時常伴隨 harness 變更，模型訓練時就包含自家 harness（apply_patch，bash 引號語意）。[Prabaker] [Lopopolo] [Horthy-SF]

## 設計原則與取捨（什麼該做，什麼該刪）

- Harness 內含的是「模型做不到什麼」的假設，模型升級後假設會過期。例：Sonnet 4.5 的 "context anxiety" 靠 context reset 補，Opus 4.5 不需要，reset 變成純負擔（延遲，cache 被丟）。每次換模型都要重新檢查哪些元件可以刪。[Bhat&He] [Prabaker]
- 刪減的證據：Cursor 用約 200 行 agent 檔取代約 12，000 行 TypeScript；Manus 半年重構 harness 5 次；LangChain deep research 一年重寫 3 次；Vercel 砍掉 80% 工具；WorkOS 刪 95% skills 後結果更好。經驗法則：若模型進步後 harness 反而更複雜，很可能過度設計 ("build to delete")。[Schmid-NoCode] [Nisi]
- 不要過度設計 (bitter lesson)：做最少的 context 管理，在對的時間把指示給模型；context 的需求不會被模型進步取代。[Lopopolo]
- 相反觀點：弱模型更依賴 harness，同模型不同 harness 差距超過 20 個百分點（HarnessBench 52.4% 到 76.2%），所以投資 harness 可讓本地開源模型逼近前沿模型。[Bhargava]
- 「harness 不夠」：若問題出在模型訓練（如維護性，RL 只獎勵測試通過），再多 harness 或 loop 也補不了，要人讀程式碼並事先規劃。[Horthy-SF]
- 對模型要「引導不要規定」：指示寫目標與限制，不寫死步驟；流程固定就寫腳本。過度 prompt 會拖慢模型（GPT-5 被叫去讀完所有檔案後才改，很慢）。可以直接問模型「我的指示哪裡讓你變慢」。[Schmid-Evals] [Chen&Fioca]
- 順著模型訓練的習慣：工具要 in-distribution (apply_patch, shell + ripgrep)，與官方 harness 對齊。[Kundel] [Chen&Fioca]
- 依賴第一方 harness (Codex, Claude Code) 並從外面 steer，而不是自己重寫 coding harness；或用 SDK / app-server 嵌入。[Lopopolo] [Chen&Fioca] [Kundel]
- 並非所有問題都需要 agent：例 DevOps agent 花兩小時調 prompt，不如 90 秒寫 bash。多數生產環境 agent 是「大量確定性程式 + 少量 LLM 步驟」。[Horthy-12F]

## Agent loop 與控制流

- 最小 harness 骨架：prompt + 工具登錄 + 模型 + loop + 停止條件；工具 = 結構化 JSON 輸出 + switch 敘述。[Horthy-12F] [Kumar] [Miraje]
- Guardrails：max iterations（示範 6），max messages 觸發壓縮，harness 層級重試上限 (3)。GPT-4.1 fast reasoning 實測每次最多 8 到 12 次 tool call 後放棄；「耐心」可設成參數，難題轉給前沿模型，簡單題交給小模型。[Kumar] [Martinez]
- 確定性關卡優先於 prompt：用 TypeScript state machine 在 implementer，verifier，reviewer，closer 之間設 gate，未通過不能前進。"Enforce with code, not prompts"。[Nisi]
- Own your control flow (12-Factor)：自己決定 break，switch，summarize，LLM-as-judge；暫停/恢復用簡單 API，把 context 序列化進 DB 以 state id 恢復；工具呼叫與人類溝通統一（第一個 token 決定是 tool 或問人）。[Horthy-12F]
- Micro-agents：確定性 DAG 中嵌入 3 到 10 步的小 agent loop（部署機器人範例）。[Horthy-12F]
- 控制論式 loop（取代盲目 Ralph loop）：sensor (ast-grep, ESLint, grep) → setpoint → controller（確定性挑下一個小項） → actuator agent（搭配手寫 golden patterns skill） → 重新量測；一次只改一小塊，讓 PR 可讀；用排程 GitHub Action 一次跑一輪。[Mistele]
- Ralph loop：同一個 prompt 反覆餵給 CLI，每輪新 context；失敗要可預測。[Prabaker] [Mistele]
- Event-sourced harness：state + 同步 reducer + after-append hook；一切（串流 chunk，tool call，錯誤，circuit breaker）都是 append-only 事件；重啟時只重播 reducer，不重打 LLM。[Templestein]（部分）
- 長期目標：持續注入 continuation prompt 直到模型呼叫 update-goal 工具；目標要具體可驗證，不要寫長文。[Kundel]
- 子 agent 作法：spawn / send-input / wait / close 工具；背景 terminal 工具；子 agent 就是一般函式當工具，可把不相干工具分組。[Kundel] [Bhargava]
- 工具參數鎖定 (partial application)：先把目錄等參數綁死，模型看不到該參數，兼顧安全與自主。[Bhargava]

## Context engineering

- 預設假設 context 會被換出：設計時要持續刷新；自動 compaction 品質已提升 (GPT-5.4, server-side compaction)。[Lopopolo] [Kundel]
- 壓縮策略實測：單純截斷會失憶；LLM 摘要不一致且把重要性交給模型；有效作法是保留頭尾各約 100 字元，中段移入可檢索的 memory store（附 id，位置，預覽），去重，保留最新工具結果，不動 system prompt。[Delucia]
- 外部化 context：session 是 append-only 事件日誌，模型可回頭讀回被丟棄的片段（近似 Recursive Language Models），壓縮不再是破壞性。[L.Martin] [Bhat&He]
- 延遲載入工具 (deferred tools + tool search)；skills 清單上限為 context 的 2%，超過就縮短描述；cache 友善排序。[Kundel]
- 以子 agent 承接大量資料的任務，主對話保持輕量。[Delucia] [Bhargava]
- 長對話要有測試：先載入 10 輪再測第 11 輪。[Delucia]
- 錯誤進 context 要壓縮：成功後清掉待處理錯誤，摘要不貼整段 stack trace。[Horthy-12F]
- 每次 loop 重新組裝 context（工具與 skills 依需求取用，向量索引檢索）。[Martinez]
- Context rot 實證：注意力隨 token 增加稀釋；資料全塞得進窗時加記憶體只增成本不增準度。[Martinez] [Druga]
- 檔案大小也是 harness 的一部分：用測試限制檔案不超過 350 行以節省 context。[Lopopolo]
- 讓程式碼「長得一致」（一種並發 helper，一種 ORM，一種 CI 腳本寫法），讓 token 更好預測。[Lopopolo]

## 工具 (Tools) 與 Skills

### 工具

- 工具設計：工具輸出就是 JSON，給模型熟悉的形狀；原生工具如 apply_patch，shell，ripgrep；以程式碼執行（持久 REPL + Playwright JS）取代一次一動作的 computer use。[Kundel]
- 範例：browser session 用純 Playwright 而非 MCP。[Kumar]
- MCP 負責 agent 對外，ACP 負責 client 對 harness：JSON-RPC，session，權限請求，可擴充方法；client，harness，tools，model 四者可分別放在不同位置。[Hancock]
- Code Mode（[Pai]，部分）：harness 的重點不只是產生程式碼，還要有一個安全的執行空間，並只在其中暴露受控的能力。
- Gateway：每個沙箱一個 MCP gateway 端點，集中控制工具/資源/prompt，harness 可替換。[Clark]

### Skills 的實作

- 最小支援 = skill registry (name, description, path) + system prompt + 讀檔工具；progressive disclosure：平時只放 name/description。[Miraje] [Schmid-Evals]
- 描述是路由訊號：用使用者的措辭與 trigger words，彼此要有區別，寫 negative case；50% 失敗來自 skill 沒被觸發。[Miraje] [Schmid-Evals]
- 依「使用者意圖」切分，不依資料模型。[Miraje]
- SKILL.md 小於 500 行；人寫的優於 AI 生成；移除 no-op 指示；能寫成腳本就別寫成 skill。[Schmid-Evals]
- 不要把文件整份轉成 skill：10，000 行自動生成 skill 使任務正確率 97% 掉到 77%；改為 553 行手寫 "gotchas" 後 eval 時間 68 分降到 6 分。[Nisi]
- Skill 的類型：capability（模型進步後可退役）與 preference（長期保留並用 eval 保護）。[Schmid-Evals]
- 超過 10 個 skill 要檢索/embedding 做 shortlist；超過 100 個要治理（admission，ownership，boundaries，lifecycle/semver，定期審計）。[Miraje]
- Skill 當作 harness 的延伸而不是打包的 prompt：子 agent 對立審查，隨機種子腳本，stdout 輸出指示，hooks，記憶（存在 repo 的忽略資料夾），針對最弱模型設計。[Bakaus]（部分）
- 注意跨 harness 差異（如 Codex 需要使用者明確授權才會開 sub-agent）。[Bakaus]
- 在 harness 內放入使用者自訂 agent 檔 (AGENTS.md + skills) 而不是寫 Python 工具；以檔案擴充能力。[Schmid-NoCode]

## 驗證，Evaluator 與品質關卡

- 不要讓同一個 context 自評：獨立 verifier（獨立 context，有 rubric）與 builder 組成迴圈。Claude Code 的 `goal`，Managed Agents 的 `outcomes` 即此概念。[L.Martin] [Prabaker] [Bakaus]
- Planner / Generator / Evaluator（GAN 式）：planner 只寫高層 spec（細節錯誤會級聯放大）；generator 與 evaluator 先協商 sprint contract（何謂完成，可測）；evaluator 要真的操作應用（Playwright，試玩）。卡住時整個丟掉重來而不是持續補丁。代價：慢且貴（範例約 US$200，6 小時）。[Prabaker]
- 確定性驗證：讀 tool-call 歷史判斷 agent 有沒有說謊（點了按鈕不代表成功，登入失敗要回報失敗）。[Kumar]
- 防作弊：agent 會 touch 一個標記檔假裝測過，改為把真實測試輸出做 SHA-256 存入並驗證；要求非程式證據（Playwright 錄影前後對照）；原則是讓做真的比說謊更容易。[Nisi]
- 靜態規則轉成 prompt：自訂 lint 與結構測試（package 隱私，層級依賴，zod schema 去重，fetch 必須帶 timeout 與 retry），且錯誤訊息要寫成補救指示，這是「在對的時間注入指示」。[Lopopolo]
- 各人設（前端架構，可靠性，擴展性）各建一個 review agent，每次 push 在 CI 跑，依文件回報 P2 以上阻擋項。[Lopopolo]
- Hooks：在每次編輯觸發 lint 並阻擋寫入，而不是事後抱怨。「若關卡可以被跳過，就會被跳過。」[Bakaus]
- 規劃勝於事後審查：產品審查 → 系統架構 → program design（型別，簽名，call graph） → 垂直切片；30 分鐘對齊省數小時審查。[Horthy-SF]
- 讓 loop 的輸出小而可讀，一個 loop 最多一個 PR 在審，回饋寫進受版控的 feedback 檔。[Mistele]
- 人工介入點：最後一哩（部署到 staging 前）才交人，並且看「意圖與規格」而非只看 diff。[CastAI]

## 記憶 (Memory)

- 觀念：記憶是 write / manage / read 的控制迴圈，不是資料庫；recall policy 要當一級指標。[Druga]
- 實驗：資料能完全放進 context 時記憶沒有好處且更貴；長程（答案在第 124 步，問題在第 500 步）時，排序過的 decisions ledger 勝過向量 RAG 與「是否需要記憶」的 gating，而且更便宜；即使給 oracle 正確記憶模型也未必採用。[Druga]
- 不要預先規定記憶 schema，讓模型自己組織 (bitter lesson)；檔案或 DB 皆可，重點是簡單可程式化。[L.Martin]
- 同步寫入 (in-band) 會寫出錯誤或區域最佳的記憶，需要離線 "dreaming" 整理（Pokemon 例：原始記憶 5 次全部掉進陷阱，dreaming 後修正）。需用 eval 驗證離線算力值得。[L.Martin] [Bhat&He]
- 記憶種類：短期，長期，共享，episodic，procedural，semantic。[Martinez] [Malcolm]
- 檔案與資料庫：檔案貼近模型習慣且附加便宜，但沒有交易一致性（平行 agent 要用 git worktree），沒有混合/向量搜尋與備份；建議混合式（短期放檔案，長期偏好升級進 DB）。這是 Oracle 的立場，其他講者 (L.Martin) 則主張重點是通用基底。[Martinez] [Malcolm] [L.Martin]
- Skill promotion：把耗時數小時的工作流蒸餾成更好的 SKILL.md，再退役舊版。[Martinez]
- Retro agent：讀 transcript (JSONL) 找 doom loop 與重複工具呼叫，更新通用與框架專屬 markdown 記憶。[Nisi]
- 語意層 (Umwelt)：把「沒說出口的」組織知識寫下來。[Martinez]
- 團隊共享記憶：跨時區共享 context（Git 只記錄程式碼，不記錄意圖）。[Malcolm]

## 沙箱，權限與安全

- 憑證：沙箱內憑證數量應為零；在邊界注入（network proxy 於外送請求時加 token；vault 僅在工具執行時解密）。[Clark] [Bhat&He] [Schmid-NoCode] [Jain]
- Brain / Hands 解耦：模型 + loop 與工具執行環境分離，沙箱壞了就重建重試，brain 壞了從 session log 恢復；hands 可放在客戶 VPC；啟動可平行，首 token 延遲 p50 降 60%，p95 降超過 90%。[Bhat&He] [L.Martin]
- 依任務意圖建模沙箱：新聞室範例（研究員有網路無寫入工具，查核員無網路，發佈者只看過濾後內容），避免「不可信輸入」與「危險工具」同在一處；coding agent 只在 commit 的幾分鐘才有簽章金鑰。[Clark]
- 範圍化能力與意圖式存取：每個任務產生 just-in-time 工具（例如僅限事故頻道的 Slack 讀取）；當請求與原始意圖不符（調查延遲卻要寄信）就拒絕或升級給人。控制放在邊界外、與模型無關。[Jain]
- Auto-review：以唯讀、不可再開子 agent 的 review agent 審核升權請求，輸入含風險分類、完整 transcript 與使用者授權程度（刪掉你要求刪的檔 vs 刪掉從未提到的 .git）。用來減少 approval fatigue 而不開 full access。[Kundel]
- 沙箱技術：OS 層 seatbelt (macOS)，bubblewrap (Linux)，自製 Windows 沙箱；隔離強度從 fork/exec，container，gVisor 到 microVM (Firecracker, Cloud Hypervisor)；fork/exec 與 container 共用核心，有核心漏洞與 noisy neighbor 風險。[Kundel] [Bhardwaj]（部分）
- 沙箱持久化：增量快照，copy-on-write，可在別台節點還原，並支援樹狀搜尋式回溯。[Bhardwaj]（部分）
- 核准是有範圍的執行狀態（誰，哪個 session，哪個工具，參數，期限），會過期而非無限重試。[Govindarajan]
- 供應鏈與身分：Cross App Access (XAA) 讓 agent 沿用 SSO/IdP。[Clark]
- 調查數據：有寫入權限的 agent 比例從 52% 升到 89%（僅取自直播片段，未深讀，引用前請回原片確認）。[WF26]

## 狀態，可靠性與可觀測

- 「模型提議，harness 提交，收據證明」：transcript 不是證據，收據記錄突變，使用的授權，以及是否真的抵達使用者。[Govindarajan]
- 五種失敗：狀態未持久化（每個事實需有單一 owner 與可重現路徑）；多寫入者覆蓋（每個狀態邊界一條有序提交路徑，讀可平行）；工具無期限（deadline，watchdog，取消）；核准漂移；內部成功不等於使用者可見成功。[Govindarajan]
- Run receipt audit 五問：什麼觸發? 繼承什麼狀態? 用了什麼授權? 執行了什麼? 留下什麼證據?[Govindarajan]
- Session 事件日誌四狀態：idle，running，rescheduling，terminated；持久化可觀測並支援恢復。[Bhat&He]
- Idempotency key，鎖，排序，事件去重。[Govindarajan]
- 觀測先於一切：「observability 與 evals 要最先考慮」；觀測也是持續改進的基底。[Chambers] [Trivedy]
- 長程 loop 的耐久性：串流中斷後可續跑，持久化 thread，queue/steer/interrupt。[Bhagwat]
- 傳輸優化：當推論達 1000 token/s，瓶頸變成網路；websocket 模式只傳增量。[Kundel]
- 元件各自擴展而非全塞進一個容器（memory，loop，identity 獨立擴展）。[Chambers]
- 透過標準協定讓前端可替換 (ACP)。[Hancock]

## 長時間，非同步與組織級 harness

- 長時間運行模式：initializer 產出 feature_list.json（用 JSON 較不易被模型覆寫），progress 檔，git；每輪新 context → 看 progress/git log → 做一項 → 驗證 → commit → 標記通過。[Prabaker]
- 以檔案系統共享狀態而非依賴 context；留下 breadcrumb（試過什麼，發現什麼 bug）給下一個模型或人。[Prabaker]
- 雲端 harness：Slack 多人互動，雲端沙箱以增加平行度，產出是 PR；Claw：外部事件監聽，heartbeat，多通道，持久記憶，自我改進。[Bhagwat]
- 組織級 harness（多人共用，有自己的身分與憑證，主動通知）。[L.Martin]
- Teleport（關筆電後遠端沙箱繼續跑）與 Studio（團隊看板審查 plan）；Ferment（里程碑，自評分，部署到 staging）。[CastAI]
- 工作節奏：「每次我需要打 continue 都是 harness 的失敗」；技能說明讓 agent 做到測試綠燈為止。[Lopopolo]
- 時間地平線：METR 曲線（約 1 小時到約 12 小時）與 harness 共演化。[Prabaker] [L.Martin]

## 成本與模型選擇

- 以「每個任務成本」而非「每 token 成本」比較模型（同品質）：例如表面便宜的模型每任務可能更貴。Outcome-aware harness 可依任務自動挑模型並隨新模型上市切換；內部 3 個月 2.5 倍節省且 token 用量增加 1.5 倍。[CastAI]
- 先用前沿模型證明可行，再用 trace 指引做 harness engineering 讓開源模型逼近；之後才考慮 fine-tune，再回頭做 harness engineering；高用量時考慮硬體成本取代 token 成本。[Trivedy]
- 問題難度路由：難的送前沿，簡單的給小模型。[Martinez]
- 不擁有模型權重的 harness 建置者，在與模型一起 RL 訓練的第一方 harness 面前處於劣勢；選型時要把這點算進去。[Horthy-SF]

## 持續改進與評估 (evals)

- Trace mining：讓 agent 讀其他 agent 的 trace，找情緒不佳的互動，壓縮後是否變笨，反事實（換模型會如何）；大型 trace 當外部物件查詢；dense feedback 優於單純通過/失敗。[Trivedy]
- 每次失敗都是 harness bug：修 harness 而不是修產出；每週一天 (garbage collection day) 把重複出現的 slop 轉為文件，lint 或 review agent。[Nisi] [Lopopolo]
- 可驗證的持續學習：失敗轉成可重播環境，修補前後有量測差異，並對舊環境做回歸測試；修補層級 (model, harness, memory) 取最小的耐久變更。[Feizi]
- Skill eval 實作：JSON 測試案例（prompt，should_trigger，預期檢查） + 簡單 runner；多以 regex 斷言，複雜時用 LLM judge；隔離工作區，多次重複，測結果不測路徑，跨 harness，每次修改都跑，保留 eval 即使 skill 退役。[Schmid-Evals]
- 自動優化：GEPA 之類最佳化器直接調整被標記的 prompt。[Bhargava] [Feizi]
- 日常除錯：最有效的是親自讀 trace；其次把 transcript 丟給另一個 agent 找問題；觀察 evaluator 判斷與人類分歧處再調 prompt。[Prabaker]
- 現有 benchmark 缺乏對維護性的懲罰（SWE-Marathon，DeepSWE，Frontier Code 為較新嘗試）。[Horthy-SF]

## 反例，風險與爭議點

- 關燈工廠（不讀程式碼）約三個月後失敗：出現無法靠 prompt 修的 bug，網站掛掉；RL 只獎勵測試通過，不獎勵架構品質。[Horthy-SF]
- 外部資料：導入 AI 後事故與每人 bug 上升，review 品質下滑（Faros AI 報告，經 [Horthy-SF] 引述）。
- Agent 會騙：假造測試通過，假報成功，範圍蔓延（自己把報告發成 PR）。[Nisi] [Kumar] [Jain]
- Fixed harness 在複雜變動環境脆弱；「適應式」harness 目前是概念，且有吸引子鎖定，單一文化，可讀性崩壞等風險。[Chandegra]
- 過度規定的記憶 schema 與過長 skill 都會讓表現變差。[L.Martin] [Nisi]
- 規模化 PR 難以審查：需縮小單次變更，並限制同時開啟 PR 數。[Mistele] [Horthy-SF]
- 技術面成本：重度 evaluator harness 又慢又貴，範例單次約 US$200。[Prabaker]

### 意見分歧

- 檔案 vs 資料庫記憶：Oracle 講者主張混合並以 DB 為主 [Martinez] [Malcolm]；Anthropic 講者主張任何通用基底皆可，避免預設 schema [L.Martin]。
- 自建 vs 依賴官方 harness：Lopopolo 主張從外面 steer 第一方 harness [Lopopolo]；Etsy 與 Cast AI 主張自建以支援本地/多模型 [Bhargava] [CastAI]；Chen&Fioca 建議以 SDK 嵌入 Codex。
- 有無 plan mode：Lopopolo 不使用，若用則把 plan 當 PR 審 [Lopopolo]；Horthy 主張大工作先規劃並對齊 [Horthy-SF]。
- 人要不要在迴圈中：OpenAI 與 Anthropic 傾向讓 agent 全自動（有 evaluator）[Lopopolo] [Prabaker]；HumanLayer 主張仍要讀程式碼 [Horthy-SF] [Mistele]。
- Harness 長期價值：「每次模型進步就刪掉」 [Schmid-NoCode] [Bhat&He] 與「harness 是限制因素」 [Bhat&He] [Bhargava] 並存，實務上是定期以 eval 重新審視。

## 現成資源（文章，程式庫，工具）

- OpenAI 文章 openai.com/index/harness-engineering 與 Latent Space podcast latent.space/p/harness-eng。[Lopopolo]
- Martin Fowler 網站的 "Harness engineering for coding agents"；LangChain 相關文章。[Chambers]
- 12-Factor Agents：github.com/humanlayer/12-factor-agents。[Horthy-12F]
- Codex CLI/harness 開源 (Apache 2, Rust)；Responses API 開放 schema；app-server 協定。[Kundel] [Chen&Fioca]
- Claude Agent SDK，Managed Agents（agent，environment，session 三原件；outcomes；dreaming）。[Bhat&He] [L.Martin]
- Strands Agents SDK + Amazon Bedrock AgentCore（memory，runtime，harness 設定檔）；AWS Agent Toolkit。[Chambers]
- Goose harness 與 Agent Client Protocol (ACP)。[Hancock]
- Pi (minimal harness) 與 Kimchi (github.com/getkimchi/kimchi)。[CastAI] [Nisi]
- Agency 語言 (agency-lang) 內建 interrupts，partial application，GEPA。[Bhargava]
- Docker `sbx` 與 MCP Gateway；Okta XAA。[Clark] [Jain]
- LangSmith Engine（trace 探勘）；RELAI；Arize Alyx。[Trivedy] [Feizi] [Delucia]
- SkillsBench；HarnessBench；Impeccable (impeccable.style) 作為 skill 工程範例。[Schmid-Evals] [Bhargava] [Bakaus]
- Oracle Agent Memory Package 與 workshop repo (agent-harness-workshop)。[Martinez]

---

## 建議的實作順序（綜合以上的歸納，非單一講者主張）

1. 先寫最小 loop + 工具登錄 + 停止條件 + 迭代上限 + trace 紀錄（事件日誌）。[Kumar] [Templestein] [Horthy-12F]
2. 加入確定性 verify 關卡與防作弊（讀 trace，雜湊證據）。[Kumar] [Nisi]
3. 把持久狀態與憑證放在 harness 側，沙箱內憑證為零；設 deadline 與單一寫入者。[Clark] [Govindarajan]
4. Context：頭尾保留 + 可檢索 memory store，延遲載入工具，大資料交給子 agent。[Delucia] [Kundel]
5. Skills 只放 "gotchas"，配 eval 與 ablation；每次換模型重跑。[Nisi] [Schmid-Evals]
6. 加獨立 evaluator（有 rubric 與真實操作工具），長任務才需要 planner 與 sprint contract。[Prabaker]
7. 記憶：先讓模型自己寫檔案；有跨 session 價值再加 recall 排序與離線整理，並量測 recall policy。[L.Martin] [Druga]
8. 建立 trace 探勘與回歸測試的改進迴圈；每個失敗當成 harness bug。[Trivedy] [Feizi] [Nisi]
9. 定期用 eval 找可刪元件。[Bhat&He] [Schmid-NoCode]

---

## 範圍與方法（本筆記的限制）
- 搜尋結果共 208 筆，去重後 158 支影片，其中 55 支逐字稿提到 "harness" 5 次以上。
- 已實際讀過逐字稿與資訊欄的有 32 支 (28 支全文，4 支只讀關鍵字附近段落，標（部分）)；另有 1 支 9 小時直播只取了少數數據點。見文末來源索引。
- 沒讀的：其餘影片已評估相關度，高相關者列在文末「待讀清單」，低相關者已移除，另有 3 支下載失敗（兩個長篇大會直播與一支音樂生成）。
- 逐字稿是 YouTube 英文自動字幕，內容為中文整理；數字與引述以影片內容為準，重要數據請回原片確認。
- 同一觀點有多人提到時，來源標籤會並列。
- 標（部分）的影片只讀了關鍵字附近段落與資訊欄，包含 [Prabaker] [Bakaus] [Templestein] [Bhardwaj] [Pai]；其中 [Prabaker] 在內文引用較多，細節請特別回原片確認。
- [WF26] 為 9 小時直播，只取了少數段落，引用的數據未經深讀驗證。
- 廠商影片（Oracle、Docker、Cast AI、RELAI）立場偏向自家產品，「意見分歧」一節已盡量並列其他講者的觀點。

---

## 來源索引

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Kumar | [Harnesses in AI: A Deep Dive, Tejas Kumar (IBM)](https://www.youtube.com/watch?v=C_GG5g38vLU) | 全文 |
| Chambers | [Harness Engineering: Building the Production Cage, Mike Chambers (AWS)](https://www.youtube.com/watch?v=gxVZ_1tuuq4) | 全文 |
| Lopopolo | [Harness Engineering: How to Build Software When Humans Steer, Ryan Lopopolo (OpenAI)](https://www.youtube.com/watch?v=am_oeAoUhew) | 全文 (含 Q&A) |
| Martinez | [Total Recall: Agent Memory and Harness Engineering, Ignacio Martinez (Oracle)](https://www.youtube.com/watch?v=xs-ob87TTzg) | 全文 |
| Chandegra | [Beyond the Harness: Adaptive Engineering, Rajiv Chandegra](https://www.youtube.com/watch?v=qdZzND79mcg) | 全文 |
| Bhat&He | [Claude Managed Agents and Evolution of Agentic Surfaces (Anthropic)](https://www.youtube.com/watch?v=K0X9QDRkIdg) | 全文 |
| Prabaker | [Anthropic Workshop: Build Agents That Run for Hours](https://www.youtube.com/watch?v=mR-WAvEPRwE) | 部分 (關鍵字段落 + 資訊欄) |
| L.Martin | [Claude for Long-Horizon Tasks, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=9QebvrrY3KY) | 全文 |
| Chen&Fioca | [Future-Proof Coding Agents (OpenAI)](https://www.youtube.com/watch?v=wVl6ZjELpBk) | 全文 |
| Trivedy | [Improving Agents is a Data Mining Problem (LangChain)](https://www.youtube.com/watch?v=CvRngaQZQ3Y) | 全文 |
| Govindarajan | [The Model Was Right. The Harness Failed. (OpenAI)](https://www.youtube.com/watch?v=BInpv7lGp1o) | 全文 |
| Bhargava | [What if the harness mattered more than the model? (Etsy)](https://www.youtube.com/watch?v=2e9ANoOEn28) | 全文 |
| Bhagwat | [Every Harness Will Become A Claw (Mastra)](https://www.youtube.com/watch?v=8qWIPUia2O8) | 全文 |
| Miraje | [Skills are new features: Skill-Centric Harness (FactSet)](https://www.youtube.com/watch?v=7jjudsEhBtM) | 全文 |
| Kundel | [How Codex Works (OpenAI)](https://www.youtube.com/watch?v=shRR1e2HXMk) | 全文 |
| Hancock | [ACP: The Universal Remote Control for AI Agents (Block)](https://www.youtube.com/watch?v=YkNulwcc5jk) | 全文 |
| CastAI | [Stop Rationing Tokens: Let the Harness Pick the Model (Kimchi)](https://www.youtube.com/watch?v=48YUYDjwfYY) | 全文 (廠商宣傳性質) |
| Druga | [Memory Harnesses for Long-Running Research Agents (Sakana.ai)](https://www.youtube.com/watch?v=R3-anFK1YM8) | 全文 |
| Bakaus | [The Dark Arts of Skill Engineering](https://www.youtube.com/watch?v=SQMCtZX3trg) | 部分 (關鍵字段落 + 資訊欄) |
| Malcolm | [No Memory, No Harness (Oracle)](https://www.youtube.com/watch?v=jA_x7F8caHI) | 全文 (廠商宣傳性質) |
| Horthy-SF | [Why Software Factories Fail, Dex Horthy](https://www.youtube.com/watch?v=Ib5GBkD555M) | 全文 |
| Templestein | [Make your own event-sourced agent harness (Iterate)](https://www.youtube.com/watch?v=vi-2nasppAg) | 部分 (關鍵字段落 + 資訊欄) |
| Feizi | [Continual Learning for AI Agents (RELAI)](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | 全文 (廠商性質) |
| Jain | [Unlock Agent Autonomy: The Runtime for AI-Native Systems (Docker)](https://www.youtube.com/watch?v=zaGyGgLW3SM) | 全文 (廠商性質) |
| Nisi | [How I deleted 95% of my agent skills (WorkOS)](https://www.youtube.com/watch?v=vy7o1g2iHY8) | 全文 |
| Delucia | [How we solved Context Management in Agents (Arize)](https://www.youtube.com/watch?v=esY99nYXxR4) | 全文 |
| Mistele | [Loop Engineering from First Principles (HumanLayer)](https://www.youtube.com/watch?v=xIt_mTQp6mY) | 全文 |
| Schmid-Evals | [Don't Ship Skills Without Evals (Google DeepMind)](https://www.youtube.com/watch?v=0vphxNt4wyk) | 全文 |
| Horthy-12F | [12-Factor Agents (HumanLayer, 2025-07)](https://www.youtube.com/watch?v=8kMaTybvDUw) | 全文 |
| Clark | [How Many Credentials Should Your AI Agent Have? Zero. (Docker)](https://www.youtube.com/watch?v=ZUZVNKFSmTM) | 全文 (廠商性質) |
| Schmid-NoCode | [Agents Without Code: Skills, YAML, and Filesystems (Google DeepMind)](https://www.youtube.com/watch?v=fjF8EKnxKCU) | 全文 |
| Bhardwaj | [From fork() to Fleet: Agent Sandbox Cloud (OpenAI)](https://www.youtube.com/watch?v=OqM67QG_Ikk) | 部分 (關鍵字段落 + 資訊欄) |
| Pai | [Code Mode: Let the Code do the Talking — Sunil Pai, Cloudflare](https://www.youtube.com/watch?v=8txf05vVVl4) | 部分 (僅讀關鍵字附近段落) |
| WF26 | [WF26 Harness Engineering 全天直播 (551 分鐘)](https://www.youtube.com/watch?v=I2cbIws9j10) | 僅少數段落, 未深讀 |

## 待讀清單

以下影片的逐字稿提到 harness 的次數偏多，但尚未讀完。我依標題與說明評估相關度，與本筆記主題較遠的（後訓練、kernel、本地模型硬體、一般 evals、keynote 合輯等）已移除。讀完後再把重點併入上方對應章節。

### 高相關（優先讀）

- [Your coding agent doesn't always follow your rules — Talha Sheikh, Checkout.com](https://www.youtube.com/watch?v=MpZzWMdmQCE)：以 hook 在每次動作即時強制規則，對應「驗證與品質關卡」的 hooks。
- [How We Built an Agent That Improves Itself — Zubin Aysola, Weights & Biases](https://www.youtube.com/watch?v=XyV6bSMyq-I)：agent 自己改自己的做法，對應「持續改進與評估」。
- [The Missing Primitive for Agent Swarms — Lou Bichard, Ona](https://www.youtube.com/watch?v=5Sui_OnSRlY)：背景 agent 叢集的基礎設施（Stripe Minions、Ramp Inspect 類型），對應「長時間、非同步與組織級 harness」。
- [Scaling Agents on Kubernetes with acpx and ACP — Onur Solmaz, OpenClaw](https://www.youtube.com/watch?v=VaS2h-dY1-4)：以 Kubernetes 與 ACP 規模化執行 agent，對應「工具與 ACP」。
- [An Interaction Is All You Need — Ivan Leo, Google DeepMind](https://www.youtube.com/watch?v=8aVbXXvJUY4)：Gemini Interactions API 與 Managed Agents，對應「抽象層級演進」。
- [The Human Is an Async API — Melanie Warrick, Temporal](https://www.youtube.com/watch?v=jc3kbZkuHTo)：等待人類回應時的耐久執行，對應「狀態、可靠性與可觀測」。
- [Claude Agent SDK [Full Workshop] — Thariq Shihipar, Anthropic](https://www.youtube.com/watch?v=TqC1qOfiVcQ)：官方 harness 的 SDK 用法，對應「自建 vs 依賴官方 harness」。
- [AI-Native Organisations Run on Skills — Imad Touil, QuantumBlack](https://www.youtube.com/watch?v=M05vON8i0aI)：技能的組織級治理，可與 [Miraje] 對照。
- [Don't Build Agents, Build Skills Instead — Barry Zhang & Mahesh Murag, Anthropic](https://www.youtube.com/watch?v=CEvIs9y1uog)：Anthropic 對 skills 的主張，可與 [Nisi] [Schmid-Evals] 對照。
- [The Great Loops Debate — Dex Horthy, Geoff Huntley 等](https://www.youtube.com/watch?v=c35YoMdnI78)：loop 的實務效果辯論，對應「意見分歧」。
- [Ralph Loops: Build Dumb AI Loops That Ship — Chris Parsons, Cherrypick](https://www.youtube.com/watch?v=2TLXsxkz0zI)：Ralph loop 的完整 workshop，對應「Agent loop 與控制流」。
- [Recursive Coding Agents — Raymond Weitekamp, OpenProse](https://www.youtube.com/watch?v=3hXJI2q0Jz8)、[RLM: Recursive Language Models for Large Codebases — Shashi, Superagentic AI](https://www.youtube.com/watch?v=8oyalrfwgjw)：以遞迴方式把 context 外部化，對應「Context engineering」。
- [OpenAI Codex Masterclass — Vaibhav Srivastav & Katia Gil Guzman](https://www.youtube.com/watch?v=MhHEGMFCEB0)：Codex 的 plugins、automations 與 subagents 實務。

### 次要候補（有餘力再讀）

- [No Vibes Allowed — Dex Horthy, HumanLayer](https://www.youtube.com/watch?v=rmvDxxNubIg)：Horthy 2025 年版的規劃與對齊，內容與 [Horthy-SF] 有重疊。
- [The Multi-Agent Architecture That Actually Ships — Luke Alvoeiro, Factory](https://www.youtube.com/watch?v=ow1we5PzK-o)：多 agent 協作的實務分類，可補「子 agent 作法」。
- [Building your own software factory — Eric Zakariasson, Cursor](https://www.youtube.com/watch?v=rnDm57Py54A)：多 agent 工廠式開發的做法，可補「長時間與組織級」。
- [Full Walkthrough: Workflow for AI Coding — Matt Pocock](https://www.youtube.com/watch?v=-QFHIoCo-Ko)：AI 輔助開發的完整工作流。
- [Evals Are Broken, Use Them Anyway — Ara Khan, Cline](https://www.youtube.com/watch?v=QuuIywMG4s8)：評估基礎設施的設定如何影響分數（Terminal Bench 例）。
- [Malleable Evals — Vincent Koc, OpenClaw](https://www.youtube.com/watch?v=4VhbYlfC7Gs)：對適應式系統做評估，可與 [Chandegra] 對照。
- [Turn 10,994 Notes Into Memory — Paul Iusztin & Louis-François Bouchard](https://www.youtube.com/watch?v=ZRM_TfEZcIo)：多 agent 的記憶實作課程，可與 [Druga] [L.Martin] 對照。
- [How We Build Effective Agents — Barry Zhang, Anthropic](https://www.youtube.com/watch?v=D7_ipDqhtwk)：Barry Zhang 2025 年的 agent 設計總論，偏入門。

另有 Chris Parsons 的 Ralph Loops 逐字稿未出現 harness 一詞，仍因主題相關列入上方。
