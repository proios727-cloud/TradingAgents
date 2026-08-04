"""READ-ONLY smoke test against the REAL Robinhood MCP dispatcher/transport.

No code on this branch has ever made a real HTTP call to Robinhood — all
other tests use in-memory fakes. The dispatcher (``broker/mcp_dispatch.py``)
parses strictly: any missing or renamed field raises and trips the kill
switch. This module surfaces those schema mismatches while the system is
still inert (``armed=False, dry_run=True``), instead of at market open with
an armed account.

    python3 -m agent.cli smoke

Safety design — read carefully:

  * **Read-only, always.** Every check below calls a parsed *read* accessor
    on ``RobinhoodMcpBroker`` (``get_account``, ``get_positions``,
    ``get_chain``) — never ``place_order`` / ``cancel_all``. The underlying
    dispatcher (``broker/mcp_dispatch.py``) independently refuses any
    mutating tool while ``dry_run=True`` or ``armed=False``, and refuses
    ``REFUSED_TOOLS`` / anything matching ``_MUTATING_PREFIXES`` outright —
    this module adds no new gate and loosens none of the existing ones.
  * **Pre-flight invariant.** ``run_smoke`` refuses outright (raises
    ``SmokeRefused``, nothing constructed, nothing dispatched) unless
    ``cfg.armed is False`` and ``cfg.dry_run is True``. This is a pre-arm
    diagnostic; it must never be usable as a live-trading side door.
  * **No credentials, no run.** This builds the REAL dispatcher via
    ``RobinhoodMcpBroker.live`` — the same code path live trading uses — so
    with no ``transport`` override it constructs the real HTTP transport,
    which itself refuses to construct without ``ROBINHOOD_MCP_TOKEN``. There
    is deliberately no fallback to ``PaperBroker`` here: that would validate
    nothing and defeat the entire point of this command. The ``transport``
    override exists only so tests can inject an in-memory fake in place of
    real HTTP — never wire a fake transport for an operator run.
  * **Never aborts on the first failure.** Each check is run and caught
    independently; a parse failure on one check does not skip the rest. The
    exception text is preserved verbatim — that text is the deliverable, not
    a paraphrase.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .broker.robinhood_mcp import RobinhoodMcpBroker
from .config import RuntimeConfig, WATCHLIST
from .kill_switch import KillState


class SmokeRefused(RuntimeError):
    """Raised when the smoke test refuses to run at all (pre-flight gate) —
    before the dispatcher/transport is even constructed."""


@dataclass
class CheckResult:
    name: str
    ok: bool
    latency_s: float
    error: str = ""


def _assert_inert(cfg: RuntimeConfig) -> None:
    """This is a pre-arm diagnostic, not a live-trading side door."""
    if cfg.armed is not False or cfg.dry_run is not True:
        raise SmokeRefused(
            "refusing to run: the smoke test requires armed=False and "
            f"dry_run=True (got armed={cfg.armed!r}, dry_run={cfg.dry_run!r}). "
            "This command is a pre-arm diagnostic and must never run against "
            "an armed/live configuration."
        )


def _run_one(name: str, fn: Callable[[], object]) -> CheckResult:
    start = time.monotonic()
    try:
        fn()
        return CheckResult(name, True, time.monotonic() - start)
    except Exception as e:  # noqa: BLE001 — the exception text IS the deliverable
        return CheckResult(
            name, False, time.monotonic() - start, f"{type(e).__name__}: {e}"
        )


def build_checks(
    broker: RobinhoodMcpBroker, watchlist: Sequence[str] = WATCHLIST,
) -> list[tuple[str, Callable[[], object]]]:
    """The read set. Prefers the broker's PARSED accessors over raw dispatch
    wherever one exists, because the point is to validate parsing, not just
    connectivity:

      * get_accounts       -> broker.get_account()   (account/balance parsing)
      * get_option_positions -> broker.get_positions() (position parsing)
      * get_option_chains  -> broker.get_chain(symbol), one per watchlist
        symbol from config — this also exercises get_option_instruments and
        get_option_quotes (and their strict Greek/price parsing) since
        get_chain fans out to both for the day's 0DTE chain.

    Deliberately excludes ``get_equity_quotes``: this agent trades 0DTE
    options only and neither the broker nor the dispatcher's ``READ_TOOLS``
    exposes an equity-quote accessor (see ``broker/mcp_dispatch.py``). Adding
    it here would just re-prove the dispatcher's own tool allowlist gate,
    not surface anything about the real API's schema — and per the existing
    "everything else is refused" design, that gate is not ours to loosen.
    """
    checks: list[tuple[str, Callable[[], object]]] = [
        ("get_accounts (broker.get_account)", broker.get_account),
        ("get_option_positions (broker.get_positions)", broker.get_positions),
    ]
    for symbol in watchlist:
        checks.append((
            f"get_option_chains:{symbol} (broker.get_chain)",
            (lambda s=symbol: broker.get_chain(s)),
        ))
    return checks


def run_smoke(
    cfg: RuntimeConfig,
    *,
    kill_state: Optional[KillState] = None,
    transport=None,
    watchlist: Sequence[str] = WATCHLIST,
) -> tuple[list[CheckResult], int]:
    """Run the read-only smoke suite through the REAL dispatcher/transport
    code path (``RobinhoodMcpBroker.live`` / ``broker/mcp_dispatch.py``).

    ``transport`` is a test-only escape hatch for injecting an in-memory fake
    in place of real HTTP — never pass it from an operator entry point. With
    ``transport=None`` (the only way ``cli.py`` calls this), constructing the
    live dispatcher requires ``ROBINHOOD_MCP_TOKEN``; its absence raises
    ``McpDispatchError`` before anything is dispatched, which the caller
    should catch and report as a clean refusal.

    Returns ``(results, exit_code)`` — ``exit_code`` is 0 only if every check
    passed. Raises ``SmokeRefused`` if the armed/dry_run pre-flight gate
    fails, and propagates ``McpDispatchError`` if the dispatcher itself can't
    be constructed (e.g. missing token) — both are refusals to even start,
    not a check result, so they are never folded into the tally.
    """
    _assert_inert(cfg)

    ks = kill_state or KillState()
    broker = RobinhoodMcpBroker.live(cfg, kill_state=ks, transport=transport)

    checks = build_checks(broker, watchlist)
    results = [_run_one(name, fn) for name, fn in checks]
    exit_code = 0 if all(r.ok for r in results) else 1
    return results, exit_code


def format_report(results: list[CheckResult]) -> str:
    lines = [
        "SuperTrades smoke test — READ-ONLY, real dispatcher/transport",
        "",
    ]
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        lines.append(f"  [{status}] {r.name}  ({r.latency_s * 1000:.0f} ms)")
        if not r.ok:
            lines.append(f"         {r.error}")
    passed = sum(1 for r in results if r.ok)
    lines.append("")
    lines.append(f"{passed}/{len(results)} checks passed")
    if passed != len(results):
        lines.append("SMOKE TEST FAILED — do not arm until every check passes.")
    return "\n".join(lines)
