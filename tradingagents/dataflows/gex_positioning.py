"""Dealer-positioning (GEX/VEX) report from recorded option-chain snapshots.

Bridges the 456CASH chain-snapshot archive into an analyst-consumable report.
Snapshots are JSON files named ``<SYMBOL>-<YYYY-MM-DD>.json`` (canonical EOD)
or ``<SYMBOL>-<YYYY-MM-DD>T<HHMM>.json`` (intraday), each carrying per-contract
bid/ask, IV, OI and volume as recorded from the broker. The map math lives in
``gex_map_engine`` (vendored from the gex-vex-heatseeker toolkit): per-strike
dealer gamma/vanna, zero-gamma flip via Black-Scholes re-derivation, node
ranking and air-pocket detection.

The snapshot directory resolves, in order:
1. ``chain_snapshot_dir`` in the TradingAgents config
2. the ``TRADINGAGENTS_CHAIN_DIR`` environment variable
3. known local 456CASH checkouts (data worktree first — it gets the freshest
   intraday captures)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tradingagents.dataflows.gex_map_engine import analyze, render

_DEFAULT_DIRS = [
    "/home/user/456CASH-data/backend/options/data/chains",
    "/home/user/456CASH/backend/options/data/chains",
]


def _snapshot_dir() -> Optional[Path]:
    from tradingagents.dataflows.config import get_config

    candidates = []
    configured = get_config().get("chain_snapshot_dir")
    if configured:
        candidates.append(configured)
    env = os.environ.get("TRADINGAGENTS_CHAIN_DIR")
    if env:
        candidates.append(env)
    candidates.extend(_DEFAULT_DIRS)

    for c in candidates:
        p = Path(c)
        if p.is_dir():
            return p
    return None


def _latest_snapshot(symbol: str, directory: Path) -> Optional[Path]:
    """Newest snapshot for the symbol. Filenames sort chronologically, and an
    intraday file (…T1337) sorts after that day's canonical file — which is the
    freshness order we want."""
    files = sorted(directory.glob(f"{symbol.upper()}-*.json"))
    return files[-1] if files else None


def _to_engine_chain(snap: dict) -> dict:
    """Convert the 456CASH snapshot schema to the map engine's input schema."""
    return {
        "symbol": snap.get("symbol"),
        "spot": snap["spot"],
        "asof": snap.get("captured_at") or snap.get("snapshot_date"),
        "contracts": [
            {
                "strike": c["strike"],
                "type": c["option_type"],
                "expiry": c["expiration"],
                "oi": c.get("open_interest", 0),
                "volume": c.get("volume", 0),
                "iv": c.get("iv"),
            }
            for c in snap.get("contracts", [])
            if c.get("iv")
        ],
    }


def _staleness_note(asof: Optional[str]) -> str:
    if not asof:
        return "capture time unknown — treat levels as indicative only."
    try:
        ts = datetime.fromisoformat(asof.replace("Z", "+00:00"))
    except ValueError:
        return f"captured {asof}."
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if age_h < 1:
        return f"captured {asof} ({age_h*60:.0f} min ago — current)."
    if age_h < 8:
        return f"captured {asof} ({age_h:.1f}h ago — same session, levels drift intraday)."
    return (
        f"captured {asof} ({age_h/24:.1f} days ago — STALE: open interest has "
        "rolled since; treat levels as background structure, not live triggers)."
    )


def get_dealer_positioning_report(symbol: str) -> str:
    """Human/LLM-readable dealer-positioning report for ``symbol``, or a plain
    explanation of why one is unavailable. Never raises."""
    directory = _snapshot_dir()
    if directory is None:
        return (
            "Dealer positioning unavailable: no chain-snapshot directory found "
            "(set config['chain_snapshot_dir'] or TRADINGAGENTS_CHAIN_DIR)."
        )

    path = _latest_snapshot(symbol, directory)
    if path is None:
        return (
            f"Dealer positioning unavailable for {symbol}: no recorded chain "
            f"snapshots in {directory}. (Currently recorded for: "
            f"{sorted({p.name.split('-')[0] for p in directory.glob('*.json')}) or 'none'}.)"
        )

    try:
        with open(path) as f:
            snap = json.load(f)
        chain = _to_engine_chain(snap)
        if not chain["contracts"]:
            return f"Dealer positioning unavailable: snapshot {path.name} has no usable contracts."
        m = analyze(chain)
    except Exception as e:  # never break the analyst loop over a bad snapshot
        return f"Dealer positioning unavailable: failed to analyze {path.name} ({e})."

    header = (
        f"DEALER POSITIONING (GEX/VEX) for {symbol} — source snapshot {path.name}, "
        f"{_staleness_note(chain.get('asof'))}\n"
        "Reading guide: positive GEX = dealers damp moves (favors mean reversion "
        "toward large nodes); negative GEX = dealers amplify (favors continuation). "
        "The flip is the regime boundary. Walls are the largest dealer-long strikes "
        "above (call wall) / dealer-short below (put wall). Air pockets are strike "
        "gaps with little hedging support where moves travel fast.\n\n"
    )
    return header + render(m)
