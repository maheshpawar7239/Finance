import sqlite3
import uuid
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_password(password: str) -> str:
    salt = "finance_backend_salt"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('viewer', 'analyst', 'admin')),
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS financial_records (
            id          TEXT PRIMARY KEY,
            amount      REAL NOT NULL CHECK(amount > 0),
            type        TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            notes       TEXT,
            created_by  TEXT NOT NULL REFERENCES users(id),
            is_deleted  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def seed_data():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    users = [
        (str(uuid.uuid4()), "admin@test.com",   hash_password("password123"), "admin"),
        (str(uuid.uuid4()), "analyst@test.com", hash_password("password123"), "analyst"),
        (str(uuid.uuid4()), "viewer@test.com",  hash_password("password123"), "viewer"),
    ]
    conn.executemany(
        "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)", users
    )

    admin_id = users[0][0]
    records = [
        (str(uuid.uuid4()), 85000.00, "income",  "Salary",      "2026-01-05", "January salary",          admin_id),
        (str(uuid.uuid4()), 12000.00, "income",  "Freelance",   "2026-01-12", "Website project payment", admin_id),
        (str(uuid.uuid4()),  3200.00, "expense", "Rent",        "2026-01-01", "Monthly rent",            admin_id),
        (str(uuid.uuid4()),   850.00, "expense", "Utilities",   "2026-01-08", "Electricity and internet", admin_id),
        (str(uuid.uuid4()),  4500.00, "expense", "Salaries",    "2026-01-15", "Contractor pay",          admin_id),
        (str(uuid.uuid4()), 85000.00, "income",  "Salary",      "2026-02-05", "February salary",         admin_id),
        (str(uuid.uuid4()),  7500.00, "income",  "Consulting",  "2026-02-18", "Strategy consulting",     admin_id),
        (str(uuid.uuid4()),  3200.00, "expense", "Rent",        "2026-02-01", "Monthly rent",            admin_id),
        (str(uuid.uuid4()),  1200.00, "expense", "Software",    "2026-02-10", "SaaS subscriptions",      admin_id),
        (str(uuid.uuid4()),   620.00, "expense", "Utilities",   "2026-02-08", "Electricity",             admin_id),
        (str(uuid.uuid4()), 85000.00, "income",  "Salary",      "2026-03-05", "March salary",            admin_id),
        (str(uuid.uuid4()),  3200.00, "expense", "Rent",        "2026-03-01", "Monthly rent",            admin_id),
        (str(uuid.uuid4()),  9800.00, "expense", "Equipment",   "2026-03-20", "Laptop and peripherals",  admin_id),
        (str(uuid.uuid4()),  5000.00, "income",  "Freelance",   "2026-03-25", "Design project",          admin_id),
        (str(uuid.uuid4()),   780.00, "expense", "Utilities",   "2026-03-08", "Utilities March",         admin_id),
    ]
    conn.executemany(
        "INSERT INTO financial_records (id, amount, type, category, date, notes, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        records,
    )

    conn.commit()
    conn.close()
    print("[seed] Created 3 users and 15 sample financial records.")
