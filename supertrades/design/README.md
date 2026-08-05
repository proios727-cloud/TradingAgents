# SuperTrades Design System

The console's visual language as a component kit — dual-theme tokens (light/dark),
terminal-monospace identity, and semantic state colors (good/warn/crit) kept strictly
separate from the teal accent.

## Layout
- `foundations/` — color tokens, typography
- `components/` — KPI cards, status chips, watchlist table, GEX level strip, rules panel + cycle pipeline
- `design-system.html` — single-page showcase of everything (published as an artifact)

Every preview is self-contained (tokens inlined) and carries a first-line
`<!-- @dsCard group="…" -->` marker, so the Claude Design pane can index it directly.

## Handoff to Claude Design (claude.ai/design)
This remote session can't run the interactive design login, so sync from either side:
1. **From Claude Design**: open/create a design-system project and use "Send to Claude Code Web"
   to seed it into this workspace — then ask the session to push `supertrades/design/**` into it, or
2. **From an interactive Claude Code session** (desktop/CLI): run `/design-login`, then ask to
   sync `supertrades/design/` — the DesignSync flow is: list_projects → finalize_plan
   (writes: `foundations/**`, `components/**`) → write_files.

Consumers: `pages/supertrades-console.html` and `pages/supertrades-indexes.html` already
use these exact tokens; new UI should import/copy the token block verbatim.
