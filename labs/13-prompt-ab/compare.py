"""Print the v1 vs v2 scorecard from the saved answers. No network, no key.

    python compare.py
"""

from __future__ import annotations

from promptlab import compare, load_eval_set, load_outputs


def report(max_broken: int = 1) -> str:
    items = load_eval_set()
    result = compare(items, load_outputs("v1"), load_outputs("v2"), max_broken=max_broken)
    rows = [
        "| Prompt | Correct | Wrong label | Unparseable | Accuracy |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, s in (("v1", result.old), ("v2", result.new)):
        rows.append(f"| {name} | {s.correct}/{s.total} | {s.wrong} | {s.invalid} | {s.accuracy:.0%} |")
    rows += [
        "",
        f"Fixed by v2 ({len(result.fixed)}): {', '.join(result.fixed) or '-'}",
        f"Broken by v2 ({len(result.broken)}): {', '.join(result.broken) or '-'}",
        f"Ship v2 (more correct, at most {max_broken} broken): {'yes' if result.ship else 'no'}",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    print(report())
