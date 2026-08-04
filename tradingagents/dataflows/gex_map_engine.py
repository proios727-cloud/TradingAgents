#!/usr/bin/env python3
"""
gex_map.py — Build a GEX/VEX dealer-positioning map from an option-chain snapshot.

WHY THIS EXISTS
---------------
Every run of the heatseeker skill needs the same math: aggregate dealer gamma and
vanna by strike, find the zero-gamma (flip) level, rank nodes, and locate air
pockets. Doing that by hand in-context is slow and error-prone, and re-deriving
gamma at hypothetical spot levels is genuinely fiddly. This script does it once,
correctly, so the model can spend its attention on reading the map instead of
building it.

INPUT
-----
A JSON file collected from the Robinhood MCP (get_option_quotes), shape:

{
  "symbol": "SPY",
  "spot": 738.41,
  "asof": "2026-07-24T19:38:00Z",
  "risk_free_rate": 0.04,          # optional, default 0.04
  "contracts": [
    {"strike": 740, "type": "call", "expiry": "2026-07-31",
     "oi": 7876, "volume": 26187, "iv": 0.186488,
     "gamma": 0.024783, "vega": 0.344232, "delta": 0.485281},
    ...
  ]
}

Only strike/type/expiry/oi/iv are strictly required. Broker-supplied gamma and
vega are used for the spot-level snapshot; gamma is re-derived from Black-Scholes
when scanning hypothetical spot levels (you cannot reuse a fixed gamma there —
gamma itself moves with spot, which is the whole reason a flip level exists).

USAGE
-----
    python3 gex_map.py chain.json                 # human-readable map
    python3 gex_map.py chain.json --json          # machine-readable
    python3 gex_map.py chain.json --flow-adjust   # also model same-day volume

DEALER SIGN CONVENTION
----------------------
Standard naive convention (SqueezeMetrics-style): dealers are assumed long call
gamma and short put gamma, i.e. calls contribute +GEX and puts contribute -GEX.
This is an assumption, not a measurement — real dealer books are not observable.
It is the same assumption the mainstream GEX vendors publish, so the levels it
produces line up reasonably with the ones traders are collectively watching,
which is most of what makes those levels self-fulfilling in the first place.
"""

import argparse
import json
import math
import sys
from collections import defaultdict

SQRT_2PI = math.sqrt(2.0 * math.pi)
# Floor on time-to-expiry (~15 minutes in years). Without this, 0DTE gamma
# diverges to infinity in the final minutes and swamps every other strike.
MIN_T = 1.0 / (365.0 * 24.0 * 4.0)


def norm_pdf(x):
    return math.exp(-0.5 * x * x) / SQRT_2PI


def d1_d2(S, K, T, sigma, r=0.04):
    """Black-Scholes d1/d2. Returns (None, None) on degenerate input."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return None, None
    v = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / v
    return d1, d1 - v


def bs_gamma(S, K, T, sigma, r=0.04):
    d1, _ = d1_d2(S, K, T, sigma, r)
    if d1 is None:
        return 0.0
    return norm_pdf(d1) / (S * sigma * math.sqrt(T))


def bs_vanna(S, K, T, sigma, r=0.04):
    """dDelta/dVol = -phi(d1) * d2 / sigma."""
    d1, d2 = d1_d2(S, K, T, sigma, r)
    if d1 is None:
        return 0.0
    return -norm_pdf(d1) * d2 / sigma


def bs_charm(S, K, T, sigma, r=0.04):
    """dDelta/dTime (per year). Drives end-of-day and OPEX pinning drift."""
    d1, d2 = d1_d2(S, K, T, sigma, r)
    if d1 is None:
        return 0.0
    v = sigma * math.sqrt(T)
    return -norm_pdf(d1) * (2.0 * r * T - d2 * v) / (2.0 * T * v)


def years_to_expiry(expiry, asof):
    """Rough calendar-day year fraction, floored at MIN_T."""
    from datetime import datetime, timezone

    def parse(s):
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.fromisoformat(s + "T00:00:00+00:00")
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    exp = parse(expiry)
    # Options settle ~16:00 ET == 20:00 UTC
    exp = exp.replace(hour=20, minute=0, second=0, microsecond=0)
    now = parse(asof)
    return max((exp - now).total_seconds() / (365.0 * 24 * 3600.0), MIN_T)


def effective_oi(c, flow_adjust):
    """
    Open interest is published T+1, so intraday it reflects yesterday's close.
    Same-day volume is live but direction-blind: we cannot tell opening from
    closing trades, nor customer buys from sells.

    Rather than pretend, --flow-adjust adds a conservative 30% of same-day
    volume as provisional new OI. Compare the adjusted map against the plain
    one: if the flip level barely moves, today's flow is not reshaping the
    board and the stale map is trustworthy. If it moves a lot, the map is
    contested and confidence should drop. The disagreement is the signal.
    """
    oi = float(c.get("oi") or 0)
    if not flow_adjust:
        return oi
    return oi + 0.30 * float(c.get("volume") or 0)


def build(chain, flow_adjust=False):
    spot = float(chain["spot"])
    asof = chain["asof"]
    r = float(chain.get("risk_free_rate", 0.04))
    contracts = []
    for c in chain["contracts"]:
        iv = float(c.get("iv") or 0)
        if iv <= 0:
            continue
        contracts.append({
            "K": float(c["strike"]),
            "type": c["type"].lower(),
            "T": years_to_expiry(c["expiry"], asof),
            "iv": iv,
            "oi": effective_oi(c, flow_adjust),
            "gamma": c.get("gamma"),
            "vega": c.get("vega"),
        })
    return spot, r, contracts


def net_gex_at(spot_level, contracts, r):
    """Signed dollar gamma per 1% move, re-deriving gamma at the given spot."""
    total = 0.0
    for c in contracts:
        g = bs_gamma(spot_level, c["K"], c["T"], c["iv"], r)
        sign = 1.0 if c["type"] == "call" else -1.0
        total += sign * g * c["oi"] * 100.0 * spot_level * spot_level * 0.01
    return total


def per_strike(spot, contracts, r):
    """Aggregate GEX / VEX / charm at the live spot, bucketed by strike."""
    gex, vex, charm = defaultdict(float), defaultdict(float), defaultdict(float)
    for c in contracts:
        sign = 1.0 if c["type"] == "call" else -1.0
        K, T, iv, oi = c["K"], c["T"], c["iv"], c["oi"]
        g = c["gamma"] if c["gamma"] is not None else bs_gamma(spot, K, T, iv, r)
        gex[K] += sign * float(g) * oi * 100.0 * spot * spot * 0.01
        vex[K] += sign * bs_vanna(spot, K, T, iv, r) * oi * 100.0 * spot * 0.01
        charm[K] += sign * bs_charm(spot, K, T, iv, r) * oi * 100.0 / 365.0
    return gex, vex, charm


def find_flip(spot, contracts, r, span=0.06, steps=241):
    """
    Scan spot levels around the current price and return every zero crossing of
    net GEX. Multiple crossings are normal and worth surfacing — the nearest one
    is the active battleground, but a second crossing above or below marks where
    the regime would flip again if price gets there.
    """
    lo, hi = spot * (1 - span), spot * (1 + span)
    step = (hi - lo) / (steps - 1)
    levels, prev_x, prev_y = [], None, None
    for i in range(steps):
        x = lo + i * step
        y = net_gex_at(x, contracts, r)
        if prev_y is not None and prev_y != y and (prev_y < 0) != (y < 0):
            levels.append(prev_x + (x - prev_x) * (-prev_y) / (y - prev_y))
        prev_x, prev_y = x, y
    return levels


def find_air_pockets(gex, spot, threshold_ratio=0.15, gap_multiple=1.8):
    """
    Air pockets: gaps between significant nodes that are materially wider than
    this board's own strike spacing. Price travels fast through them because
    there is little dealer hedging to absorb the move — they are where the
    outsized gains live, and also where stops get skipped.

    The gap must be measured against the board's typical spacing, not an
    absolute percentage. SPY lists $1 strikes and NVDA lists $2.50s; a fixed
    "0.35% wide" rule would flag every routine strike interval on one board and
    nothing at all on the other. What actually matters is a hole where you would
    normally expect a node and there isn't one.
    """
    if not gex:
        return []
    peak = max(abs(v) for v in gex.values()) or 1.0
    sig = sorted(k for k, v in gex.items() if abs(v) >= threshold_ratio * peak)
    if len(sig) < 3:
        return []
    gaps = [b - a for a, b in zip(sig, sig[1:])]
    typical = sorted(gaps)[len(gaps) // 2]  # median spacing of significant nodes
    if typical <= 0:
        return []
    pockets = []
    for a, b in zip(sig, sig[1:]):
        if (b - a) >= gap_multiple * typical:
            pockets.append({
                "low": a, "high": b,
                "width_pct": round((b - a) / spot * 100.0, 2),
                "x_normal": round((b - a) / typical, 1),
            })
    return pockets


def analyze(chain, flow_adjust=False):
    spot, r, contracts = build(chain, flow_adjust)
    if not contracts:
        raise SystemExit("no usable contracts (all missing IV?)")

    gex, vex, charm = per_strike(spot, contracts, r)
    net = sum(gex.values())
    flips = find_flip(spot, contracts, r)
    nearest_flip = min(flips, key=lambda x: abs(x - spot)) if flips else None

    ranked = sorted(gex.items(), key=lambda kv: abs(kv[1]), reverse=True)
    king = ranked[0][0] if ranked else None
    calls_above = [(k, v) for k, v in gex.items() if k > spot and v > 0]
    puts_below = [(k, v) for k, v in gex.items() if k < spot and v < 0]
    call_wall = max(calls_above, key=lambda kv: kv[1])[0] if calls_above else None
    put_wall = min(puts_below, key=lambda kv: kv[1])[0] if puts_below else None

    net_vex = sum(vex.values())
    # Alignment is the Heatseeker-style read: gamma says how hard dealers damp
    # or amplify moves, vanna says which way a vol change pushes their hedge.
    # Same sign = they reinforce (clean trend or hard pin). Opposite = they
    # fight, which is what chop and whipsaw actually are underneath.
    aligned = (net > 0) == (net_vex > 0)

    return {
        "symbol": chain.get("symbol"),
        "spot": spot,
        "asof": chain.get("asof"),
        "flow_adjusted": flow_adjust,
        "net_gex": net,
        "net_vex": net_vex,
        "regime": "positive" if net > 0 else "negative",
        "vanna_alignment": "aligned" if aligned else "divergent",
        "flip_levels": [round(f, 2) for f in flips],
        "nearest_flip": round(nearest_flip, 2) if nearest_flip else None,
        "flip_distance_pct": round((nearest_flip - spot) / spot * 100, 2) if nearest_flip else None,
        "king_node": king,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "air_pockets": find_air_pockets(gex, spot),
        # Drop negligible strikes: a node carrying <2% of peak gamma is noise
        # and only crowds out the levels that actually matter.
        "top_nodes": [
            {"strike": k, "gex": round(v / 1e6, 2), "vex": round(vex.get(k, 0) / 1e6, 2)}
            for k, v in ranked[:12]
            if ranked and abs(v) >= 0.02 * abs(ranked[0][1])
        ],
        "charm_top": [
            {"strike": k, "charm": round(v / 1e6, 3)}
            for k, v in sorted(charm.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
        ],
    }


def render(m):
    L = []
    L.append(f"== GEX/VEX MAP — {m['symbol']} @ {m['spot']} — {m['asof']} ==")
    if m["flow_adjusted"]:
        L.append("(flow-adjusted: OI + 30% of same-day volume)")
    L.append(f"Regime: {m['regime'].upper()} GEX  |  Net GEX: {m['net_gex']/1e6:,.1f}M/1%"
             f"  |  Net VEX: {m['net_vex']/1e6:,.1f}M/1vol")
    L.append(f"Vanna alignment: {m['vanna_alignment'].upper()}")
    if m["nearest_flip"]:
        L.append(f"Gamma flip: {m['nearest_flip']} ({m['flip_distance_pct']:+.2f}% from spot)")
    else:
        L.append("Gamma flip: none within +/-6% of spot")
    if len(m["flip_levels"]) > 1:
        L.append(f"  other crossings: {m['flip_levels']}")
    L.append(f"King node: {m['king_node']}  |  Call wall: {m['call_wall']}  |  Put wall: {m['put_wall']}")
    if m["air_pockets"]:
        L.append("Air pockets: " + ", ".join(
            f"{p['low']}-{p['high']} ({p['width_pct']}% wide, {p['x_normal']}x normal spacing)"
            for p in m["air_pockets"]))
    else:
        L.append("Air pockets: none (dense board)")
    L.append("")
    L.append("Top nodes (GEX $M per 1% | VEX $M per 1 vol):")
    for n in m["top_nodes"]:
        L.append(f"  {n['strike']:>9}   GEX {n['gex']:>9,.2f}   VEX {n['vex']:>9,.2f}")
    L.append("")
    L.append("Highest charm (pin pull into close/OPEX):")
    for c in m["charm_top"]:
        L.append(f"  {c['strike']:>9}   charm {c['charm']:>9,.3f}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chain")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--flow-adjust", action="store_true")
    ap.add_argument("--compare-flow", action="store_true",
                    help="Print plain vs flow-adjusted flip levels and a confidence read.")
    a = ap.parse_args()

    chain = json.load(open(a.chain))

    if a.compare_flow:
        plain, flow = analyze(chain, False), analyze(chain, True)
        pf, ff = plain["nearest_flip"], flow["nearest_flip"]
        print(render(plain))
        print("\n-- flow cross-check --")
        print(f"flip (OI only):       {pf}")
        print(f"flip (flow-adjusted): {ff}")
        if pf and ff:
            drift = abs(ff - pf) / plain["spot"] * 100
            verdict = ("STABLE — today's flow is not reshaping the board; map is trustworthy"
                       if drift < 0.15 else
                       "CONTESTED — today's flow is rebuilding the map; downgrade confidence")
            print(f"drift: {drift:.2f}%  ->  {verdict}")
        return

    m = analyze(chain, a.flow_adjust)
    print(json.dumps(m, indent=2) if a.json else render(m))


if __name__ == "__main__":
    main()
