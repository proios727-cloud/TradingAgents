"""Obsidian-journal writer (v4 Layer 3, foundation).

The loop calls these to keep an Obsidian vault (supertrades/journal/) filling
itself: a bullet appended to the current day note each cycle/fill, and a trade
note upserted on each fill. Formatting is pure (unit-tested); the thin I/O
wrappers append/create files in the vault.

Design: the vault is the reflection surface — the EOD-review section of each day
note is what feeds financial-evolution/reflections.json. Entries are tagged
signal_source=pinescript by default (auto_entries_used = 0; user-signal driven).
"""
from __future__ import annotations

import os
import re

# journal/ sits next to engine/ under supertrades/
VAULT_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "journal")
CYCLE_HEADING = "## Cycle log"


def slug(contract: str) -> str:
    """'DIS 8/21 $105C' -> 'DIS-8-21-105C' (safe filename, stable per contract)."""
    s = contract.replace("$", "").strip()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s)
    return s.strip("-")


def cycle_line(ts_et: str, event: str, detail: str) -> str:
    """One markdown bullet for the day note's Cycle log."""
    return f"- {ts_et} ET — **{event}**: {detail}"


def append_under(md: str, heading: str, line: str) -> str:
    """Insert `line` as the last bullet of the section started by `heading`.

    Pure: returns the new document text. If the heading is absent the section is
    appended at the end so nothing is ever silently dropped.
    """
    lines = md.splitlines()
    try:
        h = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        tail = "" if md.endswith("\n") else "\n"
        return f"{md}{tail}\n{heading}\n{line}\n"
    # find end of this section (next heading of same-or-higher level, or EOF)
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for i in range(h + 1, len(lines)):
        s = lines[i].lstrip("#")
        if lines[i].startswith("#") and (len(lines[i]) - len(s)) <= level:
            end = i
            break
    block = lines[h + 1:end]
    while block and block[-1].strip() == "":
        block.pop()
    # drop a lone placeholder bullet like "- (none yet)" / "- "
    if len(block) == 1 and re.fullmatch(r"-\s*(\(none[^)]*\))?", block[0].strip()):
        block = []
    new = lines[:h + 1] + block + [line, ""] + lines[end:]
    return "\n".join(new).rstrip("\n") + "\n"


def trade_frontmatter(fields: dict) -> str:
    """Build a trade note (frontmatter + skeleton) from a fill's fields."""
    keys = ["type", "symbol", "contract", "account", "side", "option_type",
            "class", "signal_source", "entry_price", "entry_time", "qty",
            "stop", "target", "ratchet_arm", "exit_price", "exit_time",
            "pnl", "outcome"]
    f = {"type": "trade", "account": "902341866", "side": "long",
         "signal_source": "pinescript", "qty": 1, **fields}
    body = ["---"]
    for k in keys:
        body.append(f"{k}: {f.get(k, '')}")
    body.append("tags: [supertrades, trade]")
    body.append("---")
    body.append("")
    body.append(f"# {f.get('contract', '')}")
    body.append("")
    body.append("## Thesis / signal")
    body.append(f"- Source: {f.get('signal_source', 'pinescript')}")
    body.append("")
    body.append("## Result & lesson")
    body.append("- ")
    return "\n".join(body) + "\n"


# --- thin I/O wrappers (not unit-tested; format helpers above are) -----------

def _day_path(date_iso: str, root: str = VAULT_ROOT) -> str:
    return os.path.join(root, "Daily", f"{date_iso}.md")


def log_cycle(date_iso: str, ts_et: str, event: str, detail: str,
              root: str = VAULT_ROOT) -> None:
    """Append a cycle/fill bullet to the day note (created if missing)."""
    path = _day_path(date_iso, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    md = open(path).read() if os.path.exists(path) else (
        f"---\ntype: daily\ndate: {date_iso}\ntags: [supertrades, daily]\n---\n\n"
        f"# {date_iso} — SuperTrades\n\n{CYCLE_HEADING}\n")
    open(path, "w").write(append_under(md, CYCLE_HEADING, cycle_line(ts_et, event, detail)))


def upsert_trade(fields: dict, root: str = VAULT_ROOT) -> str:
    """Create Trades/<slug>.md on first fill; return the path. Never overwrites."""
    path = os.path.join(root, "Trades", f"{slug(fields.get('contract', 'trade'))}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        open(path, "w").write(trade_frontmatter(fields))
    return path
