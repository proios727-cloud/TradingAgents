"""Generic fan-out / layered fan-in orchestration engine.

Every unit of work is a Node: an async callable plus a payload. fan_out runs
all nodes concurrently; layered_fan_in reduces results in batches (default 30)
through a summarizer, recursing until one summary remains; run() wires
fan_out -> layered_fan_in -> final_reporter.

Nodes are independent by contract: a node receives only its own payload and a
shared read-only snapshot, never another node's output. Sequencing belongs in
discovery (before fan_out) or the final reporter (after fan_in).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Sequence

NodeFn = Callable[[dict, dict], Awaitable[dict]]
Summarizer = Callable[[Sequence[dict]], dict]
FinalReporter = Callable[[dict, dict], dict]


@dataclass(frozen=True)
class Node:
    """One independent unit of work."""
    kind: str          # e.g. "ticker_signal", "gex_map", "position_exit", "candidate_entry"
    key: str           # e.g. "NVDA", "QQQ", option instrument id
    fn: NodeFn
    payload: dict = field(default_factory=dict)


@dataclass
class NodeResult:
    kind: str
    key: str
    ok: bool
    data: dict
    error: str | None = None

    def as_dict(self) -> dict:
        return {"kind": self.kind, "key": self.key, "ok": self.ok,
                "data": self.data, "error": self.error}


class Orchestrator:
    def __init__(self, batch_size: int = 30, max_concurrency: int = 32):
        if batch_size < 2:
            raise ValueError("batch_size must be >= 2 for fan-in to converge")
        self.batch_size = batch_size
        self._sem = asyncio.Semaphore(max_concurrency)

    async def _run_node(self, node: Node, snapshot: dict) -> NodeResult:
        async with self._sem:
            try:
                data = await node.fn(node.payload, snapshot)
                return NodeResult(node.kind, node.key, True, data)
            except Exception as exc:  # a failed node never sinks the cycle
                return NodeResult(node.kind, node.key, False, {}, f"{type(exc).__name__}: {exc}")

    async def fan_out(self, nodes: Sequence[Node], snapshot: dict) -> list[NodeResult]:
        """Run every node concurrently against a shared read-only snapshot."""
        return list(await asyncio.gather(*(self._run_node(n, snapshot) for n in nodes)))

    def layered_fan_in(self, results: Sequence[dict], summarizer: Summarizer) -> dict:
        """Reduce results through summarizer in batches, recursing past batch_size."""
        items = list(results)
        if not items:
            return summarizer([])
        while len(items) > 1 or "__summary__" not in (items[0] if items else {}):
            batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
            items = [summarizer(b) for b in batches]
            if len(batches) == 1:
                break
        return items[0]

    async def run(self, nodes: Sequence[Node], snapshot: dict,
                  summarizer: Summarizer, final_reporter: FinalReporter) -> dict:
        results = await self.fan_out(nodes, snapshot)
        summary = self.layered_fan_in([r.as_dict() for r in results], summarizer)
        return final_reporter(summary, snapshot)
