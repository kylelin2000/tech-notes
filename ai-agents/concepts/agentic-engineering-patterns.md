# Agentic Engineering Patterns（Simon Willison）：程式碼生產外包，判斷與驗證不外包

> 主線：把程式碼生產交給 coding agent，但「判斷、驗證、審查」不能外包。所有高價值模式都圍繞兩件事：**給 agent 自我驗證的工具**（測試、瀏覽器自動化、Showboat），以及**你自己把關**（先看測試失敗、自己手測、自己審 PR）。
>
> 原文：<https://simonwillison.net/guides/agentic-engineering-patterns/>｜整理日期：2026-10-06｜AI 協助閱讀後整理，限制見 §8。

核心定義：**agent 就是在 loop 中跑工具以達成目標的 LLM**，coding agent 的關鍵能力是「能執行自己寫的程式碼」。Willison 特別區分這與 vibe coding：vibe coding 是未經審查的原型程式碼，兩者不該混為一談。

與本 repo 其他筆記的關係：「給 agent 自我驗證的工具」對應 [Prompt → Loop → Graph](prompt-to-graph.md) 裡的 Harness 層；本篇是在 Harness 與 Loop 之上，從使用者角度整理的實務習慣。

## 速查：常用 prompt 與做法

| 情境 | prompt／做法 | 效果 |
| --- | --- | --- |
| 開新 session | `Review changes made today` | 讓 agent 看 git log，快速載入 context |
| 新 session 開場 | `First run the tests` | agent 知道有測試、感受專案規模、進入測試心態 |
| 新功能或修 bug | `Use red/green TDD` | test-first：先看測試失敗再實作 |
| Git 一團亂 | `Sort out this git mess for me` | 解衝突、整理 commits |
| 不熟的 CLI 工具 | `uvx <tool> --help` | 讓 agent 自學工具用法 |
| 要 agent 參考既有實作 | `clone 某 repo 到 /tmp 當參考` | 用另一份程式碼溝通，勝過長篇解釋；放 /tmp 避免混進 commit |
| 測試過程要留證據 | 用 Showboat 記錄 | `exec` 記錄「指令＋真實輸出」，防止 agent 造假 |
| 看不懂 agent 寫的東西 | 叫 agent 產出 linear walkthrough | 逐檔解說，償還認知債 |

## 1. 原則（Principles）

章節：[What is agentic engineering?](https://simonwillison.net/guides/agentic-engineering-patterns/what-is-agentic-engineering/)、[Writing code is cheap now](https://simonwillison.net/guides/agentic-engineering-patterns/code-is-cheap/)、[Hoard things you know how to do](https://simonwillison.net/guides/agentic-engineering-patterns/hoard-things-you-know-how-to-do/)、[AI should help us produce better code](https://simonwillison.net/guides/agentic-engineering-patterns/better-code/)、[Anti-patterns](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/)

- **寫程式碼變便宜了，但「好程式碼」仍有成本**。能跑、被驗證過能跑、解對問題、處理錯誤、有測試、有文件，這些還是要人把關。新習慣：直覺說「不值得花時間做」時，仍丟給非同步 agent 試試，十分鐘後回來看，最壞只是浪費 token。
- **囤積你會做的事**。把解決過的問題存成可運行的範例（blog、TIL、小工具 repo）。最強的 prompt 模式之一：給 agent 兩個能動的範例，叫它組合成新東西。有 agent 之後，每個 trick 只需要搞懂一次。
- **AI 應該讓程式碼更好，不是更差**。技術債中「概念簡單但費時」的修復（重命名、拆大檔案、合併重複功能）正是 agent 的好工作，丟去背景跑，用 PR 驗收。也可用 agent 做探索式原型（例如先寫負載測試模擬，驗證 Redis 適不適合）。Compound Engineering：每個專案結束做 retrospective，把學到的寫回指令，讓下次 agent 跑得更好。
- **反模式：不要把沒看過的程式碼丟給同事審**。提 PR 前你有責任先驗證它能動；小 PR 勝過大 PR；連 agent 寫的 PR 描述也要自己讀過。

## 2. Agent 運作原理、Git、Subagents

章節：[How coding agents work](https://simonwillison.net/guides/agentic-engineering-patterns/how-coding-agents-work/)、[Using Git with coding agents](https://simonwillison.net/guides/agentic-engineering-patterns/using-git-with-coding-agents/)、[Subagents](https://simonwillison.net/guides/agentic-engineering-patterns/subagents/)

**運作原理**：LLM + system prompt + tools，跑在 loop 裡。值得知道的細節：token 計費、cached input tokens（所以 agent 會避免改動對話前綴）、reasoning 對 debug 特別有幫助。想深入就自己寫個 mini agent loop，幾十行就夠。

**Git**：

- 不用背指令，但要知道「可能做什麼」，agent 都會。
- 高價值用法：review 今天的改動、萬能解衝突、`git bisect` 找 bug 來源（agent 幫你寫測試腳本）、`reflog` 找回丟失的程式碼。
- **把 Git 歷史當成「被編輯過的故事」而非不可變的紀錄**：agent 很擅長 rewrite history、合併 commits、從舊 repo 抽程式碼建成新 repo 並保留歷史。

**Subagents**：context window 是稀缺資源，subagent 的核心價值是**保護主 context**。Explore subagent 先探索 repo 回報摘要；可平行跑多個加速；專職 subagent（reviewer、test runner、debugger）可隱藏雜訊輸出。但別過頭，主 agent 有 token 的話自己也能做。

## 3. 測試與 QA

章節：[Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)、[First run the tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)、[Agentic manual testing](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/)

全指南最硬核的部分。

- **`Use red/green TDD`**：四個字換來 test-first。先看測試失敗（red）再實作（green），防住「程式碼不能動」和「寫了沒人用」兩大風險。
- **`First run the tests`**：每個新 session 開場先說這句。
- **永遠不要假設沒執行過的程式碼能動**。測試通過不代表能用，還要 manual testing：`python -c` 試邊界情況、`curl` 探索 API、Playwright／Rodney 瀏覽器自動化（讓 agent 看截圖判斷 UI）。
- **Showboat**：讓 agent 把測試過程寫成文件，`exec` 記錄「指令＋真實輸出」，防止 agent 造假。測試中發現的 bug 就地用 TDD 修，順便補進永久測試。

## 4. 理解程式碼（償還認知債）

章節：[Linear walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/)、[Interactive explanations](https://simonwillison.net/guides/agentic-engineering-patterns/interactive-explanations/)

- vibe code 出來的東西看不懂，就是 cognitive debt，會拖慢後續開發。
- **Linear walkthrough**：叫 agent 用 Showboat 產出結構化的逐檔解說文件，並明確要它用 grep／sed 摘片段，避免幻覺。連 40 分鐘做出的玩具專案都能變成學習機會。
- **互動式解釋**：光看 walkthrough 還不懂，就叫 agent 做動畫解釋（原文示範 word cloud 的阿基米德螺旋放置演算法動畫）。

## 5. 實戰案例的 prompt 心法

章節：[GIF optimization](https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/)、[Adding a new content type](https://simonwillison.net/guides/agentic-engineering-patterns/adding-a-new-content-type/)

- **GIF 優化工具**（把 Gifsicle 編譯成 WASM）：agent 擅長 trial-and-error，人早就放棄的編譯錯誤它能暴力試出來。關鍵是給它驗證手段（用 Rodney 自動測試）。
- **blog-to-newsletter 加新內容類型**：極短 prompt 完成任務的三個要素：
  1. clone 某個 repo 到 /tmp 當參考，用另一份程式碼當溝通媒介。
  2. 「模仿 Atom feed 的做法」，指向現有行為，省去描述邏輯。
  3. 叫它自己起 server 驗證，並跟線上版比對。
- 通用技巧：`uvx <tool> --help` 讓 agent 自學工具；tool 的 help 文字本身要為 agent 設計。

## 6. 附錄：作者的私人 prompts

章節：[Prompts I use](https://simonwillison.net/guides/agentic-engineering-patterns/prompts/)

內容有：Artifacts 禁用 React（保持純 HTML 可複製部署）、校對 prompt、alt text prompt、podcast 摘錄。值得注意的底線：**凡是署他名字、表達觀點的文字，LLM 一律不代寫**，只用來校對。

## 7. 可帶走的做法

1. 開 session 先 `First run the tests`，再 `Review changes made today`。
2. 新功能一律 `Use red/green TDD`，再加手動測試。
3. 先給 agent 驗證手段（測試、瀏覽器自動化、Showboat），再要它做大改動。
4. 看不懂就叫它出 walkthrough，不要硬留不理解的程式碼。
5. 技術債型的重構丟背景跑，用 PR 驗收。
6. 提 PR 前自己先看過、先跑過。

## 8. 驗證基準與限制

- 本篇為 AI 協助閱讀指南後整理，尚未逐章對照原文；引用前建議回原文確認。
- 指南各章仍在演進，作者自述之後會持續更新，值得回來重看新章節。
- 速查表與 §7 是整理者歸納，不是原文逐字，prompt 字面以原文為準。

## 核心來源

- [Simon Willison, Agentic Engineering Patterns（指南首頁）](https://simonwillison.net/guides/agentic-engineering-patterns/)
