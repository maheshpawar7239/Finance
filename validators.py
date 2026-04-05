import re
from datetime import datetime


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validate_record(data: dict) -> list[str]:
    errors = []

    amount = data.get("amount")
    if amount is None:
        errors.append("'amount' is required")
    elif not isinstance(amount, (int, float)) or amount <= 0:
        errors.append("'amount' must be a positive number")

    rec_type = data.get("type")
    if not rec_type:
        errors.append("'type' is required")
    elif rec_type not in ("income", "expense"):
        errors.append("'type' must be 'income' or 'expense'")

    category = data.get("category", "").strip()
    if not category:
        errors.append("'category' is required and cannot be blank")

    date = data.get("date")
    if not date:
        errors.append("'date' is required (format: YYYY-MM-DD)")
    elif not validate_date(date):
        errors.append("'date' must be a valid date in YYYY-MM-DD format")

    return errors


def validate_record_update(data: dict) -> list[str]:
    errors = []

    if "amount" in data:
        amount = data["amount"]
        if not isinstance(amount, (int, float)) or amount <= 0:
            errors.append("'amount' must be a positive number")

    if "type" in data:
        if data["type"] not in ("income", "expense"):
            errors.append("'type' must be 'income' or 'expense'")

    if "category" in data:
        if not data["category"] or not str(data["category"]).strip():
            errors.append("'category' cannot be blank")

    if "date" in data:
        if not validate_date(data["date"]):
            errors.append("'date' must be a valid date in YYYY-MM-DD format")

    return errors


def validate_user_create(data: dict) -> list[str]:
    errors = []

    email = data.get("email", "")
    if not email:
        errors.append("'email' is required")
    elif not validate_email(email):
        errors.append("'email' is not a valid email address")

    password = data.get("password", "")
    if not password:
        errors.append("'password' is required")
    elif len(password) < 6:
        errors.append("'password' must be at least 6 characters")

    role = data.get("role", "viewer")
    if role not in ("viewer", "analyst", "admin"):
        errors.append("'role' must be one of: viewer, analyst, admin")

    return errors
