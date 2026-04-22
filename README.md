# flask-api-pos

A small **Flask REST API** for a point-of-sale style workflow: users register and log in, manage **products**, record **sales**, and store a **payment** row for each sale. Authentication uses **JWT** (JSON Web Tokens). Data is persisted with **SQLAlchemy**; this project is configured for **PostgreSQL** via environment variables.

---

## Features

- **Core API routes**: `/register`, `/login`, `/products`, `/sales` (no separate `/payments` route; payments are created when you POST a sale). **`GET /`** returns a small JSON welcome payload (useful for browsers and ngrok checks).
- **JWT**: Access tokens issued on register and login; protected routes require `Authorization: Bearer <token>`.
- **Password storage**: Plain passwords are never stored; Werkzeug hashes them before saving.
- **Multi-tenant data**: Products and sales are scoped to the authenticated user (by user id in the JWT).
- **Blueprints**: Auth, products, and sales are split into Flask blueprints and wired up in the app factory.
- **Configuration**: Secrets and database URL live in **`.env`** (not committed). Use **`.env.example`** as a template.

---

## Tech stack

| Piece | Role |
|--------|------|
| [Flask](https://flask.palletsprojects.com/) | Web framework |
| [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) | ORM and database session |
| [Flask-JWT-Extended](https://flask-jwt-extended.readthedocs.io/) | JWT creation and validation |
| [Werkzeug](https://werkzeug.palletsprojects.com/) | Password hashing |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Load `.env` into environment variables |
| [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) | PostgreSQL driver for SQLAlchemy |
| [requests](https://pypi.org/project/requests/) | HTTP client for Safaricom M-Pesa APIs |

---

## Project layout

```
flask-api-pos/
├── .env                 # Your secrets (create locally; gitignored)
├── .env.example         # Template for required variables (safe to commit)
├── .gitignore
├── README.md
├── requirements.txt
├── run.py               # Dev entry: creates app and runs Flask
└── app/
    ├── __init__.py      # create_app(), db, jwt, blueprint registration, db.create_all()
    ├── models.py        # User, Product, Sale, Payment
    ├── auth.py          # /register, /login
    ├── mpesa.py         # /mpesa/stk-push, /mpesa/stk-query, /mpesa/stk-callback
    ├── products.py      # /products
    └── sales.py         # /sales (creates Sale + Payment on POST)
```

The app uses the **application factory** pattern: `create_app()` builds the Flask instance, loads configuration, initializes extensions, imports models (so metadata is registered), registers blueprints, and creates database tables if they do not exist.

---

## Prerequisites

- **Python 3.10+** (3.12 is fine).
- **PostgreSQL** running and reachable from your machine, with a database created for this app.
- A Python **virtual environment** (recommended).

---

## Setup

### 1. Clone or copy the project

```powershell
cd path\to\flask-api-pos
```

### 2. Create and activate a virtual environment (example)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you already use a venv named `flask_pos`, activate it and run `pip install -r requirements.txt` there.

### 3. Configure environment variables

Copy the example file and edit values:

```powershell
copy .env.example .env
```

Set these in **`.env`** (all are **required**; the app will not start without them):

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session / signing (use a long random string) |
| `JWT_SECRET_KEY` | Separate secret used to sign JWTs (use another long random string) |
| `SQLALCHEMY_DATABASE_URI` | SQLAlchemy database URL, e.g. `postgresql://USER:PASSWORD@HOST:5432/DATABASE` |

M-Pesa-specific variables (required when using M-Pesa endpoints):

| Variable | Purpose |
|----------|---------|
| `MPESA_CONSUMER_KEY` | Safaricom app consumer key |
| `MPESA_CONSUMER_SECRET` | Safaricom app consumer secret |
| `MPESA_SHORTCODE` | PayBill/Till short code |
| `MPESA_PASS_KEY` | Daraja passkey |
| `MPESA_CALLBACK_URL` | Public callback URL, e.g. ngrok `/mpesa/stk-callback` |
| `MPESA_ACCESS_TOKEN_URL` | Optional override (sandbox default is already set) |
| `MPESA_STK_PUSH_URL` | Optional override (sandbox default is already set) |
| `MPESA_STK_QUERY_URL` | Optional override (sandbox default is already set) |

Example URI shape:

```text
postgresql://myuser:mypassword@localhost:5432/flask_api_pos
```

Ensure the PostgreSQL user can connect and that the database exists (`CREATE DATABASE flask_api_pos;` or your chosen name).

### 4. Run the application

```powershell
python run.py
```

By default the development server listens on `http://127.0.0.1:5000/`.

On startup, `create_app()` runs **`db.create_all()`**, which creates tables if they are missing. This is convenient for development; for production you would typically use **Alembic** (or another migration tool) instead of relying only on `create_all()`.

---

## Data model

Relationships:

```text
User ──< Product ──< Sale ──< Payment
```

| Table | SQLAlchemy class | Main columns |
|-------|------------------|--------------|
| `users` | `User` | `id`, `full_name`, `email` (unique), `password` (hashed), `created_at` |
| `products` | `Product` | `id`, `user_id` → `users.id`, `name`, `amount`, `created_at` |
| `sales` | `Sale` | `id`, `product_id` → `products.id`, `created_at` |
| `payments` | `Payment` | `id`, `sale_id` → `sales.id`, `trans_code`, `trans_amount`, `phone_paid`, `created_at` |

- **Amounts** use `Numeric(12, 2)` in the database; JSON responses expose them as strings to preserve decimal precision.
- **`created_at`** is set in UTC (timezone-aware `datetime`).

---

## Authentication (JWT)

1. Call **POST `/register`** or **POST `/login`** with JSON credentials.
2. Read **`access_token`** from the JSON response.
3. For **GET/POST `/products`** and **GET/POST `/sales`**, send:

   ```http
   Authorization: Bearer <access_token>
   ```

The JWT **subject** is the user id as a string (`str(user.id)`). The API resolves the current user from that id for product and sale queries.

---

## API reference

Base URL in development: `http://127.0.0.1:5000`

All bodies are **`Content-Type: application/json`** unless noted.

### GET `/`

Public. No auth. Returns JSON confirming the service is up and lists the main route paths. Use this when testing **ngrok** or opening the base URL in a browser.

**Response `200`:** JSON with `service`, `ok`, and `routes`.

### POST `/register`

Public. Creates a user and returns a JWT.

**Request body:**

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "password": "your-secure-password"
}
```

**Responses:**

- `201` — User created.

  ```json
  {
    "access_token": "<jwt>",
    "token_type": "Bearer",
    "user": {
      "id": 1,
      "full_name": "Ada Lovelace",
      "email": "ada@example.com"
    }
  }
  ```

- `400` — Missing fields.
- `409` — Email already registered.

Other HTTP methods on `/register` return **405 Method Not Allowed** (only POST is implemented).

---

### POST `/login`

Public. Validates credentials and returns a JWT.

**Request body:**

```json
{
  "email": "ada@example.com",
  "password": "your-secure-password"
}
```

**Responses:**

- `200` — Success.

  ```json
  {
    "access_token": "<jwt>",
    "token_type": "Bearer"
  }
  ```

- `400` — Missing email or password.
- `401` — Invalid email or password.

Only **POST** is allowed (405 otherwise).

---

### GET `/products`

**Authentication required.**

Returns all products owned by the current user.

**Response `200`:**

```json
[
  {
    "id": 1,
    "user_id": 1,
    "name": "Coffee",
    "amount": "3.50",
    "created_at": "2026-04-13T12:00:00+00:00"
  }
]
```

---

### POST `/products`

**Authentication required.**

Creates a product for the current user.

**Request body:**

```json
{
  "name": "Coffee",
  "amount": 3.5
}
```

(`amount` may be sent as a number or string; it is parsed as a decimal.)

**Responses:**

- `201` — Created; body is one product object (same shape as in GET).
- `400` — Validation error (e.g. missing `name` or `amount`, or invalid amount).

---

### GET `/sales`

**Authentication required.**

Lists sales for products that belong to the current user. Each item includes a nested **`payment`** object when present (this API creates one payment per sale on POST).

**Response `200`:**

```json
[
  {
    "id": 1,
    "product_id": 1,
    "created_at": "2026-04-13T12:30:00+00:00",
    "payment": {
      "id": 1,
      "sale_id": 1,
      "trans_code": "TX-1001",
      "trans_amount": "3.50",
      "phone_paid": "+15551234567",
      "created_at": "2026-04-13T12:30:00+00:00"
    }
  }
]
```

---

### POST `/sales`

**Authentication required.**

Creates a **sale** for one of your products and a **payment** row in the same transaction.

**Request body:**

```json
{
  "product_id": 1,
  "trans_code": "TX-1001",
  "trans_amount": "3.50",
  "phone_paid": "+15551234567"
}
```

**Responses:**

- `201` — Created; body is one sale object (same shape as in GET list items).
- `400` — Missing or invalid fields.
- `404` — Product not found or not owned by you.

---

### POST `/mpesa/stk-push`

**Authentication required.**

Initiates an M-Pesa STK push using your configured Daraja credentials.

**Request body:**

```json
{
  "phone_number": "2547XXXXXXXX",
  "amount": 1,
  "account_reference": "Order-1001",
  "transaction_desc": "POS payment"
}
```

Only `phone_number` and `amount` are required.

**Responses:**

- `200` — Forwards Safaricom STK push response.
- `400` — Validation error.
- `500` — Missing M-Pesa env configuration.
- `502` — Upstream Safaricom request failed.

---

### POST `/mpesa/stk-query`

**Authentication required.**

Queries STK push status by checkout request id.

**Request body:**

```json
{
  "checkout_request_id": "ws_CO_XXXXXXXXXXXX"
}
```

**Responses:**

- `200` — Forwards Safaricom query response.
- `400` — Validation error.
- `500` — Missing M-Pesa env configuration.
- `502` — Upstream Safaricom request failed.

---

### POST `/mpesa/stk-callback`

**Public endpoint** used by Safaricom to post STK callback payloads.

Current behavior: acknowledges payload with `{"ok": true, ...}`.  
Recommended next step: persist callback details and reconcile with local `payments`.

---

## HTTP methods summary

| Path | Methods |
|------|---------|
| `/` | GET only (health / welcome JSON) |
| `/register` | POST only |
| `/login` | POST only |
| `/products` | GET, POST |
| `/sales` | GET, POST |
| `/mpesa/stk-push` | POST (JWT) |
| `/mpesa/stk-query` | POST (JWT) |
| `/mpesa/stk-callback` | POST (public) |

Using an unsupported method (for example **GET** `/login`) returns **405**.

---

## Security and configuration notes

- **Never commit `.env`**. It is listed in `.gitignore`. Commit **`.env.example`** only, with placeholders.
- **Rotate secrets** if they were ever committed or shared.
- **`SECRET_KEY`** and **`JWT_SECRET_KEY`** should be long, random, and distinct in production.
- The app **does not** implement refresh tokens, OAuth, or role-based access control; it is a minimal class-style API.

---

## Exposing the API with ngrok

Use this when you want Postman, a phone, or another machine to reach your laptop over the internet.

1. **Fix the database first** — If `python run.py` crashes on startup (PostgreSQL password, etc.), ngrok will only show errors or **502 Bad Gateway** because nothing is listening.

2. **Start Flask** (from the project folder, venv activated):

   ```powershell
   python run.py
   ```

   Default port is **5000** (override with env var `PORT`).

3. **Point ngrok at the same port** (in another terminal):

   ```powershell
   ngrok http 5000
   ```

   If you changed `PORT`, use that number instead (e.g. `ngrok http 8080`).

4. **Confirm the tunnel** — In the terminal where ngrok is running, you should see a line like `Forwarding https://xxxx.ngrok-free.dev -> http://localhost:5000`. If that window is closed, the public URL stops working. **Restarting ngrok** often gives a **new** URL; update bookmarks and Postman’s `base_url`.

5. **Port must match Flask** — `ngrok http 5000` only works if Flask is listening on **5000**. If you set `PORT=8000` in the environment, run `ngrok http 8000` instead.

6. **Open the ngrok inspector** — Visit `http://127.0.0.1:4040` on your machine to see whether requests hit ngrok and what error (502 = nothing listening on the forwarded port).

7. **Test the base URL** — **`GET https://xxxx.ngrok-free.dev/`** should return JSON (service name and route list). If that fails but `http://127.0.0.1:5000/` works locally, the problem is ngrok (wrong port, tunnel offline, or old URL).

8. **ngrok free “browser warning”** — For **Postman**, **curl**, or scripts, add this header so requests are not blocked by the interstitial page:

   | Header | Value |
   |--------|--------|
   | `ngrok-skip-browser-warning` | `true` |

   In Postman: request or collection **Headers** → add the row above. Browsers may still show a warning page until you click through once.

9. **Update Postman** — Set the collection variable `base_url` to your ngrok URL **without** a trailing slash, e.g. `https://xxxx.ngrok-free.dev`.

---

## Troubleshooting

- **`RuntimeError: Missing required environment variables`** — Create `.env` from `.env.example` and set all three variables.
- **PostgreSQL connection errors** — Check host, port, database name, user, password, and that PostgreSQL accepts TCP connections from your client.
- **401 on protected routes** — Send the `Authorization: Bearer` header; ensure the token has not expired (default JWT lifetime is set by Flask-JWT-Extended; see its docs to change expiration).

---

## License

Use and modify for your class or project as needed; add a license file if you redistribute the code.
