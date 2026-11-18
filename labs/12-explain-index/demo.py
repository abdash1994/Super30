"""Print the before/after table in the README. Run: python demo.py"""

import sqlite3

from plan import (BY_CUSTOMER, BY_DAY_FUNCTION, BY_DAY_RANGE, insert_work,
                  measure, seed)


def build() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    seed(conn)
    return conn


def run() -> list:
    conn = build()
    results = []
    results.append(measure(conn, "customer_id = ?, no index", BY_CUSTOMER, (42,)))
    write_before = insert_work(conn)

    conn.execute("CREATE INDEX idx_orders_customer ON orders(customer_id)")
    conn.execute("CREATE INDEX idx_orders_created ON orders(created_at)")
    conn.execute("ANALYZE")
    results.append(measure(conn, "customer_id = ?, with index", BY_CUSTOMER, (42,)))
    results.append(measure(conn, "date(created_at) = ?, with index",
                           BY_DAY_FUNCTION, ("2026-03-01",)))
    results.append(measure(conn, "created_at range, with index",
                           BY_DAY_RANGE, ("2026-03-01", "2026-03-02")))
    write_after = insert_work(conn)
    return results, write_before, write_after


if __name__ == "__main__":
    results, wb, wa = run()
    print("| Query | Plan | Full scan | Work units | Rows |")
    print("| --- | --- | --- | --- | --- |")
    for m in results:
        print(f"| {m.label} | `{' / '.join(m.plan)}` | {'yes' if m.full_scan else 'no'} "
              f"| {m.work:,} | {m.rows} |")
    print()
    print(f"Insert 1,000 rows: {wb:,} work units with 0 extra indexes, "
          f"{wa:,} with 2 ({wa / wb:.1f}x)")
