"""Print sequential vs concurrent timings.

    python compare.py                    # offline: three fake services, 300 ms each
    python compare.py --live URL URL URL # real HTTP calls to URLs you choose
"""

from __future__ import annotations

import argparse

import fake_services
from fetch import Timing, compare


def table(seq: Timing, conc: Timing) -> str:
    speedup = seq.total_seconds / conc.total_seconds if conc.total_seconds else float("inf")
    lines = [
        "| Mode | Total | Calls OK |",
        "| --- | --- | --- |",
    ]
    for t in (seq, conc):
        ok = sum(r.ok for r in t.results)
        lines.append(f"| {t.mode} | {t.total_seconds * 1000:.0f} ms | {ok}/{len(t.results)} |")
    lines.append("")
    lines.append(f"Concurrent was {speedup:.1f}x faster.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", nargs="+", metavar="URL", help="real URLs to call instead of the fake services")
    args = parser.parse_args()

    if args.live:
        seq, conc = compare(args.live)
    else:
        seq, conc = compare(
            fake_services.URLS,
            transport=fake_services.sync_transport(),
            async_transport=fake_services.async_transport(),
        )
    print(table(seq, conc))
    for r in conc.results:
        if not r.ok:
            print(f"  failed: {r.url} -> {r.error}")


if __name__ == "__main__":
    main()
