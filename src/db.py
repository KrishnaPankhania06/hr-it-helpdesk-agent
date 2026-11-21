"""HR database: schema, seed data, connection helpers.

Uses PostgreSQL. If DATABASE_URL is not set, a self-contained local
PostgreSQL (via the `pgserver` package) is started automatically, so the
demo runs with zero external services.
"""
import os

import psycopg

_pgserver_instance = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    department TEXT NOT NULL,
    manager TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    annual_leave_total INT NOT NULL,
    annual_leave_used INT NOT NULL
);
CREATE TABLE IF NOT EXISTS it_assets (
    asset_tag TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    device TEXT NOT NULL,
    issued_on DATE NOT NULL,
    warranty_until DATE NOT NULL
);
"""

SEED_EMPLOYEES = [
    ("E101", "Aarav Shah", "Engineering", "Priya Nair", "aarav.shah@acmetech.example", "+91 98111 22334", 24, 9),
    ("E102", "Meera Iyer", "Design", "Rohan Kulkarni", "meera.iyer@acmetech.example", "+91 98222 33445", 24, 17),
    ("E103", "Rohan Kulkarni", "Engineering", "Priya Nair", "rohan.k@acmetech.example", "+91 98333 44556", 24, 4),
    ("E104", "Sana Sheikh", "Support", "Vikram Rao", "sana.s@acmetech.example", "+91 98444 55667", 24, 11),
    ("E105", "Vikram Rao", "Support", "Anita Desai", "vikram.rao@acmetech.example", "+91 98555 66778", 24, 0),
]

SEED_ASSETS = [
    ("LP-1001", "E101", "MacBook Air M2", "2025-01-15", "2027-01-14"),
    ("LP-1002", "E102", "Dell XPS 13", "2025-03-02", "2027-03-01"),
    ("LP-1003", "E103", "Lenovo ThinkPad T14", "2024-11-20", "2026-11-19"),
    ("LP-1004", "E104", "HP EliteBook 840", "2025-06-10", "2027-06-09"),
    ("LP-1005", "E105", "MacBook Pro 14", "2025-08-01", "2027-07-31"),
]


def get_database_url():
    """Return DATABASE_URL, starting an embedded Postgres if necessary."""
    global _pgserver_instance
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if _pgserver_instance is None:
        import pgserver
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".pgdata")
        _pgserver_instance = pgserver.get_server(data_dir)
        url = _pgserver_instance.get_uri()
        os.environ["DATABASE_URL"] = url
    return os.environ["DATABASE_URL"]


def connect():
    return psycopg.connect(get_database_url())


def seed_if_empty():
    """Create tables and insert seed rows if the employees table is empty."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("SELECT COUNT(*) FROM employees")
            if cur.fetchone()[0] > 0:
                return False
            cur.executemany(
                "INSERT INTO employees VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", SEED_EMPLOYEES
            )
            cur.executemany("INSERT INTO it_assets VALUES (%s,%s,%s,%s,%s)", SEED_ASSETS)
        conn.commit()
    return True
