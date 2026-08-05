# TradingAgents/graph/parallel_analysts.py
"""Run analysts as isolated, parallel branches.

The four analysts never read each other's output — they only feed the
researcher debate through their report keys. In the sequential wiring they
share the graph's single ``messages`` channel, which is both why they must
run one-after-another and why the ``Msg Clear`` nodes exist at all.

The wrapper below runs an analyst's ReAct loop (analyst -> tools -> analyst)
against a *local* message list instead of graph state, and returns only the
analyst's report key. With no shared channel, LangGraph can fan all four out
from START in one superstep: analyst-phase wall clock drops from the sum of
the four loops to the slowest single loop, and no clear-nodes are needed.
"""

from typing import Callable

from langchain_core.messages import HumanMessage


def make_isolated_analyst(
    analyst_node: Callable,
    tool_node,
    report_key: str,
    max_tool_rounds: int = 8,
) -> Callable:
    """Wrap an analyst node + its ToolNode into one self-contained graph node.

    ``max_tool_rounds`` bounds the ReAct loop the same way the graph's
    recursion limit bounded it before; on hitting the bound the analyst's
    last text response (if any) still lands in the report key.
    """

    def isolated_analyst(state) -> dict:
        local = {
            "messages": [HumanMessage(content=state["company_of_interest"])],
            "company_of_interest": state["company_of_interest"],
            "trade_date": state["trade_date"],
        }

        report = ""
        for _ in range(max_tool_rounds + 1):
            out = analyst_node(local)
            local["messages"] = local["messages"] + list(out.get("messages", []))
            report = out.get(report_key) or report

            last = local["messages"][-1]
            if not getattr(last, "tool_calls", None):
                break
            tool_out = tool_node.invoke({"messages": local["messages"]})
            local["messages"] = local["messages"] + list(tool_out.get("messages", []))

        return {report_key: report}

    return isolated_analyst


REPORT_KEYS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}
