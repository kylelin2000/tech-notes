# AI Agents 筆記

- [concepts/prompt-to-graph.md](concepts/prompt-to-graph.md)：Prompt → Context → Harness → Loop → Graph 的發展史，以及每一層人的位置；含從零實作 agent（Thorsten Ball）、經典綜述（Weng、Huyen）與多 agent 失敗分類（MAST）
- [concepts/agentic-engineering-patterns.md](concepts/agentic-engineering-patterns.md)：Simon Willison〈Agentic Engineering Patterns〉閱讀整理，用 coding agent 開發的原則、測試與驗證習慣、常用 prompt
- [concepts/harness-engineering.md](concepts/harness-engineering.md)：AI Engineer 頻道 harness 相關演講的實作做法彙整（loop、context、skills、驗證、記憶；沙箱與評估已拆出），每項標註來源影片
- [concepts/agent-security.md](concepts/agent-security.md)：Agent 安全做法彙整（沙箱隔離、憑證注入、權限核准、containment，從 harness-engineering 拆出），加上 prompt injection 的系統性防禦（lethal trifecta、六種設計模式、CaMeL、OWASP）與套用到 Hermes 的檢查
- [concepts/agent-evals.md](concepts/agent-evals.md)：Agent 持續改進與評估做法彙整（trace mining、skill eval、eval flywheel、harness 變更發布），從 harness-engineering 拆出
- [concepts/agent-tools.md](concepts/agent-tools.md)：寫給 agent 用的工具與 MCP server 設計（切分、命名、回傳量、錯誤訊息、工具過多時的處理、MCP spec 2026-07-28 的授權與安全），以及 MCP / Agent Client Protocol / A2A 比較
- [concepts/api-primitives.md](concepts/api-primitives.md)：API 層基本元件：Claude 與 OpenAI 的 structured outputs、tool calling schema、prompt caching（機制、TTL、計價、失效條件）對照
- [concepts/agent-observability.md](concepts/agent-observability.md)：OpenTelemetry GenAI 慣例、可自架的 Langfuse / Phoenix，以及 Claude Code 自身的 OTel 遙測
- [concepts/coding-agent-ci.md](concepts/coding-agent-ci.md)：把 Claude Code、Codex、Cursor 接進 PR 與 CI（觸發方式、權限、成本控制、最小 workflow）
- [concepts/productivity-evidence.md](concepts/productivity-evidence.md)：AI 對開發者生產力的實證：METR 2025 RCT 與 2026 後續、DORA 2025
- [concepts/spec-driven-development.md](concepts/spec-driven-development.md)：Spec-driven development：spec-kit、Kiro、Böckeler 的評析，與 superpowers、compound engineering 對照

## 書籤：Agent 工具與框架

- [obra/superpowers](https://github.com/obra/superpowers)：給 coding agent 的軟體開發方法論與 skills 框架，brainstorming → 寫計畫 → TDD 實作 → code review 自動觸發；支援 Claude Code、Codex、Cursor、Gemini CLI 等多種 agent
- [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)：Every 的 Compound Engineering 工作流 plugin，核心迴圈是 brainstorm → plan → work → review → compound（把經驗寫回 docs/solutions/ 讓下一輪更輕鬆）；支援 14 種 agent host
- [dietrichgebert/ponytail](https://github.com/dietrichgebert/ponytail)：讓 agent 當「最懶的資深工程師」的 skill，寫程式前先走「由簡到繁」階梯（需要嗎 → 現成的 → stdlib → 一行），只寫最少的程式碼；附 `/ponytail-review`、`/ponytail-audit` 審查指令，支援 Claude Code、Codex、Cursor、Gemini、Copilot 等約 20 種 agent
- [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)：讓 agent 回覆先給行動、步驟編號、結尾只留一個具體下一步，去掉寒暄與冗長前言的 skill／plugin，適合注意力有限時讀回覆；支援 Claude Code、Cursor、Codex、Gemini、OpenCode 等
- [affaan-m/ECC](https://github.com/affaan-m/ECC)（[Skillselion 頁面](https://skillselion.com/marketplace/affaan-m/ECC)）：Everything Claude Code，一整套 agent harness 工程系統，約 71 個 agents、311 個 skills、97 個命令，加上 hooks、rules、記憶與持續學習、AgentShield 安全掃描；Claude Code 原生支援最完整，Codex、Qoder 有原生 plugin，Cursor、OpenCode、Gemini、Copilot 為部分適配

## 工具

- 來源表：[tools/sources/ai-agents.py](../tools/sources/ai-agents.py)，把筆記引用的來源抓一次存進 `tools/.cache/ai-agents/`（檔名即 `[簡稱]`），429 就停
- 檢查簡稱與連結：`python3 tools/check.py ai-agents`
- 其他工具與整理流程見 [tools/](../tools/README.md)
