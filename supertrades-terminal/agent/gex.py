"""Dealer gamma-exposure (GEX) engine — the real edge input, from real chain data.

Computes net GEX and the structural levels the SuperTrades factor model already
speaks in — gamma flip, call wall, put wall, king node, and the +/-gamma regime
— from a live options chain (per-strike gamma + open interest, both supplied by
the Robinhood ``get_option_quotes`` tool). No paid feed required.

Convention (documented so it can be argued with): net GEX per strike =
    (call_gamma * call_OI  -  put_gamma * put_OI) * multiplier * spot^2 * 0.01
i.e. dealers are assumed net LONG call gamma and SHORT put gamma (the common
retail/SqueezeMetrics convention). Positive aggregate GEX => dealers long gamma
=> they sell rallies / buy dips => vol suppressed, mean-reverting. Negative =>
dealers short gamma => they chase => vol expansion, trending. The gamma flip is
the spot level where cumulative GEX crosses zero.

True options *flow* (aggressive sweeps) needs a trade-tape feed RH does not
expose; ``unusual_activity`` here is an honest volume/OI proxy, not sweep flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MULTIPLIER = 100
ONE_PCT = 0.01


@dataclass(frozen=True)
class StrikeGex:
    strike: float
    call_gamma: float
    call_oi: int
    put_gamma: float
    put_oi: int
    call_vol: int = 0
    put_vol: int = 0

    def net_gex(self, spot: float) -> float:
        raw = self.call_gamma * self.call_oi - self.put_gamma * self.put_oi
        return raw * MULTIPLIER * spot * spot * ONE_PCT


@dataclass
class GexProfile:
    spot: float
    net_gex: float                       # $ / 1% move
    flip: float                          # gamma flip (spot level)
    call_wall: float                     # strongest positive-GEX strike
    put_wall: float                      # strongest negative-GEX strike
    king_node: float                     # max |GEX| strike — dominant magnet
    regime: str                          # 'positive' | 'negative'
    per_strike: list[tuple] = field(default_factory=list)  # (strike, gex)
    unusual: list[tuple] = field(default_factory=list)     # (strike, side, vol/oi)

    @property
    def negative_gamma(self) -> bool:
        return self.regime == "negative"


def _flip(rows: list[StrikeGex], spot: float) -> float:
    """Spot level where cumulative GEX (low->high strike) crosses zero."""
    ordered = sorted(rows, key=lambda r: r.strike)
    cum = 0.0
    prev_strike, prev_cum = None, 0.0
    for r in ordered:
        cum += r.net_gex(spot)
        if prev_strike is not None and (prev_cum <= 0 <= cum or prev_cum >= 0 >= cum) and cum != prev_cum:
            # linear-interpolate the zero crossing between the two strikes
            frac = -prev_cum / (cum - prev_cum)
            return round(prev_strike + frac * (r.strike - prev_strike), 2)
        prev_strike, prev_cum = r.strike, cum
    # no crossing in range — fall back to the strike nearest spot
    return min(rows, key=lambda r: abs(r.strike - spot)).strike


def compute_gex(rows: list[StrikeGex], spot: float,
                unusual_ratio: float = 2.0) -> GexProfile:
    """Build the GEX profile from per-strike chain rows and the current spot."""
    if not rows:
        raise ValueError("empty chain")
    per = [(r.strike, r.net_gex(spot)) for r in rows]
    net = sum(g for _, g in per)
    flip = _flip(rows, spot)
    call_wall = max(per, key=lambda x: x[1])[0]           # most positive
    put_wall = min(per, key=lambda x: x[1])[0]            # most negative
    king_node = max(per, key=lambda x: abs(x[1]))[0]      # biggest magnet
    # Regime is the sign of AGGREGATE net GEX — a market-wide property,
    # independent of where spot sits vs the flip. (Deriving it from spot>=flip
    # coupled regime to the gate's own side-test and made the -gamma branch
    # unreachable.) net<0 => dealers short gamma => chase => trend/vol expansion.
    regime = "negative" if net < 0 else "positive"

    unusual = []
    for r in rows:
        if r.call_oi and r.call_vol / r.call_oi >= unusual_ratio:
            unusual.append((r.strike, "call", round(r.call_vol / r.call_oi, 1)))
        if r.put_oi and r.put_vol / r.put_oi >= unusual_ratio:
            unusual.append((r.strike, "put", round(r.put_vol / r.put_oi, 1)))

    return GexProfile(spot=spot, net_gex=net, flip=flip, call_wall=call_wall,
                      put_wall=put_wall, king_node=king_node, regime=regime,
                      per_strike=per, unusual=unusual)


def flow_skew(profile: GexProfile) -> float:
    """Bias from unusual-activity: +1 all call-heavy, -1 all put-heavy, 0 balanced.
    A proxy for order-flow direction until a real sweep feed is wired."""
    call = sum(r for _, side, r in profile.unusual if side == "call")
    put = sum(r for _, side, r in profile.unusual if side == "put")
    return (call - put) / (call + put) if (call + put) else 0.0


def gex_confirms(profile: GexProfile, direction: str,
                 skew: float | None = None,
                 flip_band_pct: float = 0.0015) -> tuple[bool, str]:
    """Does the GEX structure support a ``direction`` ('long'|'short') entry?

    For a LONG-PREMIUM 0DTE buyer the only regime that pays is NEGATIVE-gamma
    continuation (dealers chase -> vol expands). Positive gamma is a pinning /
    mean-reverting regime — death for a premium buyer (theta + IV crush while
    price sticks) — so it is NOT confirmed here. Within a band of the flip it is
    a coin-flip line (stale-OI flip uncertainty exceeds the distance), so that
    is an explicit no-trade. On a decisive break, a long needs spot strictly
    ABOVE the flip, a short strictly BELOW, and heavily opposing flow vetoes.
    Gates entries; does not size them.

    (flip is a GEX *balance strike* proxy from stale prior-day OI, not a
    re-priced zero-gamma level — treat it as approximate, hence the band.)
    """
    p = profile
    if direction not in ("long", "short"):
        return False, f"unknown direction {direction!r}"
    sk = flow_skew(p) if skew is None else skew

    # No-trade band around the flip — equality never double-confirms.
    if abs(p.spot - p.flip) < flip_band_pct * p.spot:
        return False, (f"at the flip ({p.flip:g}, +/-{flip_band_pct:.2%}) — "
                       f"coin-flip line, wait for a decisive break")

    on_side = p.spot > p.flip if direction == "long" else p.spot < p.flip
    if not on_side:
        verb = "reclaim" if direction == "long" else "lose"
        return False, (f"{direction} fights the flip: spot {p.spot:g} vs flip "
                       f"{p.flip:g} — {verb} it first")

    # Long premium only works in -gamma continuation; +gamma pins -> reject.
    if not p.negative_gamma:
        return False, (f"+gamma (pinning regime, net GEX {p.net_gex/1e9:+.2f}B) — "
                       f"poor for buying 0DTE premium; edge is -gamma trends only")

    if direction == "long" and sk < -0.4:
        return False, f"-gamma up but flow is put-heavy (skew {sk:+.2f}) — not confirmed"
    if direction == "short" and sk > 0.4:
        return False, f"-gamma down but flow is call-heavy (skew {sk:+.2f}) — not confirmed"
    return True, (f"-gamma continuation, {direction} side of flip {p.flip:g}, "
                  f"dealers chase (skew {sk:+.2f})")
