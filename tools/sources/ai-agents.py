#!/usr/bin/env python3
"""ai-agents 筆記的來源表。抓一次就存進 tools/.cache/ai-agents/<簡稱>.txt，已存在的跳過。ID 就是筆記裡的 [簡稱]。

python3 tools/sources/ai-agents.py           # 全部
python3 tools/sources/ai-agents.py CaMeL     # 只跑指定 ID

- 網頁轉純文字；GitHub raw 與網址以 .md 結尾的 Markdown 原樣存；PDF 用 pdftotext。
- 429、403、CAPTCHA 的處理見 tools/fetch.py。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch

CACHE = Path(__file__).resolve().parents[1] / ".cache" / "ai-agents"
fetch.SPACING = 3.0  # 秒；arXiv 間隔太短會 429
RAW = "https://raw.githubusercontent.com/"
SPEC = "https://modelcontextprotocol.io/specification/latest/"
# GenAI semconv 已從 semantic-conventions 搬到獨立 repo（2026-10 確認）
OTEL = RAW + "open-telemetry/semantic-conventions-genai/main/docs/gen-ai/"
# 兩家 API 文件網址後加 .md 可拿 Markdown 版（2026-10 確認）
CLAUDE = "https://platform.claude.com/docs/en/"
OPENAI = "https://developers.openai.com/api/docs/guides/"

SOURCES = {
    # 工具 / MCP server 設計
    "Anthropic-Tools": "https://www.anthropic.com/engineering/writing-tools-for-agents",
    "Anthropic-CodeExec": "https://www.anthropic.com/engineering/code-execution-with-mcp",
    "Anthropic-AdvTools": "https://www.anthropic.com/engineering/advanced-tool-use",
    "MCP-Changelog": SPEC + "changelog",
    "MCP-Tools": SPEC + "server/tools",
    "MCP-Auth": SPEC + "basic/authorization",
    "MCP-Security": SPEC + "basic/security_best_practices",
    "MCP-Servers": RAW + "modelcontextprotocol/servers/main/README.md",
    # Prompt injection
    "Willison-PI": "https://simonwillison.net/tags/prompt-injection/",
    "Willison-Trifecta": "https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/",
    "Willison-DP": "https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/",
    "Willison-CaMeL": "https://simonwillison.net/2025/Apr/11/camel/",
    "DesignPatterns": "https://arxiv.org/pdf/2506.08837",
    "CaMeL": "https://arxiv.org/pdf/2503.18813",
    "OWASP-LLM01": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
    "OWASP-Agentic": "https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/",
    "OWASP-AgenticTop10": "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
    # 上面兩頁只是介紹，內容在 PDF
    "OWASP-Agentic-PDF": "https://genai.owasp.org/download/45674/?tmstv=1739819891",
    "OWASP-AgenticTop10-PDF": "https://genai.owasp.org/download/52117/?tmstv=1765059207",
    # 可觀測性
    "OTel-GenAI": OTEL + "README.md",
    "OTel-Spans": OTEL + "gen-ai-spans.md",
    "OTel-Inference": OTEL + "client-inference.md",
    "OTel-TokenMetrics": OTEL + "gen-ai-token-metrics.md",
    "OTel-Agent": OTEL + "gen-ai-agent-spans.md",
    "OTel-Events": OTEL + "gen-ai-events.md",
    "OTel-MCP": OTEL + "mcp.md",
    "OTel-Metrics": OTEL + "gen-ai-metrics.md",
    "Langfuse": RAW + "langfuse/langfuse/main/README.md",
    "Langfuse-OTel": "https://langfuse.com/integrations/native/opentelemetry",
    "Langfuse-Self": "https://langfuse.com/self-hosting",
    "Phoenix": RAW + "Arize-ai/phoenix/main/README.md",
    "Phoenix-Self": "https://arize.com/docs/phoenix/self-hosting",
    "CC-OTel": "https://code.claude.com/docs/en/monitoring-usage",
    # Coding agent 接 CI
    "CCA": RAW + "anthropics/claude-code-action/main/README.md",
    "CCA-Docs": "https://code.claude.com/docs/en/github-actions",
    "Codex-Action": RAW + "openai/codex-action/main/README.md",
    "Codex-GHA": "https://developers.openai.com/codex/github-action",
    "Codex-Review": "https://developers.openai.com/codex/integrations/github",
    "Cursor-Cloud": "https://cursor.com/docs/cloud-agent",
    "Cursor-Bugbot": "https://cursor.com/docs/bugbot",
    "Cursor-Automations": "https://cursor.com/docs/cloud-agent/automations",
    # Spec-driven development
    "SpecKit": RAW + "github/spec-kit/main/README.md",
    "SpecKit-SDD": RAW + "github/spec-kit/main/spec-driven.md",
    "Kiro-Specs": "https://kiro.dev/docs/specs/",
    "Kiro-Feature": "https://kiro.dev/docs/specs/feature-specs/",
    "Fowler-SDD": "https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html",
    "Superpowers": RAW + "obra/superpowers/main/README.md",
    "CompoundEng": RAW + "EveryInc/compound-engineering-plugin/main/README.md",
    # API 層基本元件
    "Claude-StructOut": CLAUDE + "build-with-claude/structured-outputs.md",
    "Claude-ToolUse": CLAUDE + "agents-and-tools/tool-use/overview.md",
    "Claude-ToolCalls": CLAUDE + "agents-and-tools/tool-use/handle-tool-calls.md",
    "Claude-Caching": CLAUDE + "build-with-claude/prompt-caching.md",
    "OpenAI-StructOut": OPENAI + "structured-outputs.md",
    "OpenAI-FnCall": OPENAI + "function-calling.md",
    "OpenAI-Caching": OPENAI + "prompt-caching.md",
    # 生產力實證
    "METR-RCT": "https://arxiv.org/pdf/2507.09089",
    "METR-2025": "https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/",
    "METR-Uplift2026": "https://metr.org/blog/2026-02-24-uplift-update/",
    "METR-Survey2026": "https://metr.org/blog/2026-05-11-ai-usage-survey/",
    "DORA-2025": "https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf",
    # 失敗模式
    "MAST": "https://arxiv.org/pdf/2503.13657",
    # Agent 間協定
    "A2A-Spec": RAW + "a2aproject/A2A/main/docs/specification.md",
    "A2A-Repo": RAW + "a2aproject/A2A/main/README.md",
    "LF-A2A": "https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents",
    "IBM-ACP": "https://research.ibm.com/projects/agent-communication-protocol",
    "ACP-Intro": "https://agentclientprotocol.com/get-started/introduction.md",
    "ACP-Arch": "https://agentclientprotocol.com/get-started/architecture.md",
    # 從零實作與經典綜述
    "Ball-Agent": "https://ampcode.com/notes/how-to-build-an-agent",
    "Weng-Agents": "https://lilianweng.github.io/posts/2023-06-23-agent/",
    "Huyen-Agents": "https://huyenchip.com/2025/01/07/agents.html",
}


def run(sid, url):
    final, raw = fetch.get(url)
    if raw[:5] == b"%PDF-":
        body = fetch.pdf_text(raw)
    elif final.startswith(RAW) or final.endswith(".md"):
        body = raw.decode("utf-8", "replace")
    else:
        body = fetch.html_text(raw, final)
    (CACHE / f"{sid}.txt").write_text(f"# {sid} {final}\n\n{body}", encoding="utf-8")
    return "ok" if final == url else f"ok (redirect {final})"


if __name__ == "__main__":
    fetch.main(SOURCES, run, CACHE)
