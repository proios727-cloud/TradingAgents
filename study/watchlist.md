# Watchlist — Recommended Viewing Order

Order optimized for: fundamentals → extension mechanisms → building your own → applied automation.
Ratings = practical value for a technical/Python operator, 1–5.

---

## 1. CompileFuture — Claude Code Tutorial: Full AI Coding Workflow for Beginners (2026)
- https://www.youtube.com/watch?v=vGx5Y_gSEO0 (blog mirror: compilefuture.com/blog/claude-code-tutorial)
- **Why:** fastest end-to-end orientation — install, auth, the three permission modes (Shift+Tab), live-coding a site, token management.
- **Level:** beginner · **Type:** implementation
- **Revisit:** the "compact prompt" for session handoffs (in blog post); modes segment; MCP-for-docs segment. Skip the statusline script unless you want it.
- ⚠️ Calls MCP "Modular Context Provider" — wrong; it's *Model* Context *Protocol*.
- **Rating:** 3/5 (good on-ramp, thin on depth; skippable if you already run Claude Code)

## 2. Michele Torti — Master Claude Code MCP in 13 minutes (Beginner's Guide)
- https://www.youtube.com/watch?v=3wArVlPvqAk · 13:26
- **Why:** best conceptual model in the set — Skills (instructions) vs Hooks (guardrails) vs MCP (new abilities) — plus real `.mcp.json` config and the token-cost warning nobody else mentions.
- **Level:** beginner→intermediate · **Type:** both
- **Revisit:** 01:16 Skills vs Hooks vs MCP · 02:15 `.mcp.json` config · 06:46 Chrome DevTools bulk-screenshot example · 07:57 Supabase PDF→vector-DB example · 11:15 **The Hidden Cost (context bloat)** ← most valuable 2 min in all six videos
- **Rating:** 5/5

## 3. Grace Leung — Claude Code just Built me an AI Agent Team (Claude Code + Skills + MCP)
- https://www.youtube.com/watch?v=0J2_YGuNrDo · 17:23 · Dec 2025
- **Why:** the multi-agent pattern: agents-as-markdown-files (role/knowledge/tools), routing rules in CLAUDE.md, orchestration. Marketing use case, but the structure transfers to trading pipelines directly.
- **Level:** intermediate · **Type:** implementation (workflow design)
- **Revisit:** 03:36 1st agent (context templates) · 07:15 official skills · 09:23 MCP agent · 11:30 custom skill · 13:45 routing rules · 14:34 orchestration demo
- **Rating:** 4/5

## 4. Shawhin Talebi — How to Build (Custom) AI Agents with MCP
- https://www.youtube.com/watch?v=w-Ml3NivoFo · 17:06 · code: github.com/ShawhinT/yt-mcp-agent
- **Why:** the only source that builds an MCP server from scratch (Python, FastMCP, decorators, stdio) then wires it to an agent. Directly reusable for a TradingAgents MCP server.
- **Level:** intermediate · **Type:** implementation (code)
- **Revisit:** 5:20 server primitives (tools/resources/prompts) · 9:02 init server · 9:55 prompts+tools & docstring emphasis · 12:46 stdio transport · 13:00 agent creation · 14:58 demo. Clone the repo; reading it > rewatching.
- Uses OpenAI Agents SDK as client — pattern is identical for Claude Code (`claude mcp add`).
- **Rating:** 5/5

## 5. Shabbir Noor — Create any n8n Workflow Instantly (Claude MCP Tutorial)
- https://www.youtube.com/watch?v=flgxyWgCrU0 · 15:55 · repo: github.com/czlonkowski/n8n-mcp
- **Why:** case study of a *great* MCP server design: docs coverage + validation tools + explicit tool-ordering instructions. Honest about failures — first workflows broke; validation loop fixed them. Watch for the design lessons even if you don't use n8n.
- **Level:** intermediate · **Type:** implementation (applied)
- **Revisit:** npx install + `claude_desktop_config.json` edit; docs-only vs full-management mode (N8N_API_URL/KEY); project system-instructions for tool ordering; end prompting tips.
- ⚠️ Jul 2025 — n8n-mcp now has a hosted option and Claude Code path; check the repo README for current setup.
- **Rating:** 3/5 (4/5 if you'll actually drive n8n)

## 6. Grace Leung — Turn Claude to Powerful AI Agents, Automate 50% of Your Work
- https://www.youtube.com/watch?v=p0pR_zq-85M · 17:16 · May 2025
- **Why:** the 4-tier MCP sourcing hierarchy (native → official → community → self-built) and 5 agent archetypes (research, BI, personal assistant, UX, project). Everything else is superseded by her Dec 2025 video (#3).
- **Level:** beginner · **Type:** conceptual
- **Revisit:** 01:03 ways to use MCP (the hierarchy) · skim one agent demo (06:45 Business Intelligence) for flavor.
- ⚠️ **Dated:** Claude-Desktop-centric, manual `claude_desktop_config.json` + git-clone era; Connectors and `claude mcp add` have since simplified all of this. Watch at 1.5–2×, or skip and read the hierarchy in `master-guide.md` §2.
- **Rating:** 2/5 today

---

**Minimum path if short on time:** #2 → #4 → #3. Read `master-guide.md` in place of #1, #5, #6.
