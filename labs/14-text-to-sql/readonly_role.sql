-- The same "read-only user" on a real PostgreSQL / Supabase database.
-- Not run in CI (no database server there); the SQLite version in text_to_sql.py is.
-- Replace the password and run as an admin.

CREATE ROLE analyst_bot LOGIN PASSWORD 'change-me';

-- Can connect and see the schema, nothing more by default.
REVOKE ALL ON SCHEMA public FROM analyst_bot;
GRANT USAGE ON SCHEMA public TO analyst_bot;

-- Read only the tables the bot is meant to answer questions about.
GRANT SELECT ON customers, orders TO analyst_bot;
-- staff_salaries gets no grant, so any query on it fails with "permission denied".

-- Every transaction this role opens is read-only, and no query runs longer than 5 s.
ALTER ROLE analyst_bot SET default_transaction_read_only = on;
ALTER ROLE analyst_bot SET statement_timeout = '5s';
