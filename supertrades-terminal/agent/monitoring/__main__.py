"""CLI: score a snapshot file and print (or write) the session report.

    cd supertrades-terminal
    python -m agent.monitoring snapshot.json                # report to stdout
    python -m agent.monitoring snapshot.json -o report.md   # and write file
    python -m agent.monitoring snapshot.json --json         # metrics as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .report import render
from .scorer import load_snapshot, score_snapshot


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agent.monitoring")
    p.add_argument("snapshot", help="snapshot JSON file from the monitoring loop")
    p.add_argument("-o", "--out", help="also write the markdown report here")
    p.add_argument("--json", action="store_true", help="print metrics/violations as JSON")
    args = p.parse_args(argv)

    score = score_snapshot(load_snapshot(args.snapshot))
    if args.json:
        print(json.dumps({
            "adherence": score.adherence,
            "metrics": score.metrics,
            "violations": [vars(v) for v in score.violations],
            "recommendations": score.recommendations,
        }, indent=2, default=str))
    else:
        print(render(score))
    if args.out:
        Path(args.out).write_text(render(score))
    return 0


if __name__ == "__main__":
    sys.exit(main())
