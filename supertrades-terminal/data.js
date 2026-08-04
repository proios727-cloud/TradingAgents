// SuperTrades app — simulated market data (deterministic seeds, live jitter applied in logic)
export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function genCandles(seed, n, start) {
  const rnd = mulberry32(seed);
  const out = []; let price = start;
  for (let i = 0; i < n; i++) {
    const drift = (rnd() - 0.47) * (start * 0.004);
    const open = price, close = price + drift;
    out.push({ open, close, high: Math.max(open, close) + rnd() * start * 0.0018, low: Math.min(open, close) - rnd() * start * 0.0018, vol: 0.4 + rnd() * 0.6 });
    price = close;
  }
  return out;
}
export const WATCHLIST = [
  { sym: 'NVDA', last: 202.55, chg: 0.71, vol: '144.3M', atr: 2.35, conf: 82, spread: 0.01 },
  { sym: 'SPY',  last: 746.74, chg: 1.04, vol: '69.4M', atr: 3.40, conf: 74, spread: 0.01 },
  { sym: 'TSLA', last: 402.90, chg: -4.02, vol: '36.1M', atr: 8.90, conf: 51, spread: 0.03 },
  { sym: 'AMD',  last: 493.61, chg: -1.47, vol: '38.7M', atr: 9.80, conf: 38, spread: 0.04 },
  { sym: 'QQQ',  last: 740.62, chg: 2.51, vol: '43.0M', atr: 5.10, conf: 66, spread: 0.01 },
  { sym: 'META', last: 642.01, chg: -3.39, vol: '12.3M', atr: 7.60, conf: 45, spread: 0.05 },
  { sym: 'COIN', last: 160.49, chg: -4.02, vol: '18.8M', atr: 6.20, conf: 71, spread: 0.03 },
  { sym: 'MSTR', last: 94.95, chg: 0.87, vol: '13.1M', atr: 4.30, conf: 29, spread: 0.02 },
  { sym: 'XOM',  last: 129.84, chg: 2.16, vol: '21.5M', atr: 2.10, conf: 76, spread: 0.01 },
  { sym: 'CVX',  last: 176.42, chg: 1.63, vol: '9.8M',  atr: 2.60, conf: 69, spread: 0.02 },
  { sym: 'XLE',  last: 103.17, chg: 1.88, vol: '17.2M', atr: 1.20, conf: 72, spread: 0.01 },
];
// Names reporting within the event window (hyperscaler week) — blocked by the event filter
export const EARNINGS = ['GOOGL', 'META', 'MSFT', 'AMZN', 'TSLA'];
export const SIGNALS = [
  { id: 'SG-8842', direction: 'long', symbol: 'NVDA', strategy: 'Squeeze confluence · 5m', entry: '202.10', stop: '201.75', target: '202.90', rr: '1 : 2.3', confidence: 82, time: '14:32:07', live: true,
    thesis: 'Price reclaimed VWAP on rising volume after holding the 201.75 shelf through two tests. Spot pressing the 205 king node from below in a −gamma pocket — dealers chase; 205C 0DTE swept at ask ($2.4M).',
    factors: [
      { label: 'King node 205', kind: 'gex', fired: true, detail: '+1.85B pin above — magnet' },
      { label: 'Squeeze regime', kind: 'gex', fired: true, detail: '−gamma pocket 199–200, dealers chase' },
      { label: 'Unusual flow', kind: 'flow', fired: true, detail: '5,100× 205C 0DTE at ask · $2.4M' },
      { label: 'VWAP reclaim', kind: 'ta', fired: true, detail: 'Held 201.75 shelf ×2, reclaimed on volume' },
      { label: 'HVN shelf 201.75', kind: 'hvn', fired: true, detail: 'Stop tucked under high-volume node' },
      { label: 'Index aligned', kind: 'mkt', fired: true, detail: 'QQQ +2.51% · TICK +412 — tailwind' },
    ] },
  { id: 'SG-8841', direction: 'short', symbol: 'TSLA', strategy: 'Gamma flip break · 1m', entry: '403.40', stop: '404.90', target: '399.60', rr: '1 : 2.5', confidence: 71, time: '14:27:44', live: true,
    thesis: 'Breakout above 405 failed on declining volume as spot lost the 402.60 gamma flip — negative gamma opens the range. 400P 0DTE sweeps confirm. Targeting the morning gap fill at 399.60.',
    factors: [
      { label: 'Gamma flip break', kind: 'gex', fired: true, detail: 'Lost 402.60 → −gamma regime' },
      { label: 'Unusual flow', kind: 'flow', fired: true, detail: '6,400× 400P 0DTE at ask · $860K' },
      { label: 'Failed breakout', kind: 'ta', fired: true, detail: '405 push absorbed, lower high' },
      { label: 'LVN below', kind: 'hvn', fired: true, detail: 'Thin volume 402.6→399.6 — fast travel' },
    ] },
  { id: 'SG-8840', direction: 'long', symbol: 'COIN', strategy: 'ORB + flow · 5m', entry: '158.60', stop: '157.90', target: '160.30', rr: '1 : 2.4', confidence: 74, time: '14:12:19', live: false, status: 'Target',
    thesis: 'Opening range breakout continuation with sector momentum and unusual call buying at the lows.',
    factors: [
      { label: 'Unusual flow', kind: 'flow', fired: true, detail: '4,200× 160C 0DTE at ask · $1.9M' },
      { label: 'ORB continuation', kind: 'ta', fired: true, detail: 'Held ORH retest' },
      { label: 'Above gamma flip', kind: 'gex', fired: true, detail: 'Spot > flip 156.50' },
    ] },
  { id: 'SG-8839', direction: 'long', symbol: 'AMD', strategy: 'Trend pullback · 15m', entry: '494.40', stop: '492.20', target: '499.50', rr: '1 : 2.3', confidence: 58, time: '13:48:02', live: false, status: 'Stopped',
    thesis: 'Pullback to rising 20EMA in an uptrend; invalidated on the 492.20 break. TA-only setup — no GEX or flow confirmation.',
    factors: [
      { label: '20EMA pullback', kind: 'ta', fired: true, detail: 'Rising 15m trend' },
      { label: 'GEX support', kind: 'gex', fired: false, detail: 'No node at entry — unprotected' },
      { label: 'Index fighting', kind: 'mkt', fired: false, veto: true, detail: 'VETO: TICK −4 min streak' },
    ] },
  { id: 'SG-8838', direction: 'short', symbol: 'META', strategy: 'Range fade at call wall · 5m', entry: '644.90', stop: '646.40', target: '641.00', rr: '1 : 2.6', confidence: 63, time: '13:22:37', live: false, status: 'Filled',
    thesis: 'Fading the top of a three-hour range into the 645 call wall on weakening breadth.',
    factors: [
      { label: 'Call wall 645', kind: 'gex', fired: true, detail: '+gamma cap — dealers sell into it' },
      { label: 'Range top', kind: 'ta', fired: true, detail: 'Third rejection, breadth fading' },
      { label: 'Flow confirm', kind: 'flow', fired: false, detail: 'No put sweeps yet' },
    ] },
];
export const POSITIONS = [
  { sym: 'NVDA', side: 'long', qty: 400, avg: 202.12, r: 0.70 },
  { sym: 'TSLA', side: 'short', qty: 100, avg: 403.38, r: 0.60 },
];
export const TRADES = [
  { time: '14:12', sym: 'COIN', side: 'long', in: '158.60', out: '160.30', r: '+2.4R', pnl: '+$680.00' },
  { time: '13:48', sym: 'AMD', side: 'long', in: '494.40', out: '492.20', r: '−1.0R', pnl: '−$210.00' },
  { time: '13:22', sym: 'META', side: 'short', in: '644.90', out: '643.05', r: '+1.9R', pnl: '+$470.00' },
  { time: '11:56', sym: 'SPY', side: 'long', in: '744.90', out: '746.20', r: '+1.6R', pnl: '+$390.00' },
  { time: '10:41', sym: 'NVDA', side: 'short', in: '201.20', out: '201.55', r: '−1.0R', pnl: '−$175.00' },
  { time: '09:52', sym: 'QQQ', side: 'long', in: '737.40', out: '739.30', r: '+2.1R', pnl: '+$532.00' },
];
export const GEX = {
  symbol: 'NVDA', spot: 202.55, flip: 199.5, kingNode: 205, callWall: 210, putWall: 195, hvl: 202.5,
  strikes: [
    { k: 187.5, gex: -0.42 }, { k: 190, gex: -0.88 }, { k: 192.5, gex: -0.61 },
    { k: 195, gex: -1.35 }, { k: 197.5, gex: -0.52 }, { k: 199, gex: -0.18 },
    { k: 200, gex: 0.24 }, { k: 202.5, gex: 0.96 }, { k: 205, gex: 1.85 },
    { k: 207.5, gex: 0.74 }, { k: 210, gex: 1.42 }, { k: 212.5, gex: 0.38 }, { k: 215, gex: 0.20 },
  ],
};
export const GEX_ALERTS = [
  { time: '14:31:52', sym: 'NVDA', kind: 'squeeze', text: 'Short-gamma squeeze setup — spot pressing 205 king node from below, dealers chasing' },
  { time: '14:29:10', sym: 'TSLA', kind: 'flip', text: 'Crossed gamma flip 402.60 → negative gamma regime, expect expanded range' },
  { time: '14:24:36', sym: 'SPY', kind: 'highvol', text: 'HIGH VOL: RVOL 3.2× at 747 node · IV 5m +14%' },
  { time: '14:18:04', sym: 'COIN', kind: 'unusual', text: 'Unusual buying at lows — 4,200× 160C 0DTE swept at ask ($1.9M)' },
];
export const EQUITY = [24810, 24790, 24960, 25120, 25080, 25310, 25290, 25490, 25440, 25620, 25580, 25810, 25890, 26094];
export const STRATEGIES = ['Squeeze confluence', 'Gamma flip break', 'ORB + flow', 'Trend pullback', 'Range fade at call wall'];
// Per-strategy risk assignment (swept for max return with worst DD ≤ ~25%): strongest edges size up, weakest sizes down.
export const STRATEGY_RISK = { 'Squeeze confluence': 0.05, 'Gamma flip break': 0.06, 'ORB + flow': 0.07, 'Trend pullback': 0.06, 'Range fade at call wall': 0.02 };
// 90-session bar-by-bar replay backtest. A deterministic daily price path is anchored to
// end at endPrice (today's real level); each session's trades are filled against that day's
// actual O/H/L/C — target hit, stop hit, or closed out at the bell. Two execution models:
// Equity = shares at 0.4% account risk/trade (compounding). Options = 0DTE premium, 5% of CURRENT balance risk/trade, capped at 40% of start ($1k on $2.5k) — 0DTE fill capacity limit. ~1.9x payoff, theta drag.
// Drawdown governance (options): daily loss limit −2R (stop trading for the day), half-size the day after a losing day until a green day.
// Press rule: once the day is ≥+2R, later trades size up 2×, extra risk funded only by the day's booked profit, never base bankroll.
// slip = round-trip slippage + bid/ask spread charged on EVERY trade, in units of
// risked premium (0DTE spreads are wide and you cross them twice). This is the
// single biggest reason raw backtests overstate 0DTE returns, so it is modeled
// explicitly and on by default. shares get a much lighter slippage (penny spreads).
export function genBacktest(seed, days = 90, endPrice = 100, riskF = 0.05, slip = 0.15) {
  const rnd = mulberry32(seed);
  const rets = [];
  for (let d = 0; d < days; d++) rets.push((rnd() - 0.485) * 0.032);
  let p = endPrice / rets.reduce((a, r) => a * (1 + r), 1);
  const curve = [{ eq: 1, op: 1 }];
  let eq = 1, op = 1, wins = 0, trades = 0, scr = 0, sumR = 0, gw = 0, gl = 0, pe = 1, po = 1, ddE = 0, ddO = 0, halfSize = false;
  const dailyOpRet = [];            // per-session options return (for Sharpe)
  let lossStreak = 0, maxLossStreak = 0;  // consecutive losing trades (0DTE risk-of-ruin read)
  for (let d = 0; d < days; d++) {
    const o = p, c = p * (1 + rets[d]);
    const h = Math.max(o, c) * (1 + rnd() * 0.007), l = Math.min(o, c) * (1 - rnd() * 0.007);
    p = c;
    // Trade selection: body/range ratio gates participation — chop days get 0-1 small trades
    const body = Math.abs(c - o) / ((h - l) || 1);
    const trendDay = body >= 0.35;
    const n = trendDay ? 2 + Math.floor(rnd() * 4) : Math.floor(rnd() * 2);
    let dE = 0, dO = 0, dayR = 0, halted = false;
    const size = halfSize ? 0.5 : 1;
    for (let t = 0; t < n; t++) {
      if (halted) break;
      const long = c >= o ? rnd() < 0.9 : rnd() < 0.1; // trade with the tape
      const sgn = long ? 1 : -1;
      const entry = o + (c - o) * rnd() * 0.25; // enter early in the move
      const risk = Math.max((h - l) * 0.35, entry * 0.0035);
      const mult = 1.5 + rnd() * 1.2;
      const target = entry + sgn * risk * mult, stop = entry - sgn * risk;
      const hitT = long ? h >= target : l <= target;
      const hitS = long ? l <= stop : h >= stop;
      let R;
      if (hitT && hitS) R = rnd() < 0.28 ? -1 : mult;
      else if (hitT) R = rnd() < 0.3 ? mult * 1.6 : mult; // 30% runners trail past target
      else if (hitS) R = -1;
      else {
        R = (sgn * (c - entry)) / risk;
        if (R < 0 && R > -0.6) R = rnd() < 0.6 ? 0 : R; // scratch weak closes at breakeven
        R = Math.max(-1, Math.min(mult, R));
      }
      trades++; sumR += R;
      if (R === 0) scr++;
      else if (R > 0) { wins++; gw += R; lossStreak = 0; }
      else { gl -= R; lossStreak++; if (lossStreak > maxLossStreak) maxLossStreak = lossStreak; }
      dE += (R - 0.03) * 0.004; // shares: light slippage/commission haircut
      let riskU = Math.min(op * riskF, 0.4); // riskF of current balance, capped at 40% of start ($1k) — capacity
      if (dayR >= 2 && dO > 0) riskU = Math.min(riskU * 2, riskU + dO * 0.5); // press winners with house money
      // 0DTE net = ~1.9x payoff, minus theta drag (0.12), minus round-trip slippage/spread (slip).
      dO += (R * 1.9 - 0.12 - slip) * riskU * size;
      dayR += R;
      if (dayR <= -2) halted = true; // daily loss limit: stop at −2R on the day
    }
    halfSize = dayR < 0; // half-size after a red day, restore after a green one
    dailyOpRet.push(op > 0 ? dO / op : 0); // return on the running options balance
    eq *= 1 + dE; op += dO; // options: fixed-$ risk, additive
    pe = Math.max(pe, eq); po = Math.max(po, op);
    ddE = Math.max(ddE, 1 - eq / pe); ddO = Math.max(ddO, 1 - op / po);
    curve.push({ eq, op });
  }
  // Risk-adjusted read on the 0DTE curve: annualized Sharpe (√252) from the daily
  // return series, and recovery factor (total return ÷ max drawdown). These are the
  // honest quality gauges of the sim — win rate alone hides drawdown and volatility.
  const mean = dailyOpRet.reduce((a, r) => a + r, 0) / (dailyOpRet.length || 1);
  const variance = dailyOpRet.reduce((a, r) => a + (r - mean) ** 2, 0) / (dailyOpRet.length || 1);
  const sd = Math.sqrt(variance);
  const sharpe = sd > 0 ? (mean / sd) * Math.sqrt(252) : 0;
  const recovery = ddO > 0 ? (op - 1) / ddO : 0;
  return { curve, trades, scratches: scr, winRate: wins / ((trades - scr) || 1), avgR: sumR / trades, pf: gw / (gl || 1), retE: eq - 1, retO: op - 1, ddE, ddO, sharpe, recovery, maxLossStreak };
}
