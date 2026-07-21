# Deduplicated Canon — one clearest version per topic

All six sources re-explain the same 5 things. These are the keeper versions; everything else across the videos is a restatement.

---

## 1. What Claude Code is
**Keeper: Grace Leung (Dec 2025) + CompileFuture, merged.**
An agentic CLI where Claude operates on a real workspace: reads/edits files, runs commands, uses git — looping with permission gates. Unlike chat apps, agents built in it share one filesystem/context instead of you copy-pasting between silos; you set direction, it coordinates execution.
*Redundant retellings:* every source's intro segment (~first 90s of each video). Skip all intros.

## 2. What MCP is
**Keeper: Talebi's technical version, with Grace's one-liner as the mnemonic.**
- Mnemonic: "a universal plug / USB-C port for AI" — standard way for any model to reach external tools and data.
- Technical: client–server protocol. Client lives in the AI app; server exposes **tools** (callable functions), **resources** (readable data), **prompts** (instruction templates). Transport is stdio (local subprocess) or HTTP (remote, OAuth). Build a server once, use it from any client (Claude Code, Desktop, ChatGPT, OpenAI Agents SDK).
- Why it matters (Torti/Shabbir): the server ships documentation + validation, so the model stops hallucinating API formats.
*Redundant:* Grace's plug metaphor ×2 videos, Torti's plugin metaphor, CompileFuture's (mislabeled) version, Shabbir's intro — all the same content.

## 3. How to install/configure MCP
**Keeper: merged Torti (Claude Code) + Shabbir (Desktop).**
- Claude Code: `claude mcp add <name> -- <launch-cmd>` (or edit `.mcp.json`); verify with `/mcp`.
- Claude Desktop: Settings → Developer → Edit Config → add `mcpServers` entry to `claude_desktop_config.json` → restart app.
- Universal prerequisites: runtime (Node/uv/Docker) + service API key ready *before* configuring; follow the server README exactly; smoke-test one tool call.
*Outdated variant to discard:* Grace Leung May 2025's git-clone-the-repo workflow — modern servers install via `npx`/`uvx` one-liners or hosted URLs. Her 4-tier sourcing hierarchy (native → official → community → self-built) is the only part worth keeping.

## 4. How to think about agent workflows
**Keeper: Grace Leung (Dec 2025), sharpened.**
- Agent = markdown file: role (non-overlapping) + knowledge/templates + allowed tools.
- One coordinator delegates; specialists produce files into the shared workspace; routing rules live in CLAUDE.md.
- Templates for every deliverable; explicit params, no defaults.
- Add capability in layers: plain context → skills → MCP → custom skills → routing/orchestration.
- Validation loop (from Shabbir/n8n-mcp, generalize it): generate → validate with a tool → fix → validate → ship. Expect first attempts to fail.
*Redundant:* Geeky-Gadgets writeup of the same video; Grace's May 2025 "3-step framework" is the embryonic version of the same idea.

## 5. When to build a custom MCP server
**Keeper: synthesis (Talebi + Torti's cost warning).**
Build custom only when ALL of:
1. No native integration, official server, or maintained community server exists (check the hierarchy first);
2. The task needs *live external action/data* — if it's just "follow these steps," write a skill instead (free vs. per-request token cost);
3. You'll reuse it across tasks/clients — one-off glue is faster as a plain script Claude runs.
Then: FastMCP + decorators + fat docstrings + stdio. Deploy remotely (OAuth/Railway) only when a non-local client needs it.
*Redundant:* Talebi's ChatGPT article and AgentCon talk cover the same server with different clients — read the repo instead.
