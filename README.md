# Finance Dashboard Backend

A REST API for a finance dashboard system with role-based access control. Built with Python's standard library — no external dependencies, just `python3 main.py` and it runs.

---

## Why no framework?

I decided against FastAPI or Flask here because the assignment is for an internship evaluation and I wanted to show I understand what's actually happening underneath — routing, HTTP parsing, token verification — rather than just wiring framework decorators together. The tradeoff is more boilerplate in `server.py`, but every piece of it is readable and intentional.

If this were a real production project I'd use FastAPI without hesitation. But for this, vanilla Python felt more honest.

---

## Setup

Requires Python 3.10+ (uses `dict | None` type hints). No installs needed.

```bash
git clone <repo-url>
cd finance-backend
python3 main.py
```

Server starts at `http://localhost:8000`. On first run it creates `finance.db` and seeds three test users plus 15 sample records.

To use a different port:
```bash
PORT=9000 python3 main.py
```

---

## Test users (pre-seeded)

| Email | Password | Role |
|---|---|---|
| admin@test.com | password123 | admin |
| analyst@test.com | password123 | analyst |
| viewer@test.com | password123 | viewer |

---

## Project structure

```
finance-backend/
├── main.py          # entry point, route table, HTTP server
├── handlers.py      # all request handlers (auth, users, records, dashboard)
├── database.py      # SQLite setup, seed data, password hashing
├── auth.py          # JWT creation/verification (stdlib only)
├── server.py        # routing engine, response helpers
├── validators.py    # input validation functions
└── finance.db       # created on first run
```

---

## API reference

### Authentication

All endpoints except `POST /auth/login` require a `Bearer` token in the `Authorization` header.

**Login**
```
POST /auth/login
Body: { "email": "...", "password": "..." }
Returns: { "access_token": "...", "token_type": "bearer", "role": "..." }
```

---

### Users  *(admin only except /users/me)*

| Method | Path | Who |
|---|---|---|
| GET | `/users` | admin |
| POST | `/users` | admin |
| GET | `/users/me` | any logged-in user |
| GET | `/users/{id}` | admin |
| PATCH | `/users/{id}` | admin |
| DELETE | `/users/{id}` | admin (soft deactivate) |

**Create user**
```
POST /users
Body: { "email": "...", "password": "...", "role": "viewer|analyst|admin" }
```

**Update user**
```
PATCH /users/{id}
Body: { "role": "analyst", "is_active": true }
```

---

### Financial Records

| Method | Path | Who |
|---|---|---|
| GET | `/records` | viewer, analyst, admin |
| GET | `/records/{id}` | viewer, analyst, admin |
| POST | `/records` | analyst, admin |
| PATCH | `/records/{id}` | analyst (own records only), admin |
| DELETE | `/records/{id}` | admin (soft delete) |

**Filter records**
```
GET /records?type=income&category=Rent&date_from=2026-01-01&date_to=2026-03-31&page=1&limit=20
```

All filters are optional and combinable. Pagination defaults to page 1, 20 per page, max 100.

**Create record**
```
POST /records
Body: {
  "amount": 5000.00,
  "type": "income",
  "category": "Freelance",
  "date": "2026-04-01",
  "notes": "Optional"
}
```

---

### Dashboard

| Endpoint | Who | What it returns |
|---|---|---|
| GET `/dashboard/summary` | any | total income, expenses, net balance, count |
| GET `/dashboard/by-category` | analyst, admin | income/expense breakdown per category |
| GET `/dashboard/trends?period=monthly` | analyst, admin | monthly or weekly totals |
| GET `/dashboard/recent?limit=10` | any | most recent N records |
| GET `/dashboard/income-vs-expense` | any | income vs expense with percentages |

---

## Role permissions summary

| Action | viewer | analyst | admin |
|---|---|---|---|
| View records | ✓ | ✓ | ✓ |
| View dashboard summary | ✓ | ✓ | ✓ |
| Category breakdown & trends | — | ✓ | ✓ |
| Create records | — | ✓ | ✓ |
| Edit records | — | own only | ✓ |
| Delete records | — | — | ✓ |
| Manage users | — | — | ✓ |

---

## Design decisions and tradeoffs

**Password hashing**: I used SHA-256 (stdlib) instead of bcrypt because bcrypt isn't available without pip. In a real system bcrypt or argon2 is the right call — they're slow by design, which matters for offline attacks. SHA-256 is fast, which is a real weakness. I've noted this in the code.

**JWT implementation**: Built from scratch using hmac + hashlib. Standard JWT libraries would be cleaner, but again — no pip. The token structure (header.payload.signature) follows the JWT spec and the signature verification uses `hmac.compare_digest` to avoid timing attacks.

**Soft deletes everywhere**: Records marked `is_deleted = 1` stay in the database. Deactivated users stay too. This is intentional — financial data shouldn't disappear, and it makes auditing possible. Nothing actually gets removed.

**Analyst edit restriction**: Analysts can create and edit records but only their own. Admins can edit anything. I made this call because it seemed like the right default for a finance system where you'd want records tied to whoever entered them.

**SQLite WAL mode**: Enabled WAL (Write-Ahead Logging) so reads don't block writes. Probably overkill for a single-file SQLite DB but it's a good habit and costs nothing.

**No pagination on dashboard endpoints**: Dashboard queries aggregate the full dataset by design — you want the real totals, not a page of them. Records listing has full pagination.

---

## Assumptions I made

- "Deactivating" a user is the right model instead of hard deleting — the assignment said "manage user status" so I went with `is_active` rather than DELETE.
- Viewers should see the summary and recent activity but not the detailed category breakdown — that felt like analyst-level analysis.
- The `notes` field on records is optional. Everything else is required.
- Dates are stored as `TEXT` in `YYYY-MM-DD` format. SQLite's date functions work fine with this format.
- I didn't implement search (substring match on category is there though) or rate limiting — those felt like the right ones to skip given the time constraint.

---

## Example curl flow

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Check dashboard summary
curl -s http://localhost:8000/dashboard/summary \
  -H "Authorization: Bearer $TOKEN"

# 3. Create a record
curl -s -X POST http://localhost:8000/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 2500, "type": "expense", "category": "Marketing", "date": "2026-04-05"}'

# 4. Filter records by type
curl -s "http://localhost:8000/records?type=expense&page=1&limit=5" \
  -H "Authorization: Bearer $TOKEN"

# 5. Monthly trends
curl -s "http://localhost:8000/dashboard/trends?period=monthly" \
  -H "Authorization: Bearer $TOKEN"
```
