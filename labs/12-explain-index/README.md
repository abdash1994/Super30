# Lab 12: read the query plan, before and after an index

**Result:** on 50,000 seeded orders, finding one customer's 7 orders goes from a full table scan (15,003 work units) to an index search (6 work units), about 2,500x less work for the same 7 rows; but the same index is ignored when the query wraps the column in a function (`date(created_at) = ?`: full scan, 20,035 units), and the two indexes make every insert about 1.6x more expensive.

## The problem

"The dashboard is slow" is one of the most common client complaints, and the cause is usually one query reading the whole table to return a handful of rows. Guessing ("add more servers", "add an index on everything") wastes money. The database will tell you exactly what it does if you ask: in PostgreSQL that is `EXPLAIN ANALYZE`, which runs the query and prints the plan with real row counts and timings.

Two words in a plan matter most:

- **Scan** (Postgres `Seq Scan`, SQLite `SCAN`): read every row and throw away the ones that don't match.
- **Search / Index Scan:** jump straight to the matching rows using an index, like the index at the back of a book.

## What this lab does

| File | Job |
| --- | --- |
| `plan.py` | Seeds an `orders` table (50,000 rows, 5,000 customers, 300 days, fixed random seed) in SQLite, reads the plan with `EXPLAIN QUERY PLAN`, and measures work by counting SQLite VM instructions (1 work unit = 10 instructions). |
| `pg_explain.py` | Reads real PostgreSQL `EXPLAIN ANALYZE` text and pulls out the top plan node, `Execution Time` and `Rows Removed by Filter`, so a before/after can go into a ticket. |
| `demo.py` | Runs the four queries below and the insert test, and prints the table. |
| `test_plan.py`, `test_pg_explain.py` | 16 tests: the plan flips from scan to search, the answer is identical with and without the index, the >100x drop, the function trap, the write cost, and the Postgres reader on sample plans. |

`python demo.py` output (same numbers on SQLite 3.45 and 3.53; the tests check the ratios, not the exact counts):

| Query | Plan | Full scan | Work units | Rows |
| --- | --- | --- | --- | --- |
| `customer_id = ?`, no index | `SCAN orders` | yes | 15,003 | 7 |
| `customer_id = ?`, with index | `SEARCH orders USING INDEX idx_orders_customer (customer_id=?)` | no | 6 | 7 |
| `date(created_at) = ?`, with index | `SCAN orders USING COVERING INDEX idx_orders_created` | yes | 20,035 | 172 |
| `created_at` range, with index | `SEARCH orders USING COVERING INDEX idx_orders_created (created_at>? AND created_at<?)` | no | 70 | 172 |

Inserting 1,000 rows: 2,000 work units with no extra indexes, 3,100 with two (1.6x).

Note row 3: the plan mentions an index, but it starts with `SCAN`, so it still reads every entry. Asking for "orders on 1 March" as `created_at >= '2026-03-01' AND created_at < '2026-03-02'` returns the same 172 rows with about 290x less work.

Why work units and not milliseconds: timings on a shared CI machine jump around, so a test on them would be flaky. Counted instructions give the same number on every run.

## Run it

```bash
pip install -r requirements.txt
pytest -q          # 16 tests, standard library only, no database server
python demo.py     # prints the table above
```

On a real Postgres or Supabase database, the same experiment is:

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT id, amount_inr FROM orders WHERE customer_id = 42;
CREATE INDEX idx_orders_customer ON orders (customer_id);
EXPLAIN (ANALYZE, BUFFERS) SELECT id, amount_inr FROM orders WHERE customer_id = 42;
```

Paste each output into `pg_explain.summarise(text)` to get `Seq Scan` vs `Index Scan`, the execution time and the rows thrown away. Note that `EXPLAIN ANALYZE` really runs the query, so wrap an `UPDATE` or `DELETE` in `BEGIN; ... ROLLBACK;`.

## Why it matters to a business

A forward deployed engineer often walks into a client whose app "got slow" as data grew. Reading one plan turns that into a specific, cheap fix ("this screen reads all 50,000 orders to show 7; one index makes it a lookup") instead of a bigger database bill. The before/after plan is also the evidence a client's DBA or change board will ask for before approving a change on production.

## Trade-off

Indexes are not free. Every index is extra storage and extra work on every insert and update (1.6x here with two), and building one on a large live table can lock writes unless done with `CREATE INDEX CONCURRENTLY` in Postgres. So index the columns real, frequent queries filter on, and check the plan rather than indexing everything. An index also only helps if the query lets the database use it: functions on the column, leading-wildcard `LIKE '%abc'` and mismatched types all fall back to a scan. On a tiny table a scan is often faster anyway, which is why the planner sometimes ignores an index you just made. SQLite is a stand-in here so the lab runs without a server; Postgres plans use different words and have more plan types (bitmap scans, parallel scans), which the Postgres reader handles.
