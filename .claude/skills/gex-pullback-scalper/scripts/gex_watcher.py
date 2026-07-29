#!/usr/bin/env python3
"""
GEX WATCHER — SPY/QQQ heatmap monitor for the gex-pullback-scalper system.

Polls Polygon.io options snapshots, computes net GEX by strike (gamma flip,
call wall, put wall, vacuum zones), runs the pullback gate, and fires a
Discord webhook the moment a play arms. You then open Claude (chat or
Cowork) and say "midday check-in" / "run the GEX team" with the alert pasted.

This script ALERTS ONLY. It never places orders.

Setup:
  pip install requests
  export POLYGON_API_KEY=...        (needs an options-tier key)
  export DISCORD_WEBHOOK_URL=...
  python gex_watcher.py             (run 9:30–16:00 ET; cron/Task Scheduler)

Tuning lives in CONFIG below — thresholds mirror the SKILL.md defaults.
"""

import os, sys, time, json, datetime, urllib.request

CONFIG = {
    "tickers": ["SPY", "QQQ"],
    "poll_seconds": 60,
    "pullback_pct": -0.75,          # intraday % move to qualify (criterion 1)
    "wall_proximity_pct": 0.15,     # % distance to count as "tagging" a wall
    "vacuum_min_gap_pct": 0.30,     # min strike gap (% of spot) to call a vacuum
    "strike_window_pct": 3.0,       # only consider strikes within ±3% of spot
    "min_dte": 0, "max_dte": 7,     # expirations folded into the GEX map
    "alert_cooldown_min": 20,       # don't re-fire same alert type within N min
}

POLY = "https://api.polygon.io"
KEY = os.environ.get("POLYGON_API_KEY", "")
HOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def get(url):
    sep = "&" if "?" in url else "?"
    with urllib.request.urlopen(f"{url}{sep}apiKey={KEY}", timeout=20) as r:
        return json.loads(r.read())


def fetch_chain(ticker):
    """All option contracts within the strike window and DTE range, w/ greeks+OI."""
    today = datetime.date.today()
    out, url = [], (f"{POLY}/v3/snapshot/options/{ticker}?limit=250"
                    f"&expiration_date.gte={today}"
                    f"&expiration_date.lte={today + datetime.timedelta(days=CONFIG['max_dte'])}")
    while url:
        data = get(url)
        out += data.get("results", [])
        url = data.get("next_url")
    return out


def spot_and_change(ticker):
    s = get(f"{POLY}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
    t = s["ticker"]
    px = t["lastTrade"]["p"] if t.get("lastTrade") else t["day"]["c"]
    return px, t.get("todaysChangePerc", 0.0)


def build_gex_map(chain, spot):
    """Net GEX per strike. Convention: dealers long calls (+), long puts (-).
    GEX = gamma * OI * 100 * spot^2 * 0.01  (dollar gamma per 1% move)."""
    gex = {}
    lo, hi = spot * (1 - CONFIG["strike_window_pct"]/100), spot * (1 + CONFIG["strike_window_pct"]/100)
    for c in chain:
        d, g = c.get("details", {}), c.get("greeks", {}) or {}
        k, oi, gamma = d.get("strike_price"), c.get("open_interest", 0), g.get("gamma")
        if not k or not oi or gamma is None or not (lo <= k <= hi):
            continue
        sign = 1 if d.get("contract_type") == "call" else -1
        gex[k] = gex.get(k, 0) + sign * gamma * oi * 100 * spot * spot * 0.01
    return dict(sorted(gex.items()))


def levels(gex, spot):
    if not gex:
        return None
    strikes = list(gex)
    cum, flip = 0, None
    for k in strikes:                       # zero-cross of cumulative GEX
        prev = cum; cum += gex[k]
        if prev < 0 <= cum or prev > 0 >= cum:
            flip = k
    call_wall = max((k for k in strikes if k >= spot), key=lambda k: gex[k], default=None)
    put_wall = min(((k, gex[k]) for k in strikes if k <= spot), key=lambda kv: kv[1], default=(None,))[0]
    net = sum(gex.values())
    # vacuum: biggest gap between "significant" strikes (top-quartile |GEX|)
    sig = sorted(k for k in strikes if abs(gex[k]) >= sorted(map(abs, gex.values()))[3*len(gex)//4])
    vacuums = [(a, b) for a, b in zip(sig, sig[1:]) if (b - a) / spot * 100 >= CONFIG["vacuum_min_gap_pct"]]
    return {"flip": flip, "call_wall": call_wall, "put_wall": put_wall,
            "net_gex": net, "vacuums": vacuums}


def evaluate(ticker, spot, chg, lv):
    """Pullback gate + play triggers. Returns list of alert strings."""
    alerts, crit = [], []
    near = lambda k: k and abs(spot - k) / spot * 100 <= CONFIG["wall_proximity_pct"]
    below_flip = lv["flip"] and spot < lv["flip"]
    crit += ["down>=0.75%"] if chg <= CONFIG["pullback_pct"] else []
    crit += ["below_flip"] if below_flip else []
    crit += ["wall/vacuum_contact"] if (near(lv["put_wall"]) or any(a <= spot <= b for a, b in lv["vacuums"])) else []
    # (VIX criterion checked manually in the chat session — most Polygon plans lack indices)
    if len(crit) < 2:
        return []
    base = (f"**{ticker}** {spot:.2f} ({chg:+.2f}%) | gate PASS [{', '.join(crit)}]\n"
            f"flip {lv['flip']} | call wall {lv['call_wall']} | put wall {lv['put_wall']} | "
            f"net GEX {'+' if lv['net_gex']>=0 else ''}{lv['net_gex']/1e9:.2f}B")
    if near(lv["put_wall"]):
        alerts.append(("P1", base + "\n🎯 **PLAY 1 ARMING — put-wall tag.** Watch for the hold/reclaim, then run the GEX team."))
    if lv["put_wall"] and spot < lv["put_wall"]:
        alerts.append(("P2", base + "\n⚡ **PLAY 2 ARMING — wall breached / vacuum.** Failed retest = entry. Run the GEX team."))
    if below_flip and lv["flip"] and (lv["flip"] - spot) / spot * 100 <= CONFIG["wall_proximity_pct"]:
        alerts.append(("P3", base + "\n🔄 **PLAY 3 WATCH — approaching flip from below.** Reclaim+hold = entry. Run the GEX team."))
    return alerts


def discord(msg):
    req = urllib.request.Request(HOOK, json.dumps({"content": msg}).encode(),
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def main():
    if not KEY or not HOOK:
        sys.exit("Set POLYGON_API_KEY and DISCORD_WEBHOOK_URL env vars.")
    last = {}   # (ticker, play) -> last alert time
    print("GEX watcher running…")
    while True:
        for tk in CONFIG["tickers"]:
            try:
                spot, chg = spot_and_change(tk)
                lv = levels(build_gex_map(fetch_chain(tk), spot), spot)
                if not lv:
                    continue
                for play, msg in evaluate(tk, spot, chg, lv):
                    key, now = (tk, play), time.time()
                    if now - last.get(key, 0) > CONFIG["alert_cooldown_min"] * 60:
                        discord(msg); last[key] = now
                        print(f"[{datetime.datetime.now():%H:%M}] alert {tk} {play}")
            except Exception as e:
                print(f"[{tk}] error: {e}")
        time.sleep(CONFIG["poll_seconds"])


if __name__ == "__main__":
    main()
