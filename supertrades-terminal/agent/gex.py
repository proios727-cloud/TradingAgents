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
    regime = "positive" if spot >= flip else "negative"

    unusual = []
    for r in rows:
        if r.call_oi and r.call_vol / r.call_oi >= unusual_ratio:
            unusual.append((r.strike, "call", round(r.call_vol / r.call_oi, 1)))
        if r.put_oi and r.put_vol / r.put_oi >= unusual_ratio:
            unusual.append((r.strike, "put", round(r.put_vol / r.put_oi, 1)))

    return GexProfile(spot=spot, net_gex=net, flip=flip, call_wall=call_wall,
                      put_wall=put_wall, king_node=king_node, regime=regime,
                      per_strike=per, unusual=unusual)


def gex_confirms(profile: GexProfile, direction: str) -> tuple[bool, str]:
    """Does the GEX structure support a ``direction`` ('long'|'short') entry?

    The SuperTrades read: in a NEGATIVE-gamma regime dealers chase, so momentum
    continuation is favored toward the king node / into the wall. In POSITIVE
    gamma dealers fade, so breakouts stall — only take continuation when spot is
    clear of the flip. This gates entries; it does not size them.
    """
    p = profile
    if direction == "long":
        if p.negative_gamma and p.spot <= p.call_wall:
            return True, f"-gamma, room to call wall {p.call_wall:g} (dealers chase up)"
        if not p.negative_gamma and p.spot > p.flip:
            return True, f"+gamma but above flip {p.flip:g} — trend intact"
        return False, f"long not supported (regime {p.regime}, spot {p.spot:g} vs flip {p.flip:g})"
    if direction == "short":
        if p.negative_gamma and p.spot >= p.put_wall:
            return True, f"-gamma, room to put wall {p.put_wall:g} (dealers chase down)"
        if not p.negative_gamma and p.spot < p.flip:
            return True, f"+gamma but below flip {p.flip:g} — trend intact"
        return False, f"short not supported (regime {p.regime}, spot {p.spot:g} vs flip {p.flip:g})"
    return False, f"unknown direction {direction!r}"
