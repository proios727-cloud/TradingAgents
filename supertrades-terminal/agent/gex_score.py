"""Post-session scorer — score the enriched GEX forward-log on real premium.

Run flow (the fetch is the RH-MCP step; this module is pure + testable):
  1. During RTH: `gex_live.build_snapshot(...)` -> append enriched rows to
     gex_log.jsonl (each row carries both ATM contracts' option_id + mid + spread).
  2. After the session: for every gated row, pull the two contracts' real
     premium bars via get_option_historicals over the horizon (snapshot ts ->
     +horizon, capped at the 15:45 ET flatten), and drop them in a bars cache
     keyed by option_id.
  3. `python -m agent.gex_score gex_log.jsonl <bars_dir>` -> the honest verdict
     from gex_validate.analyze (baselines, session bootstrap, decision).

Bars cache: <bars_dir>/<option_id>.json = a JSON array of [open,high,low,close]
already sliced to the horizon window (this module replays whatever it's given).
"""

from __future__ import annotations

import json
import os
import sys

from .gex_validate import Decision, EntryCfg, analyze


def to_entry(snap: dict, call_bars: list, put_bars: list) -> dict:
    """Map an enriched snapshot + its two contracts' horizon bars into the
    entry shape gex_validate expects."""
    return {
        "session": snap.get("session"),
        "gate_dir": snap.get("gate_dir"),
        "call": {"mid": snap["call"]["mid"], "spread": snap["call"]["spread_pct"],
                 "bars": call_bars},
        "put": {"mid": snap["put"]["mid"], "spread": snap["put"]["spread_pct"],
                "bars": put_bars},
    }


def score_log(snapshots: list[dict], bars_by_oid: dict,
              cfg: EntryCfg = EntryCfg(), decision: Decision = Decision()) -> dict:
    """Score enriched snapshots against a {option_id: [(o,h,l,c),...]} bars map.
    Snapshots missing bars for either leg are skipped (can't be scored)."""
    entries, skipped = [], 0
    for s in snapshots:
        cb = bars_by_oid.get(s.get("call", {}).get("option_id"))
        pb = bars_by_oid.get(s.get("put", {}).get("option_id"))
        if cb is None or pb is None:
            skipped += 1
            continue
        entries.append(to_entry(s, [tuple(b) for b in cb], [tuple(b) for b in pb]))
    res = analyze(entries, cfg, decision)
    res["skipped_unscorable"] = skipped
    return res


def _load_bars_dir(path: str) -> dict:
    out = {}
    if not os.path.isdir(path):
        return out
    for fn in os.listdir(path):
        if fn.endswith(".json"):
            with open(os.path.join(path, fn), encoding="utf-8") as f:
                out[fn[:-5]] = json.load(f)
    return out


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: python -m agent.gex_score <gex_log.jsonl> <bars_dir>")
        return 2
    snaps = [json.loads(l) for l in open(argv[0], encoding="utf-8") if l.strip()]
    res = score_log(snaps, _load_bars_dir(argv[1]))
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
