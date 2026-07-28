"""Render a SessionScore as a markdown session report.

Pure formatting — every number comes from scorer. Account numbers arrive
pre-masked in the snapshot; nothing here should widen what gets written."""

from __future__ import annotations

from .scorer import RoundTrip, SessionScore

_SEV_ORDER = {"high": 0, "medium": 1, "info": 2}
_SEV_MARK = {"high": "🔴", "medium": "🟡", "info": "ℹ️"}


def _fmt_trade_row(t: RoundTrip) -> str:
    entry = t.entry_ts.strftime("%H:%M")
    if t.closed:
        exit_s = t.exit_ts.strftime("%H:%M")
        pnl = f"{t.pnl:+.0f}"
        pct = f"{t.pct:+.0%}"
        r = f"{t.r_multiple:+.2f}R"
        hold = f"{t.hold_minutes:.0f}m"
    else:
        exit_s, hold = "open", "—"
        pnl = "—" if t.pct is None else f"{t.pct * t.entry_premium:+.0f}*"
        pct = "—" if t.pct is None else f"{t.pct:+.0%}*"
        r = "—"
    dte = "0DTE" if t.dte_at_entry == 0 else f"{t.dte_at_entry}DTE"
    return (f"| {t.label()} | {dte} | {entry} | {exit_s} | ${t.entry_premium:.0f} "
            f"| {pnl} | {pct} | {r} | {hold} |")


def render(score: SessionScore) -> str:
    s, m = score.snapshot, score.metrics
    lines = [
        f"# Session report — {s.session_date.isoformat()} (Agentic {s.account_masked})",
        "",
        f"Captured {s.captured_at.strftime('%H:%M')} ET · account value "
        f"${s.total_value:,.2f} · cash ${s.cash:,.2f} · buying power ${s.buying_power:,.2f}",
        "",
        f"**Adherence {score.adherence:.0f}/100** · realized {m['realized_pnl']:+,.0f} "
        f"({m['total_r']:+.2f}R) · {m['n_closed']} closed / {m['n_open']} open",
        "",
        "## Trades",
        "",
        "| Contract | DTE | In (ET) | Out | Premium | P&L $ | P&L % | R | Hold |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in score.closed + score.open_lots:
        lines.append(_fmt_trade_row(t))
    if score.open_lots and any(t.mark is not None for t in score.open_lots):
        lines.append("")
        lines.append("`*` unrealized, from last mark.")

    lines += ["", "## Guardrail findings", ""]
    if score.violations:
        for v in sorted(score.violations, key=lambda v: _SEV_ORDER.get(v.severity, 9)):
            where = f" — {v.trade}" if v.trade else ""
            lines.append(f"- {_SEV_MARK.get(v.severity, '')} **{v.rule}**{where}: {v.detail}")
    else:
        lines.append("- Clean session — no guardrail findings.")

    lines += [
        "",
        "## Efficacy",
        "",
        f"- Win rate {m['win_rate']:.0%} · avg {m['avg_r']:+.2f}R · profit factor "
        + ("∞" if m["profit_factor"] == float("inf") else f"{m['profit_factor']:.2f}"),
        f"- Avg winner {m['avg_win_pct']:+.0%} · avg loser {m['avg_loss_pct']:+.0%} · "
        f"median hold {m['median_hold_min']:.0f}m",
    ]

    lines += ["", "## Recommendations", ""]
    if score.recommendations:
        lines += [f"{i}. {r}" for i, r in enumerate(score.recommendations, 1)]
    else:
        lines.append("None — keep doing what the data says is working.")
    lines.append("")
    return "\n".join(lines)
