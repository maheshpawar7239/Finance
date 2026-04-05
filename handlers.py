import uuid
from urllib.parse import parse_qs

from database import get_connection, hash_password, verify_password
from auth import create_token
from server import json_response, error, parse_body, require_auth
from validators import validate_record, validate_record_update, validate_user_create


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row_to_dict(row) -> dict:
    return dict(row)


def paginate(query_params: dict) -> tuple[int, int]:
    try:
        page = max(1, int(query_params.get("page", [1])[0]))
    except (ValueError, IndexError):
        page = 1
    try:
        limit = min(100, max(1, int(query_params.get("limit", [20])[0])))
    except (ValueError, IndexError):
        limit = 20
    return page, limit


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login(handler, params, query):
    body = parse_body(handler)
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return error(handler, 400, "Both 'email' and 'password' are required")

    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
    ).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return error(handler, 401, "Invalid email or password")

    token = create_token(user["id"], user["email"], user["role"])
    json_response(handler, 200, {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
    })


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def list_users(handler, params, query):
    user, denied = require_auth(handler, "admin")
    if denied:
        return
    conn = get_connection()
    rows = conn.execute("SELECT id, email, role, is_active, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    json_response(handler, 200, [row_to_dict(r) for r in rows])


def create_user(handler, params, query):
    current, denied = require_auth(handler, "admin")
    if denied:
        return
    body = parse_body(handler)
    errs = validate_user_create(body)
    if errs:
        return error(handler, 400, "; ".join(errs))

    email = body["email"].strip().lower()
    role = body.get("role", "viewer")

    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return error(handler, 409, f"A user with email '{email}' already exists")

    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (uid, email, hash_password(body["password"]), role),
    )
    conn.commit()
    row = conn.execute("SELECT id, email, role, is_active, created_at FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    json_response(handler, 201, row_to_dict(row))


def get_me(handler, params, query):
    current, denied = require_auth(handler)
    if denied:
        return
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, role, is_active, created_at FROM users WHERE id = ?", (current["sub"],)
    ).fetchone()
    conn.close()
    if not row:
        return error(handler, 404, "User not found")
    json_response(handler, 200, row_to_dict(row))


def get_user(handler, params, query):
    current, denied = require_auth(handler, "admin")
    if denied:
        return
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, role, is_active, created_at FROM users WHERE id = ?", (params["user_id"],)
    ).fetchone()
    conn.close()
    if not row:
        return error(handler, 404, "User not found")
    json_response(handler, 200, row_to_dict(row))


def update_user(handler, params, query):
    current, denied = require_auth(handler, "admin")
    if denied:
        return
    body = parse_body(handler)
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (params["user_id"],)).fetchone()
    if not row:
        conn.close()
        return error(handler, 404, "User not found")

    updates = {}
    if "role" in body:
        if body["role"] not in ("viewer", "analyst", "admin"):
            conn.close()
            return error(handler, 400, "'role' must be one of: viewer, analyst, admin")
        updates["role"] = body["role"]
    if "is_active" in body:
        updates["is_active"] = 1 if body["is_active"] else 0

    if not updates:
        conn.close()
        return error(handler, 400, "Provide at least one field to update: 'role' or 'is_active'")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (*updates.values(), params["user_id"]))
    conn.commit()
    updated = conn.execute(
        "SELECT id, email, role, is_active, created_at FROM users WHERE id = ?", (params["user_id"],)
    ).fetchone()
    conn.close()
    json_response(handler, 200, row_to_dict(updated))


def deactivate_user(handler, params, query):
    current, denied = require_auth(handler, "admin")
    if denied:
        return
    if params["user_id"] == current["sub"]:
        return error(handler, 400, "You can't deactivate your own account")
    conn = get_connection()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (params["user_id"],)).fetchone()
    if not row:
        conn.close()
        return error(handler, 404, "User not found")
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (params["user_id"],))
    conn.commit()
    conn.close()
    json_response(handler, 200, {"message": "User deactivated"})


# ---------------------------------------------------------------------------
# Financial Records
# ---------------------------------------------------------------------------

def list_records(handler, params, query):
    current, denied = require_auth(handler, "viewer", "analyst", "admin")
    if denied:
        return

    page, limit = paginate(query)
    conditions = ["is_deleted = 0"]
    sql_params = []

    rec_type = query.get("type", [None])[0]
    if rec_type:
        if rec_type not in ("income", "expense"):
            return error(handler, 400, "'type' must be 'income' or 'expense'")
        conditions.append("type = ?")
        sql_params.append(rec_type)

    category = query.get("category", [None])[0]
    if category:
        conditions.append("category LIKE ?")
        sql_params.append(f"%{category}%")

    date_from = query.get("date_from", [None])[0]
    if date_from:
        conditions.append("date >= ?")
        sql_params.append(date_from)

    date_to = query.get("date_to", [None])[0]
    if date_to:
        conditions.append("date <= ?")
        sql_params.append(date_to)

    where = " AND ".join(conditions)
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM financial_records WHERE {where}", sql_params).fetchone()[0]
    offset = (page - 1) * limit
    rows = conn.execute(
        f"SELECT id, amount, type, category, date, notes, created_by, created_at "
        f"FROM financial_records WHERE {where} ORDER BY date DESC LIMIT ? OFFSET ?",
        sql_params + [limit, offset],
    ).fetchall()
    conn.close()

    json_response(handler, 200, {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [row_to_dict(r) for r in rows],
    })


def get_record(handler, params, query):
    current, denied = require_auth(handler, "viewer", "analyst", "admin")
    if denied:
        return
    conn = get_connection()
    row = conn.execute(
        "SELECT id, amount, type, category, date, notes, created_by, created_at "
        "FROM financial_records WHERE id = ? AND is_deleted = 0",
        (params["record_id"],),
    ).fetchone()
    conn.close()
    if not row:
        return error(handler, 404, "Record not found")
    json_response(handler, 200, row_to_dict(row))


def create_record(handler, params, query):
    current, denied = require_auth(handler, "analyst", "admin")
    if denied:
        return
    body = parse_body(handler)
    errs = validate_record(body)
    if errs:
        return error(handler, 400, "; ".join(errs))

    rid = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        "INSERT INTO financial_records (id, amount, type, category, date, notes, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rid, body["amount"], body["type"], body["category"].strip(), body["date"], body.get("notes"), current["sub"]),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, amount, type, category, date, notes, created_by, created_at "
        "FROM financial_records WHERE id = ?", (rid,)
    ).fetchone()
    conn.close()
    json_response(handler, 201, row_to_dict(row))


def update_record(handler, params, query):
    current, denied = require_auth(handler, "analyst", "admin")
    if denied:
        return
    body = parse_body(handler)

    if not body:
        return error(handler, 400, "Request body is empty")

    errs = validate_record_update(body)
    if errs:
        return error(handler, 400, "; ".join(errs))

    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM financial_records WHERE id = ? AND is_deleted = 0", (params["record_id"],)
    ).fetchone()
    if not row:
        conn.close()
        return error(handler, 404, "Record not found")

    # analysts can only edit records they created
    if current["role"] == "analyst" and row["created_by"] != current["sub"]:
        conn.close()
        return error(handler, 403, "Analysts can only edit records they created")

    allowed = ["amount", "type", "category", "date", "notes"]
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        conn.close()
        return error(handler, 400, f"No valid fields to update. Allowed: {', '.join(allowed)}")

    updates["updated_at"] = "datetime('now')"
    set_clause = ", ".join(
        f"{k} = datetime('now')" if k == "updated_at" else f"{k} = ?"
        for k in updates
    )
    values = [v for k, v in updates.items() if k != "updated_at"]
    conn.execute(
        f"UPDATE financial_records SET {set_clause} WHERE id = ?",
        (*values, params["record_id"]),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT id, amount, type, category, date, notes, created_by, created_at "
        "FROM financial_records WHERE id = ?", (params["record_id"],)
    ).fetchone()
    conn.close()
    json_response(handler, 200, row_to_dict(updated))


def delete_record(handler, params, query):
    current, denied = require_auth(handler, "admin")
    if denied:
        return
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM financial_records WHERE id = ? AND is_deleted = 0", (params["record_id"],)
    ).fetchone()
    if not row:
        conn.close()
        return error(handler, 404, "Record not found")
    conn.execute("UPDATE financial_records SET is_deleted = 1 WHERE id = ?", (params["record_id"],))
    conn.commit()
    conn.close()
    json_response(handler, 200, {"message": "Record deleted"})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard_summary(handler, params, query):
    current, denied = require_auth(handler, "viewer", "analyst", "admin")
    if denied:
        return
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS total_income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS total_expenses,
            COUNT(*) AS record_count
        FROM financial_records WHERE is_deleted = 0
    """).fetchone()
    conn.close()
    income = row["total_income"]
    expenses = row["total_expenses"]
    json_response(handler, 200, {
        "total_income":    round(income, 2),
        "total_expenses":  round(expenses, 2),
        "net_balance":     round(income - expenses, 2),
        "record_count":    row["record_count"],
    })


def dashboard_by_category(handler, params, query):
    current, denied = require_auth(handler, "analyst", "admin")
    if denied:
        return
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            category,
            COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expenses
        FROM financial_records WHERE is_deleted = 0
        GROUP BY category
        ORDER BY (income + expenses) DESC
    """).fetchall()
    conn.close()
    json_response(handler, 200, [
        {
            "category": r["category"],
            "income":   round(r["income"], 2),
            "expenses": round(r["expenses"], 2),
            "net":      round(r["income"] - r["expenses"], 2),
        }
        for r in rows
    ])


def dashboard_trends(handler, params, query):
    current, denied = require_auth(handler, "analyst", "admin")
    if denied:
        return

    period = query.get("period", ["monthly"])[0]
    if period == "monthly":
        group_expr = "strftime('%Y-%m', date)"
        label = "month"
    elif period == "weekly":
        group_expr = "strftime('%Y-W%W', date)"
        label = "week"
    else:
        return error(handler, 400, "'period' must be 'monthly' or 'weekly'")

    conn = get_connection()
    rows = conn.execute(f"""
        SELECT
            {group_expr} AS period,
            COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expenses
        FROM financial_records WHERE is_deleted = 0
        GROUP BY period ORDER BY period ASC
    """).fetchall()
    conn.close()
    json_response(handler, 200, [
        {
            label:      r["period"],
            "income":   round(r["income"], 2),
            "expenses": round(r["expenses"], 2),
            "net":      round(r["income"] - r["expenses"], 2),
        }
        for r in rows
    ])


def dashboard_recent(handler, params, query):
    current, denied = require_auth(handler, "viewer", "analyst", "admin")
    if denied:
        return
    try:
        limit = min(50, max(1, int(query.get("limit", [10])[0])))
    except (ValueError, IndexError):
        limit = 10
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, amount, type, category, date, notes, created_at
        FROM financial_records WHERE is_deleted = 0
        ORDER BY date DESC, created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    json_response(handler, 200, [row_to_dict(r) for r in rows])


def dashboard_income_vs_expense(handler, params, query):
    current, denied = require_auth(handler, "viewer", "analyst", "admin")
    if denied:
        return
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expenses
        FROM financial_records WHERE is_deleted = 0
    """).fetchone()
    conn.close()
    income = row["income"]
    expenses = row["expenses"]
    total = income + expenses
    json_response(handler, 200, {
        "income":       round(income, 2),
        "expenses":     round(expenses, 2),
        "income_pct":   round(income / total * 100, 1) if total else 0,
        "expense_pct":  round(expenses / total * 100, 1) if total else 0,
    })
