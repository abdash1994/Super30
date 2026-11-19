"""Read the three numbers that matter from PostgreSQL EXPLAIN ANALYZE text.

On a real client database (Postgres, Supabase) you run
`EXPLAIN (ANALYZE, BUFFERS) <query>` and get a text plan. This turns it
into a small summary so before/after can be compared in a ticket or a PR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NODE = re.compile(r"^\s*(?:->\s*)?([A-Z][A-Za-z ]+?)(?: on | using |\s+\(cost=)")
_EXEC = re.compile(r"Execution Time:\s*([\d.]+)\s*ms")
_REMOVED = re.compile(r"Rows Removed by Filter:\s*(\d+)")


@dataclass
class PlanSummary:
    top_node: str
    execution_ms: float
    rows_removed_by_filter: int

    @property
    def is_seq_scan(self) -> bool:
        return "Seq Scan" in self.top_node


def summarise(plan_text: str) -> PlanSummary:
    lines = [line for line in plan_text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty plan")
    node = None
    for line in lines:
        match = _NODE.match(line)
        if match:
            node = match.group(1).strip()
            break
    exec_match = _EXEC.search(plan_text)
    if node is None or exec_match is None:
        raise ValueError("not EXPLAIN ANALYZE output (need a plan node and Execution Time)")
    removed = sum(int(n) for n in _REMOVED.findall(plan_text))
    return PlanSummary(node, float(exec_match.group(1)), removed)


def speedup(before: PlanSummary, after: PlanSummary) -> float:
    if after.execution_ms <= 0:
        raise ValueError("after.execution_ms must be positive")
    return before.execution_ms / after.execution_ms
