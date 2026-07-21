# Slide Outline — Claude Code + MCP Fast Review (13 slides)

**1. The stack in one picture**
- Claude Code (agent loop) → CLAUDE.md (memory) → Skills (playbooks) → Hooks (guardrails) → MCP (external reach)
- You = director; workspace files = shared context

**2. Claude Code surfaces + modes**
- Terminal (full power) / IDE / web / desktop
- Shift+Tab: default ↔ plan ↔ auto-accept
- Plan mode for anything non-trivial

**3. The file map**
- CLAUDE.md · .mcp.json · .claude/settings.json · .claude/skills/ · .claude/agents/ · ~/.claude/

**4. MCP in 4 bullets**
- Client (in app) ↔ server (has the tools)
- Server exposes: tools / resources / prompts
- Transport: stdio (local) or HTTP (remote+OAuth)
- Build once → works in any MCP client

**5. Skills vs Hooks vs MCP**
- Skill = instructions (on-demand, ~free)
- Hook = deterministic guardrail (always runs)
- MCP = new abilities (costs context every request)
- Compose them; don't substitute one for another

**6. Sourcing hierarchy — never build first**
- Native/Connectors → official server → community → self-built
- Registry: modelcontextprotocol/servers

**7. MCP setup checklist**
- Runtime + API key ready → `claude mcp add` / .mcp.json → restart → `/mcp` verify → 1 smoke-test call

**8. Custom server = 4 decorators**
- `FastMCP("name")` · `@mcp.tool` · `@mcp.resource` · `@mcp.prompt` · `mcp.run(transport="stdio")`
- Docstring = the LLM's API doc → write it fat

**9. Agent = a markdown file**
- Role (non-overlapping) + knowledge/templates + tool allowlist
- Coordinator routes via CLAUDE.md rules; outputs = files

**10. The universal loop**
- Plan → approve → execute → **validate with a tool** → fix → commit small → compact/handoff
- First attempt failing is expected; the loop is the product

**11. Token economics**
- Every enabled MCP server bloats every request
- Enable per-task; prefer skills for pure instructions
- Long session → handoff summary → fresh session

**12. Failure modes**
- Overlapping roles · vague docstrings · no validator · secrets in prompts · trusting random community servers · MCP-for-everything

**13. Trading application (this repo)**
- TradingAgents functions → @mcp.tool wrappers → market-data MCP
- Analyst/risk/execution agents as .claude/agents with routing
- Hooks: block live-order paths; validate before any execution
