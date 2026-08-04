# SuperTrades journal — Obsidian vault

This folder **is** an Obsidian vault (a vault is just a folder of markdown + a `.obsidian/` config). Nothing here needs a server or the desktop app to be present in this repo — you open it with Obsidian on your own machine.

## Open it
1. Install Obsidian on your machine (one-time): https://obsidian.md/download
   - macOS: `brew install --cask obsidian`
   - Windows: `winget install Obsidian.Obsidian`
   - Linux: download the AppImage/`.deb`/Flatpak from the site.
2. Obsidian → **Open folder as vault** → select this `supertrades/journal/` folder (clone/sync the repo first, or use Obsidian Sync / Git plugin).
3. Enable the community **Dataview** plugin to render the Dashboard tables.

## Layout
- `Daily/YYYY-MM-DD.md` — one note per trading day (premarket read, rails, cycle log, EOD review). Created from `Templates/Daily-Note.md`.
- `Trades/<contract>.md` — one note per position, stamped on fill. From `Templates/Trade.md`.
- `Dashboard.md` — map-of-content + Dataview queries.
- `.obsidian/` — vault config (daily-notes → `Daily/`, templates → `Templates/`).

## How the loop writes to it
`supertrades/engine/journal.py` appends structured lines to the current day note and upserts a trade note on each fill — so the vault fills itself while the loop runs. The **EOD review** section is the human/agent reflection that feeds `financial-evolution/reflections.json`.

Frontmatter tags (`#supertrades/daily`, `#supertrades/trade`) drive the Dataview views. `signal_source` defaults to `pinescript` because entries are user-signal driven (auto_entries_used = 0).
