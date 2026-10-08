# AI Agents 筆記

- [concepts/prompt-to-graph.md](concepts/prompt-to-graph.md)：Prompt → Context → Harness → Loop → Graph 的發展史，以及每一層人的位置
- [concepts/agentic-engineering-patterns.md](concepts/agentic-engineering-patterns.md)：Simon Willison〈Agentic Engineering Patterns〉閱讀整理，用 coding agent 開發的原則、測試與驗證習慣、常用 prompt
- [concepts/harness-engineering.md](concepts/harness-engineering.md)：AI Engineer 頻道 harness 相關演講的實作做法彙整（loop、context、skills、驗證、記憶；沙箱與評估已拆出），每項標註來源影片
- [concepts/agent-security.md](concepts/agent-security.md)：Agent 安全做法彙整（沙箱隔離、憑證注入、權限核准、containment），從 harness-engineering 拆出
- [concepts/agent-evals.md](concepts/agent-evals.md)：Agent 持續改進與評估做法彙整（trace mining、skill eval、eval flywheel、harness 變更發布），從 harness-engineering 拆出
- [hermes/architecture.md](hermes/architecture.md)：Hermes Agent 的架構與設計決策

## 書籤：Agent 工具與框架

- [obra/superpowers](https://github.com/obra/superpowers)：給 coding agent 的軟體開發方法論與 skills 框架，brainstorming → 寫計畫 → TDD 實作 → code review 自動觸發；支援 Claude Code、Codex、Cursor、Gemini CLI 等多種 agent
- [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)：Every 的 Compound Engineering 工作流 plugin，核心迴圈是 brainstorm → plan → work → review → compound（把經驗寫回 docs/solutions/ 讓下一輪更輕鬆）；支援 14 種 agent host
