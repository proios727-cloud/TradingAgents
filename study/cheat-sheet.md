# Cheat Sheet — Claude Code + MCP

## Core concepts (one line each)
- **Claude Code** — agentic CLI: reads/edits files, runs commands, loops until done.
- **MCP** — standard client↔server protocol giving LLMs tools/resources/prompts.
- **Skill** — on-demand markdown playbook ("do it this way"). Cheap.
- **Hook** — auto-run shell command at lifecycle events (guardrail). Deterministic.
- **Subagent** — separate context window + role + tool allowlist (`.claude/agents/*.md`).
- **CLAUDE.md** — persistent project memory, loaded every session.

## Setup order
1. `npm i -g @anthropic-ai/claude-code` → `claude` → auth
2. `cd project` → `/init` → edit `CLAUDE.md`
3. Add skills (`.claude/skills/` or anthropics/skills repo)
4. Add MCP only when you need external systems: `claude mcp add <name> -- <cmd>`
5. Add hooks last (enforce what already works)

## Must-know files
```
CLAUDE.md                     # project memory + routing rules
.mcp.json                     # project-scoped MCP servers (git-shared)
.claude/settings.json         # permissions, hooks
.claude/skills/<x>/SKILL.md   # custom skills
.claude/agents/<x>.md         # subagents
~/.claude/                    # user-scoped versions of the above
claude_desktop_config.json    # Claude Desktop MCP (Settings→Developer)
```

## Workflow loop
```
Plan mode → review plan → approve → execute → validate (tests/linter/MCP validator)
→ fix → commit small → /compact or fresh session with handoff summary
```

## MCP server in ~15 lines (Python)
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("name")

@mcp.tool()
def my_tool(arg: str) -> str:
    """Detailed docstring — this IS the LLM's API doc."""
    ...

mcp.run(transport="stdio")
```
Register: `claude mcp add name -- uv run server.py` → verify with `/mcp`.

## Prompt pattern
```
Context (or: it's in CLAUDE.md) → concrete goal → constraints →
deliverable format/template → "validate with X before finishing"
```

## Common mistakes
- Loading many MCP servers "just in case" → context bloat, worse tool use. Enable per-task.
- Using MCP where a skill (instructions) suffices.
- Vague docstrings on custom tools → wrong/failed tool calls.
- Skipping validation step → plausible-but-broken output (esp. generated workflows/configs).
- One giant session → degraded answers. Compact/handoff early.
- Overlapping agent roles → conflicts, duplicated work.
- Secrets in prompts/committed config instead of env vars.
- Trusting community MCP servers blindly — they run code on your machine.
