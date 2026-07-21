# Master Guide: Claude Code + MCP + Skills + Agent Workflows

> Synthesized from 6 video sources (see `watchlist.md`) + official docs knowledge.
> Implementation-focused. Definitions appear once — see `repeat-info-removed.md` for the canonical versions.

---

## 1. Claude Code basics

**What it is:** Anthropic's agentic CLI. Reads/edits files, runs shell commands, uses git, and calls external tools — in a loop, with your permission gates. Available as terminal CLI, IDE extension (VS Code/Cursor/JetBrains), web app, and desktop app. Terminal is the most complete surface; learn it there first.

**Install / auth:**
```bash
npm install -g @anthropic-ai/claude-code   # or native installer
claude                                      # auth via Pro/Max subscription or API key
```

**Permission modes** (cycle with `Shift+Tab`):
- **Default** — asks before each edit/command
- **Plan mode** — read-only; produces a plan you approve before any edit
- **Auto-accept ("YOLO")** — applies changes without asking (`--dangerously-skip-permissions` is the extreme version; use only in sandboxes)

**Key files:**
| File | Purpose |
|---|---|
| `CLAUDE.md` | Project memory: context, conventions, rules, agent routing rules. Auto-loaded every session. |
| `.claude/settings.json` | Permissions, hooks, env vars (project scope) |
| `.mcp.json` | Project-scoped MCP servers (checked into git, shared with team) |
| `~/.claude/` | User-scoped settings, skills, agents |
| `.claude/skills/<name>/SKILL.md` | Custom skills |
| `.claude/agents/<name>.md` | Subagent definitions |

**Essential commands:** `/init` (generate CLAUDE.md), `/compact` (compress context), `/clear` (reset), `/mcp` (inspect MCP servers), `/agents`, `Esc` (interrupt).

**Context management (CompileFuture's core tip):** long sessions degrade + burn tokens. Before hitting the limit, have Claude emit a dense handoff summary (goal, decisions, files touched, next steps) and paste it into a fresh session. `/compact` does a built-in version of this.

---

## 2. MCP basics

**Model Context Protocol** — open standard for connecting LLMs to external tools/data. Client–server: the AI app (Claude Code, Claude Desktop, ChatGPT, OpenAI Agents SDK) embeds an MCP *client*; the *server* exposes three primitive types:

- **Tools** — functions the model can call (actions: query DB, take screenshot, place order)
- **Resources** — data the model can read (files, CSV catalogs, docs)
- **Prompts** — reusable instruction templates the server ships with

**Transport:** `stdio` (server runs as a local subprocess — the client spawns it from a command in config) or HTTP/SSE (remote server, like an API; needs auth, usually OAuth).

**Why it beats hand-rolled integrations:** build the toolset once, use it from any MCP client. Server ships its own usage instructions, so the model knows how to call the API correctly instead of hallucinating request formats.

**Server sourcing hierarchy (Grace Leung's ordering — use the first that exists):**
1. Native integrations / Connectors in the Claude apps (Gmail, Calendar, Drive)
2. Official vendor MCP servers (Notion, Supabase, GitHub, Perplexity)
3. Community servers (e.g. `czlonkowski/n8n-mcp`, Chrome DevTools) — check maintenance + trust before use
4. Self-built (Python FastMCP, or no-code via n8n)

Registry: `github.com/modelcontextprotocol/servers`

---

## 3. Skills vs Hooks vs MCP (Torti's framing — memorize this)

| | What it is | Analogy | When to use |
|---|---|---|---|
| **Skill** | Markdown instructions + optional scripts, loaded on demand | "Do this task *this way*" — a playbook | Repeatable procedures, output formats, domain workflows |
| **Hook** | Shell command run automatically at lifecycle events (pre/post tool use, session start/stop) | Guardrail / security guard | Enforce rules deterministically: block file writes, run linters after edits, log actions |
| **MCP** | External tool server | New abilities / extra pair of hands | Anything requiring live data or external systems |

They compose: MCP gives the capability, skills tell Claude how/when to use it, hooks enforce what it must never do. Skills ≈ free (loaded only when triggered); MCP tools cost context on every request (see §7).

---

## 4. MCP setup workflow (Claude Code)

```bash
# preferred: CLI
claude mcp add <name> -- <command to launch server>          # stdio, local scope
claude mcp add --transport http <name> <url>                 # remote
claude mcp add <name> --scope project -- <command>           # writes .mcp.json (shared via git)
claude mcp list / claude mcp get <name>                      # verify
```

Or edit `.mcp.json` directly:
```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp"]
    },
    "n8n-mcp": {
      "command": "npx",
      "args": ["-y", "n8n-mcp"],
      "env": { "N8N_API_URL": "https://your-n8n.com", "N8N_API_KEY": "..." }
    }
  }
}
```

Claude Desktop equivalent: Settings → Developer → Edit Config → `claude_desktop_config.json`, same `mcpServers` shape, then restart the app.

**Checklist for any new server:**
1. Prerequisite runtime installed (Node for `npx` servers, `uv`/Python for Python servers, Docker for containerized)
2. Get the API key/token for the target service first
3. Add config exactly per the server's README (env vars matter)
4. Restart / `/mcp` to verify tools are listed
5. Smoke-test with one simple prompt that forces a tool call

---

## 5. Custom MCP server workflow (Python — Talebi's pattern)

Minimal viable server (~20 lines):

```python
from mcp.server.fastmcp import FastMCP     # official Anthropic Python SDK

mcp = FastMCP("my-server")

@mcp.prompt()
def system_prompt() -> str:
    """Instructions for using this server."""
    return open("prompts/instructions.md").read()

@mcp.resource("data://tickers")
def ticker_list() -> str:
    """Watchlist as a markdown table."""
    return format_csv_as_markdown("resources/tickers.csv")

@mcp.tool()
def fetch_prices(ticker: str, days: int = 30) -> str:
    """Fetch daily OHLCV for a ticker.

    Args:
        ticker: e.g. "SPY"
        days: lookback window
    Returns: markdown table of prices
    """
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Rules that matter:**
- Any Python function (input → output) can be a tool. Decorator = registration.
- **Docstrings are the API docs the LLM reads.** Long, explicit docstrings (description, args, returns) directly improve tool-call accuracy.
- Keep prompts in separate `.md` files — you iterate on agent behavior by editing markdown, not code.
- Return LLM-friendly formats (markdown tables > raw JSON blobs).

**Connect it:**
- Claude Code: `claude mcp add my-server -- uv run server.py`
- Claude Desktop: config entry with `"command": "uv", "args": ["run", "/path/server.py"]`
- OpenAI Agents SDK: `MCPServerStdio(params={"command": "uv", "args": ["run", "server.py"]})` — same server, different client. That portability is the point of MCP.

**Remote deployment** (only if you need access from web apps): host on Railway/Fly, add OAuth (Auth0), expose `/mcp` over HTTP. Skip until a local stdio server is proven.

---

## 6. Multi-agent workflow patterns (Grace Leung's agent-team model)

**Core idea:** one workspace (project folder), one coordinator (the main Claude session), N specialist agents. Agents share the filesystem as common context instead of you copy-pasting between chat silos.

**Each agent = one markdown file** with three sections:
1. **Role & responsibilities** — specific and non-overlapping (biggest failure mode is role overlap)
2. **Knowledge** — workflow details, templates, brand/domain context, which skills to use
3. **Tools** — which MCP servers it may touch

**Build order used in the video:**
1. Agent with context templates only (pure prompt engineering)
2. Agent + official skills (`github.com/anthropics/skills`)
3. Agent + MCP (live external data)
4. Agent + custom skill (your own SKILL.md)
5. Routing rules in `CLAUDE.md`: "requests about X go to agent A, then hand off to B" → orchestration

**Practical guidance:**
- Coordinator delegates; specialists execute; outputs land as files in the workspace.
- Provide templates for every deliverable — agents fill structure far better than they invent it.
- In Claude Code proper, this maps to **subagents** (`.claude/agents/*.md`, `/agents` command): each gets its own context window, tool allowlist, and system prompt.
- Start with 2 agents + 1 handoff. Five-agent teams demo well but debug badly.

---

## 7. Best practices (operator mindset)

- **Context is the scarce resource.** Every MCP server's tool schemas load into every request. Torti measured meaningful token bloat from idle servers. Only enable servers you're using now; remove the rest (`claude mcp remove`). Same reason: prefer skills (lazy-loaded) over MCP when instructions suffice.
- **Plan → approve → execute** for anything non-trivial. Plan mode first; let it touch files only after the plan is right.
- **Validate loops beat one-shot prompts.** The n8n-MCP workflow (search → configure → validate → build → validate again → deploy) generalizes: give Claude a validator (tests, linter, schema check) and make it self-check before "shipping." First attempts often fail — iteration is the design, not a bug.
- **Order tool usage explicitly.** LLMs misorder tool calls; system instructions like "always call X before Y" (n8n-mcp's project instructions) fix this. Put such rules in CLAUDE.md or the skill.
- **CLAUDE.md is your leverage.** Every correction you keep repeating in chat belongs there instead.
- **Templates + explicit params.** Never rely on defaults in generated configs/workflows — have Claude set every parameter explicitly.
- **Credentials:** env vars / `.env`, never in prompts or committed configs. Rotate anything pasted into a chat.
- **Hooks for anything that must ALWAYS happen** (lint after edit, block prod paths). Instructions can be ignored under context pressure; hooks can't.

## Sources
- Grace Leung ×2, CompileFuture, Michele Torti, Shabbir Noor, Shawhin Talebi — details and links in `watchlist.md`.
