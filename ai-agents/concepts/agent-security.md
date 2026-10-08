# Agent 安全：沙箱、權限與憑證

本篇從 [harness-engineering.md](harness-engineering.md) 的「沙箱，權限與安全」章節拆出，內容逐條照搬。內文的 [簡稱]（如 [Clark]）對應文末「來源」表，完整索引見原筆記的來源索引。

## 做法

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
- Credential-injecting proxy：在外送請求的 header 動態注入 token，模型只執行程式、永遠看不到密鑰，被 prompt injection 也無從洩漏 (Managed Agents)。[Leo]
- Swiss cheese 多層防禦：model alignment、harness（權限、prompt、對 bash 指令做 AST parsing）、sandbox（網路與檔案系統隔離）；重點是阻止外洩，sandbox 放在託管環境而不是滿是 secrets 的個人電腦。[Shihipar]
- 不要讓 secrets 以檔案形式存在：權限不足的 agent 會在檔案系統裡找更高權限的 token；RL 讓模型更會找漏洞，安全必須來自外圍基礎設施。[LoopsDebate]
- 隔離層級：開發任務用 VM 而不只是 container（container 不是牢靠邊界，K8s 上還有 noisy neighbor）；每個 cloud agent 一台獨立 VM，連 DB 與服務一起，避免 worktree 共用 DB / cache 的副作用。對照：Pocock 用 git worktree + Docker，Solmaz 用每任務一個 K8s pod。[Bichard] [Zakariasson] [Pocock] [Solmaz]
- 不可逆判準：「這件事能不能不尷尬地復原？」不能就不做，留註記交還給人。實作：email 只准草稿、AI 專屬金鑰保留稽核軌跡、開發工具唯讀、跑在獨立 VPS；留意 lethal trifecta（不可信輸入 + 網路 + 機密資料同在）。[Parsons]
- 依角色設 sandbox：review 與資安分析類 subagent 一律 read-only，要產文件的才給寫入。Guardian approvals（Codex 實驗功能）讓 subagent 判斷特權操作要不要叫人，以降低核准疲勞、取代 YOLO mode，概念同 [Kundel] 的 auto-review（講者現場示範沒成功）。[Codex-MC]
- 用 hook 禁止 agent 修改最敏感的區域（加密、認證）；為特定 invariant 建 security sentinel automation，只在改到相關檔案的 PR 上跑。[Zakariasson]
- Containment 優先於 human-in-the-loop：使用者約核准 93% 的 permission prompt，審核疲勞讓人工把關不可靠。Claude Code 用 OS 級 sandbox（Seatbelt / bubblewrap）預設允許讀取、寫入限於 workspace、網路預設禁止，沙箱內不再打斷使用者，permission prompt 減少 84%。[Anthropic-Contain]
- 隔離強度配合使用者的監督能力：claude.ai 用 gVisor 臨時容器；Claude Code 用 OS sandbox 加人工核准（開發者看得懂 bash）；Cowork 面向非技術使用者，用本機 VM 當常開的硬邊界，憑證留在 host keychain，VM 只拿 per-session、可撤銷的縮權 token。[Anthropic-Contain]
- 事故教訓是「自己寫的元件最脆弱」：trust dialog 之前就執行了 project hook、allowlist 內的 api.anthropic.com 被拿來外洩資料，而 hypervisor、seccomp、gVisor 都守住了。對應做法：project-open、config-load、localhost listener 一律視同外部請求；egress allowlist 當成 capability grant（VM 內的 MITM proxy 只放行帶本 VM session token 的請求）；symlink 先解析再驗證路徑；掛載分 read-only、read-write、read-write-no-delete。[Anthropic-Contain]
- Agent loop 放在 VM 外、只把程式碼執行放進 VM（VM 起不來時 agent 仍能回應除錯，同 [Bhat&He] 的 brain / hands 分離）；tool 回傳值進入 context 前由小而快的 classifier 檢查。Auto mode 的 classifier 約擋下 83% 過度積極行為、誤擋約 0.4% 良性指令，只能當縱深防禦的一層。[Anthropic-Contain]
- 瀏覽器本身就是 sandbox：檔案用 File System Access API（目前僅 Chrome）、網路用 CSP + `<iframe sandbox>`、程式碼執行放 Web Worker 裡的 WebAssembly，不需要數 GB 的本機容器。[Willison]

## 相關筆記

- [harness-engineering.md](harness-engineering.md)：Harness 實作做法總覽與完整來源索引
- [agent-evals.md](agent-evals.md)：持續改進與評估（evals）

## 來源

### 演講與影片

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Clark | [How Many Credentials Should Your AI Agent Have? Zero. (Docker)](https://www.youtube.com/watch?v=ZUZVNKFSmTM) | 全文 (廠商性質) |
| Bhat&He | [Claude Managed Agents and Evolution of Agentic Surfaces (Anthropic)](https://www.youtube.com/watch?v=K0X9QDRkIdg) | 全文 |
| Schmid-NoCode | [Agents Without Code: Skills, YAML, and Filesystems (Google DeepMind)](https://www.youtube.com/watch?v=fjF8EKnxKCU) | 全文 |
| Jain | [Unlock Agent Autonomy: The Runtime for AI-Native Systems (Docker)](https://www.youtube.com/watch?v=zaGyGgLW3SM) | 全文 (廠商性質) |
| L.Martin | [Claude for Long-Horizon Tasks, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=9QebvrrY3KY) | 全文 |
| Kundel | [How Codex Works (OpenAI)](https://www.youtube.com/watch?v=shRR1e2HXMk) | 全文 |
| Bhardwaj | [From fork() to Fleet: Agent Sandbox Cloud (OpenAI)](https://www.youtube.com/watch?v=OqM67QG_Ikk) | 部分 (關鍵字段落 + 資訊欄) |
| Govindarajan | [The Model Was Right. The Harness Failed. (OpenAI)](https://www.youtube.com/watch?v=BInpv7lGp1o) | 全文 |
| WF26 | [WF26 Harness Engineering 全天直播 (551 分鐘)](https://www.youtube.com/watch?v=I2cbIws9j10) | 僅少數段落, 未深讀 |
| Leo | [An Interaction Is All You Need, Ivan Leo (Google DeepMind)](https://www.youtube.com/watch?v=8aVbXXvJUY4) | 全文 (agent 摘要，廠商性質) |
| Shihipar | [Claude Agent SDK [Full Workshop], Thariq Shihipar (Anthropic)](https://www.youtube.com/watch?v=TqC1qOfiVcQ) | 全文 (agent 摘要，廠商性質) |
| LoopsDebate | [The Great Loops Debate, Dex Horthy, Geoff Huntley, Ian Livingstone, Greg Pstrucha](https://www.youtube.com/watch?v=c35YoMdnI78) | 全文 (agent 摘要) |
| Bichard | [The Missing Primitive for Agent Swarms, Lou Bichard (Ona)](https://www.youtube.com/watch?v=5Sui_OnSRlY) | 全文 (agent 摘要) |
| Zakariasson | [Building your own software factory, Eric Zakariasson (Cursor)](https://www.youtube.com/watch?v=rnDm57Py54A) | 全文 (agent 摘要，廠商性質) |
| Pocock | [Full Walkthrough: Workflow for AI Coding, Matt Pocock](https://www.youtube.com/watch?v=-QFHIoCo-Ko) | 全文 (agent 摘要) |
| Solmaz | [Scaling Agents on Kubernetes with acpx and ACP, Onur Solmaz (OpenClaw)](https://www.youtube.com/watch?v=VaS2h-dY1-4) | 全文 (agent 摘要) |
| Parsons | [Ralph Loops: Build Dumb AI Loops That Ship, Chris Parsons (Cherrypick)](https://www.youtube.com/watch?v=2TLXsxkz0zI) | 全文 (agent 摘要) |
| Codex-MC | [OpenAI Codex Masterclass, Vaibhav Srivastav & Katia Gil Guzman (OpenAI)](https://www.youtube.com/watch?v=MhHEGMFCEB0) | 全文 (agent 摘要，廠商性質) |

### 文章與程式庫

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-Contain | [How we contain Claude across products (Anthropic Engineering)](https://www.anthropic.com/engineering/how-we-contain-claude) | 全文 (agent 摘要) |
| Willison | [the browser is the sandbox, Simon Willison](https://simonwillison.net/2026/Jan/25/the-browser-is-the-sandbox/) | 全文 (agent 摘要，轉介 Paul Kinlan 的文章) |
