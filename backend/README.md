# FoodLoop School backend

The backend uses Python's standard library and SQLite; no package installation is required. Buyer and seller accounts can both publish listings and place orders. Admin accounts are provisioned separately.

## Run locally

From the project root:

```powershell
python backend\server.py --create-admin
python backend\server.py
```

The admin setup command securely prompts for the initial admin email and password. Choose a password with at least 12 characters. The password is PBKDF2-HMAC-SHA256 hashed and is never returned by the API or shown in the admin account list.

Open `http://127.0.0.1:8000`. The app database is created at `backend\foodloop.sqlite3`. Set `FOODLOOP_DB` to use another database path. To listen on another address or port, set `FOODLOOP_HOST` and `FOODLOOP_PORT`. For HTTPS deployments, set `FOODLOOP_COOKIE_SECURE=1` and terminate TLS at a trusted reverse proxy.

## API overview

- `POST /api/auth/register` — create buyer or seller account (`name`, `email`, `password`, `role`).
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` — login/session lifecycle. Sessions use HttpOnly, SameSite cookies.
- `GET /api/products` — approved listings; `GET /api/products?mine=true` — seller's listings.
- `POST /api/products` — seller creates a pending listing.
- `PATCH /api/products/{id}` — owner updates available stock.
- `GET /api/orders`, `POST /api/orders` — list or place a buyer order.
- `POST /api/orders/{id}/accept`, `/cancel`, `/advance` — seller order workflow.
- `GET /api/admin/users`, `PATCH /api/admin/users/{id}` — admin account management. Passwords are never exposed.
- `PATCH /api/admin/users/{id}/status` — suspend/activate an account and revoke its sessions when suspended.
- `PATCH /api/admin/users/{id}/password` — set a new password without revealing the old one; revoke existing sessions.
- `GET /api/admin/products`, `PATCH /api/admin/products/{id}/approve`, `DELETE /api/admin/products/{id}` — moderation.
- `GET /api/stats` — completed sales only; includes monthly totals, categories and partner leaderboard.

Order acceptance uses a SQLite `BEGIN IMMEDIATE` transaction and conditional stock update to prevent concurrent over-selling. Cancelling a reserved order restores stock in the same transaction. SQLite is suitable for a local/demo deployment; a multi-instance production deployment should use a shared transactional database and HTTPS.
