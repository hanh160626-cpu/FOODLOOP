#!/usr/bin/env python3
"""FoodLoop School API and static web server; uses only the Python standard library."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import mimetypes
import os
import secrets
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from http.cookies import SimpleCookie


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("FOODLOOP_DB", ROOT / "backend" / "foodloop.sqlite3"))
PBKDF2_ITERATIONS = 310_000
SESSION_DAYS = 7
ROLES = {"buyer": "Người mua", "seller": "Người bán", "admin": "Quản trị viên"}
ORDER_STATES = {
    "pending": "Chờ xác nhận",
    "confirmed": "Đã xác nhận",
    "preparing": "Đang chuẩn bị",
    "shipping": "Đang giao",
    "completed": "Hoàn thành",
    "cancelled": "Đã hủy",
}
PRODUCT_FIELDS = (
    "name", "category", "purpose", "description", "weight", "unit", "price",
    "stock", "packed", "expiry", "storage", "image", "place",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    return db


@contextmanager
def database():
    db = connect()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    with database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('buyer','seller','admin')),
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
                created_at TEXT NOT NULL,
                last_login TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                purpose TEXT NOT NULL CHECK(purpose IN ('human','animal')),
                description TEXT NOT NULL,
                weight REAL NOT NULL CHECK(weight > 0),
                unit TEXT NOT NULL,
                price INTEGER NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                packed TEXT NOT NULL,
                expiry TEXT NOT NULL,
                storage TEXT NOT NULL,
                image TEXT NOT NULL DEFAULT '',
                place TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected','inactive')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS products_status_created ON products(status, created_at);
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                buyer_id TEXT NOT NULL REFERENCES users(id),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_price INTEGER NOT NULL CHECK(unit_price >= 0),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','confirmed','preparing','shipping','completed','cancelled')),
                stock_reserved INTEGER NOT NULL DEFAULT 0 CHECK(stock_reserved IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS orders_buyer_created ON orders(buyer_id, created_at);
            CREATE INDEX IF NOT EXISTS orders_product_created ON orders(product_id, created_at);
            """
        )


def password_digest(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, digest_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    _, candidate = password_digest(password, salt)
    return hmac.compare_digest(candidate, digest_hex)


def public_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "email": row["email"],
        "role": row["role"], "roleLabel": ROLES[row["role"]],
        "status": row["status"], "createdAt": row["created_at"],
        "lastLogin": row["last_login"],
    }


def product_json(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "sellerId": row["seller_id"], "name": row["name"],
        "category": row["category"], "purpose": row["purpose"],
        "description": row["description"], "weight": row["weight"],
        "unit": row["unit"], "price": row["price"], "stock": row["stock"],
        "packed": row["packed"], "expiry": row["expiry"],
        "storage": row["storage"], "image": row["image"], "place": row["place"],
        "status": row["status"], "provider": row["seller_name"],
        "checked": ("Đã xác nhận thông tin" if row["status"] == "approved"
                    else "Chờ xác nhận thông tin" if row["status"] == "pending"
                    else row["status"]),
    }


def order_json(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "productId": row["product_id"],
        "productName": row["product_name"], "buyerId": row["buyer_id"],
        "buyer": row["buyer_name"], "sellerId": row["seller_id"],
        "seller": row["seller_name"], "qty": row["quantity"],
        "total": row["quantity"] * row["unit_price"],
        "status": ORDER_STATES[row["status"]],
        "statusCode": row["status"], "held": bool(row["stock_reserved"]),
        "created": row["created_at"][:10],
    }


def main() -> None:
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "--create-admin":
        import getpass

        email = input("Admin email: ").strip().lower()
        name = input("Admin name: ").strip() or "FoodLoop Admin"
        password = getpass.getpass("Admin password (at least 12 chars): ")
        if "@" not in email or len(password) < 12 or len(password) > 256:
            raise SystemExit("A valid email and a password between 12 and 256 characters are required.")
        salt, digest = password_digest(password)
        with database() as db:
            db.execute(
                """INSERT INTO users(id,name,email,password_hash,password_salt,role,status,created_at)
                   VALUES(?,?,?,?,?,'admin','active',?)
                   ON CONFLICT(email) DO UPDATE SET name=excluded.name,
                     password_hash=excluded.password_hash,password_salt=excluded.password_salt,
                     role='admin',status='active'""",
                (str(uuid.uuid4()), name, email, digest, salt, utc_now()),
            )
            db.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE email=?)", (email,))
        print("Administrator account created or updated. The password is never stored in plaintext.")
        return
    host = os.environ.get("FOODLOOP_HOST", "127.0.0.1")
    port = int(os.environ.get("FOODLOOP_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"FoodLoop running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping FoodLoop.")
    finally:
        server.server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = "FoodLoop/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def send_json(self, status: int, data: object) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' https: data: blob: 'unsafe-inline' 'unsafe-eval'")
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("Request body is too large.")
            value = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON request body.") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON request body must be an object.")
        return value

    def require_auth(self, db: sqlite3.Connection, roles: set[str] | None = None) -> sqlite3.Row:
        token = self.session_token()
        if not token:
            raise PermissionError("Đăng nhập để tiếp tục.")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = db.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>?""", (token_hash, utc_now())
        ).fetchone()
        if not row or row["status"] != "active":
            raise PermissionError("Phiên đăng nhập không hợp lệ hoặc tài khoản đã bị khóa.")
        if roles and row["role"] not in roles:
            raise PermissionError("Bạn không có quyền thực hiện thao tác này.")
        return row

    def session_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        return cookies["foodloop_session"].value if "foodloop_session" in cookies else ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.serve_static(parsed.path)
            return
        try:
            with database() as db:
                self.handle_get(db, parsed.path, parse_qs(parsed.query))
        except PermissionError as exc:
            self.send_json(401 if "Đăng nhập" in str(exc) or "Phiên" in str(exc) else 403, {"error": str(exc)})
        except Exception as exc:
            print(f"GET {parsed.path} failed: {exc}")
            self.send_json(500, {"error": "Lỗi máy chủ nội bộ."})

    def handle_get(self, db: sqlite3.Connection, path: str, query: dict) -> None:
        if path == "/api/health":
            self.send_json(200, {"ok": True, "service": "foodloop"})
        elif path == "/api/auth/me":
            try:
                self.send_json(200, {"user": public_user(self.require_auth(db))})
            except PermissionError:
                self.send_json(200, {"user": None})
        elif path == "/api/products":
            if query.get("mine") == ["true"]:
                user = self.require_auth(db, {"buyer", "seller", "admin"})
                rows = db.execute(
                        """SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id
                       WHERE p.seller_id=? ORDER BY p.created_at DESC""", (user["id"],)
                ).fetchall()
            elif query.get("all") == ["true"]:
                self.require_auth(db, {"admin"})
                rows = db.execute(
                        "SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id ORDER BY p.created_at DESC"
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id
                       WHERE p.status='approved' AND p.stock>0 ORDER BY p.created_at DESC"""
                ).fetchall()
            self.send_json(200, {"products": [product_json(row) for row in rows]})
        elif path.startswith("/api/products/"):
            product_id = unquote(path.rsplit("/", 1)[-1])
            row = db.execute(
                """SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id
                   WHERE p.id=?""",
                (product_id,),
            ).fetchone()
            if row and row["status"] != "approved":
                user = self.require_auth(db, {"buyer", "seller", "admin"})
                if user["role"] != "admin" and row["seller_id"] != user["id"]:
                    row = None
            if not row:
                self.send_json(404, {"error": "Không tìm thấy lô hàng."})
            else:
                self.send_json(200, {"product": product_json(row)})
        elif path == "/api/orders":
            user = self.require_auth(db)
            if user["role"] == "admin":
                rows = db.execute(self.order_select() + " ORDER BY o.created_at DESC").fetchall()
            else:
                rows = db.execute(
                    self.order_select() + " WHERE p.seller_id=? OR o.buyer_id=? ORDER BY o.created_at DESC",
                    (user["id"], user["id"]),
                ).fetchall()
            self.send_json(200, {"orders": [order_json(row) for row in rows]})
        elif path == "/api/admin/users":
            self.require_auth(db, {"admin"})
            users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            self.send_json(200, {"users": [public_user(row) for row in users]})
        elif path == "/api/admin/products":
            self.require_auth(db, {"admin"})
            rows = db.execute(
                """SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id
                   ORDER BY p.created_at DESC"""
            ).fetchall()
            self.send_json(200, {"products": [product_json(row) for row in rows]})
        elif path == "/api/stats":
            self.stats(db)
        else:
            self.send_json(404, {"error": "Không tìm thấy API."})

    @staticmethod
    def order_select() -> str:
        return """SELECT o.*,p.name product_name,p.seller_id,s.name seller_name,b.name buyer_name
                  FROM orders o JOIN products p ON p.id=o.product_id
                  JOIN users s ON s.id=p.seller_id JOIN users b ON b.id=o.buyer_id"""

    def stats(self, db: sqlite3.Connection) -> None:
        completed = db.execute(
            """SELECT COUNT(*) orders, COALESCE(SUM(o.quantity*p.weight),0) kg,
                      COALESCE(SUM(o.quantity*o.unit_price),0) value
               FROM orders o JOIN products p ON p.id=o.product_id WHERE o.status='completed'"""
        ).fetchone()
        partners = db.execute(
            """SELECT COUNT(DISTINCT p.seller_id) FROM products p
               JOIN users u ON u.id=p.seller_id WHERE u.status='active'"""
        ).fetchone()[0]
        monthly = db.execute(
            """SELECT substr(o.created_at,1,7) month, SUM(o.quantity*p.weight) kg,
                      COUNT(*) orders, SUM(o.quantity*o.unit_price) value
               FROM orders o JOIN products p ON p.id=o.product_id
               WHERE o.status='completed' GROUP BY substr(o.created_at,1,7) ORDER BY month"""
        ).fetchall()
        groups = db.execute(
            """SELECT p.category, SUM(o.quantity*p.weight) kg FROM orders o
               JOIN products p ON p.id=o.product_id WHERE o.status='completed'
               GROUP BY p.category ORDER BY kg DESC"""
        ).fetchall()
        leaderboard = db.execute(
            """SELECT u.id,u.name,SUM(o.quantity*p.weight) kg,COUNT(*) orders
               FROM orders o JOIN products p ON p.id=o.product_id JOIN users u ON u.id=p.seller_id
               WHERE o.status='completed' GROUP BY u.id,u.name ORDER BY kg DESC LIMIT 10"""
        ).fetchall()
        users_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.send_json(200, {
            "completed": {"orders": completed["orders"], "kg": completed["kg"], "value": completed["value"]},
            "partners": partners, "users": users_count,
            "monthly": [dict(row) for row in monthly], "categories": [dict(row) for row in groups],
            "leaderboard": [dict(row) for row in leaderboard],
        })

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self.read_json()
            with database() as db:
                self.handle_post(db, path, body)
        except PermissionError as exc:
            self.send_json(401 if "Đăng nhập" in str(exc) or "Phiên" in str(exc) else 403, {"error": str(exc)})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.IntegrityError as exc:
            self.send_json(409, {"error": "Dữ liệu bị trùng hoặc không hợp lệ."})
        except Exception as exc:
            print(f"POST {path} failed: {exc}")
            self.send_json(500, {"error": "Lỗi máy chủ nội bộ."})

    def handle_post(self, db: sqlite3.Connection, path: str, body: dict) -> None:
        if path == "/api/auth/register":
            name, email, password = (str(body.get(k, "")).strip() for k in ("name", "email", "password"))
            role = body.get("role", "buyer")
            if not name or len(name) > 120 or "@" not in email or len(password) < 10 or len(password) > 256:
                raise ValueError("Vui lòng nhập tên, email hợp lệ và mật khẩu ít nhất 10 ký tự.")
            if role not in ("buyer", "seller"):
                raise ValueError("Vai trò đăng ký chỉ có thể là người mua hoặc người bán.")
            salt, digest = password_digest(password)
            user_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO users(id,name,email,password_hash,password_salt,role,status,created_at,last_login)
                   VALUES(?,?,?,?,?,?, 'active',?,?)""",
                (user_id, name, email.lower(), digest, salt, role, utc_now(), utc_now()),
            )
            user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            self.create_session(db, user)
        elif path == "/api/auth/login":
            email = str(body.get("email", "")).strip().lower()
            password = str(body.get("password", ""))
            if len(password) > 256:
                self.send_json(401, {"error": "Email hoặc mật khẩu không chính xác."})
                return
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
                self.send_json(401, {"error": "Email hoặc mật khẩu không chính xác."})
                return
            if user["status"] != "active":
                self.send_json(403, {"error": "Tài khoản đang bị khóa. Vui lòng liên hệ quản trị viên."})
                return
            db.execute("UPDATE users SET last_login=? WHERE id=?", (utc_now(), user["id"]))
            user = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            self.create_session(db, user)
        elif path == "/api/auth/logout":
            token_hash = self._token_hash()
            if token_hash:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            self.send_json(200, {"ok": True})
        elif path == "/api/products":
            user = self.require_auth(db, {"buyer", "seller"})
            self.create_product(db, user, body)
        elif path == "/api/orders":
            user = self.require_auth(db, {"buyer", "seller"})
            product_id = str(body.get("productId", ""))
            try:
                quantity = int(body.get("quantity", 0))
            except (TypeError, ValueError):
                quantity = 0
            if quantity < 1 or quantity > 1_000_000_000:
                raise ValueError("Số lượng đặt phải là số nguyên dương.")
            product = db.execute(
                "SELECT * FROM products WHERE id=? AND status='approved' AND stock>=?",
                (product_id, quantity),
            ).fetchone()
            if not product:
                self.send_json(409, {"error": "Lô hàng không còn hoặc số lượng vượt tồn kho."})
                return
            if product["seller_id"] == user["id"]:
                self.send_json(403, {"error": "Không thể đặt hàng từ bài đăng của chính tài khoản này."})
                return
            order_id = "OD-" + uuid.uuid4().hex[:12].upper()
            now = utc_now()
            db.execute(
                """INSERT INTO orders(id,product_id,buyer_id,quantity,unit_price,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,'pending',?,?)""",
                (order_id, product_id, user["id"], quantity, product["price"], now, now),
            )
            row = db.execute(self.order_select() + " WHERE o.id=?", (order_id,)).fetchone()
            self.send_json(201, {"order": order_json(row)})
        elif path.startswith("/api/orders/") and path.endswith("/accept"):
            user = self.require_auth(db, {"buyer", "seller", "admin"})
            order_id = unquote(path.split("/")[-2])
            self.accept_order(db, user, order_id)
        elif path.startswith("/api/orders/") and path.endswith("/cancel"):
            user = self.require_auth(db)
            order_id = unquote(path.split("/")[-2])
            self.cancel_order(db, user, order_id)
        elif path.startswith("/api/orders/") and path.endswith("/advance"):
            user = self.require_auth(db, {"buyer", "seller", "admin"})
            order_id = unquote(path.split("/")[-2])
            self.advance_order(db, user, order_id)
        else:
            self.send_json(404, {"error": "Không tìm thấy API."})

    def create_session(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        token = secrets.token_urlsafe(36)
        expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        db.execute(
            "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), user["id"], expires, utc_now()),
        )
        payload = json.dumps({"expiresAt": expires, "user": public_user(user)}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        secure = "; Secure" if os.environ.get("FOODLOOP_COOKIE_SECURE") == "1" else ""
        self.send_header("Set-Cookie", f"foodloop_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_DAYS * 86400}{secure}")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def create_product(self, db: sqlite3.Connection, user: sqlite3.Row, body: dict) -> None:
        values = {key: body.get(key) for key in PRODUCT_FIELDS}
        required = ("name", "category", "purpose", "description", "weight", "unit",
                    "price", "stock", "packed", "expiry", "storage")
        if any(values.get(key) in (None, "") for key in required):
            raise ValueError("Vui lòng cung cấp đầy đủ thông tin sản phẩm.")
        if values["purpose"] not in ("human", "animal"):
            raise ValueError("Mục đích phải là human hoặc animal.")
        try:
            weight, price, stock = float(values["weight"]), int(values["price"]), int(values["stock"])
            packed, expiry = datetime.strptime(str(values["packed"]), "%Y-%m-%d"), datetime.strptime(str(values["expiry"]), "%Y-%m-%d")
        except (ValueError, TypeError) as exc:
            raise ValueError("Khối lượng, giá, số lượng hoặc ngày tháng không hợp lệ.") from exc
        if not math.isfinite(weight) or weight <= 0 or weight > 1_000_000 or price < 0 or price > 1_000_000_000_000 or stock < 1 or stock > 1_000_000_000 or expiry < packed:
            raise ValueError("Giá trị không hợp lệ hoặc hạn dùng trước ngày đóng gói.")
        product_id = "FL-" + uuid.uuid4().hex[:10].upper()
        now = utc_now()
        db.execute(
            """INSERT INTO products(id,seller_id,name,category,purpose,description,weight,unit,price,stock,
               packed,expiry,storage,image,place,status,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)""",
            (product_id, user["id"], values["name"], values["category"], values["purpose"],
             values["description"], weight, values["unit"], price, stock, values["packed"],
             values["expiry"], values["storage"], values.get("image") or "", values.get("place") or "",
             now, now),
        )
        self.send_json(201, {"id": product_id, "status": "pending", "message": "Bài đăng đang chờ quản trị viên duyệt."})

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self.read_json()
            with database() as db:
                if path.startswith("/api/products/"):
                    user = self.require_auth(db, {"buyer", "seller", "admin"})
                    product_id = unquote(path.rsplit("/", 1)[-1])
                    try:
                        stock = int(body.get("stock", -1))
                    except (TypeError, ValueError):
                        stock = -1
                    if stock < 0 or stock > 1_000_000_000:
                        raise ValueError("Số lượng tồn kho không hợp lệ.")
                    sql = "UPDATE products SET stock=?,updated_at=? WHERE id=?"
                    params: tuple = (stock, utc_now(), product_id)
                    if user["role"] != "admin":
                        sql += " AND seller_id=?"
                        params += (user["id"],)
                    updated = db.execute(sql, params)
                    self.send_json(200 if updated.rowcount else 404,
                                   {"ok": bool(updated.rowcount), "error": None if updated.rowcount else "Không tìm thấy lô hàng."})
                elif path.startswith("/api/admin/users/") and path.endswith("/status"):
                    user = self.require_auth(db, {"admin"})
                    user_id = unquote(path.split("/")[-2])
                    status = body.get("status")
                    if status not in ("active", "suspended"):
                        raise ValueError("Trạng thái tài khoản không hợp lệ.")
                    if user_id == user["id"] and status != "active":
                        raise ValueError("Không thể tự khóa tài khoản quản trị đang sử dụng.")
                    updated = db.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
                    if not updated.rowcount:
                        self.send_json(404, {"error": "Không tìm thấy tài khoản."})
                    else:
                        if status == "suspended":
                            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                        self.send_json(200, {"ok": True})
                elif path.startswith("/api/admin/users/") and path.endswith("/password"):
                    self.require_auth(db, {"admin"})
                    user_id = unquote(path.split("/")[-2])
                    password = str(body.get("newPassword", ""))
                    if len(password) < 10 or len(password) > 256:
                        raise ValueError("Mật khẩu mới phải có ít nhất 10 ký tự.")
                    salt, digest = password_digest(password)
                    updated = db.execute(
                        "UPDATE users SET password_hash=?,password_salt=? WHERE id=?",
                        (digest, salt, user_id),
                    )
                    if not updated.rowcount:
                        self.send_json(404, {"error": "Không tìm thấy tài khoản."})
                    else:
                        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                        self.send_json(200, {"ok": True})
                elif path.startswith("/api/admin/users/"):
                    user = self.require_auth(db, {"admin"})
                    user_id = unquote(path.rsplit("/", 1)[-1])
                    changes = []
                    values: list[str] = []
                    if "name" in body:
                        name = str(body["name"]).strip()
                        if not name or len(name) > 120:
                            raise ValueError("Tên tài khoản phải có từ 1 đến 120 ký tự.")
                        changes.append("name=?")
                        values.append(name)
                    if "role" in body:
                        role = body["role"]
                        if role not in ("buyer", "seller") or user_id == user["id"]:
                            raise ValueError("Không thể gán vai trò quản trị từ đây hoặc đổi vai trò của chính mình.")
                        changes.append("role=?")
                        values.append(role)
                    if not changes:
                        raise ValueError("Không có thông tin tài khoản cần cập nhật.")
                    values.append(user_id)
                    updated = db.execute(f"UPDATE users SET {','.join(changes)} WHERE id=?", values)
                    self.send_json(200 if updated.rowcount else 404,
                                   {"ok": bool(updated.rowcount), "error": None if updated.rowcount else "Không tìm thấy tài khoản."})
                elif path.startswith("/api/admin/products/") and path.endswith("/approve"):
                    self.require_auth(db, {"admin"})
                    product_id = unquote(path.split("/")[-2])
                    updated = db.execute(
                        "UPDATE products SET status='approved',updated_at=? WHERE id=? AND status='pending'",
                        (utc_now(), product_id),
                    )
                    self.send_json(200 if updated.rowcount else 404,
                                   {"ok": bool(updated.rowcount), "error": None if updated.rowcount else "Không tìm thấy bài chờ duyệt."})
                else:
                    self.send_json(404, {"error": "Không tìm thấy API."})
        except PermissionError as exc:
            self.send_json(401 if "Đăng nhập" in str(exc) or "Phiên" in str(exc) else 403, {"error": str(exc)})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            print(f"PATCH {path} failed: {exc}")
            self.send_json(500, {"error": "Lỗi máy chủ nội bộ."})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        try:
            with database() as db:
                self.require_auth(db, {"admin"})
                if path.startswith("/api/admin/products/"):
                    product_id = unquote(path.rsplit("/", 1)[-1])
                    db.execute("BEGIN IMMEDIATE")
                    found = db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
                    if not found:
                        db.rollback()
                        self.send_json(404, {"error": "Không tìm thấy bài đăng."})
                    else:
                        linked = db.execute("SELECT 1 FROM orders WHERE product_id=? LIMIT 1", (product_id,)).fetchone()
                        if linked:
                            db.execute("UPDATE products SET status='inactive',stock=0,updated_at=? WHERE id=?",
                                       (utc_now(), product_id))
                        else:
                            db.execute("DELETE FROM products WHERE id=?", (product_id,))
                        db.commit()
                        self.send_json(200, {"ok": True})
                else:
                    self.send_json(404, {"error": "Không tìm thấy API."})
        except PermissionError as exc:
            self.send_json(401 if "Đăng nhập" in str(exc) or "Phiên" in str(exc) else 403, {"error": str(exc)})
        except Exception as exc:
            print(f"DELETE {path} failed: {exc}")
            self.send_json(500, {"error": "Lỗi máy chủ nội bộ."})

    def accept_order(self, db: sqlite3.Connection, user: sqlite3.Row, order_id: str) -> None:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            self.order_select() + " WHERE o.id=?", (order_id,)
        ).fetchone()
        if not row or (user["role"] != "admin" and row["seller_id"] != user["id"]):
            db.rollback()
            self.send_json(404, {"error": "Không tìm thấy đơn hàng."})
            return
        if row["status"] != "pending":
            db.rollback()
            self.send_json(409, {"error": "Đơn hàng không còn chờ xác nhận."})
            return
        update = db.execute(
            "UPDATE products SET stock=stock-?,updated_at=? WHERE id=? AND stock>=? AND status='approved'",
            (row["quantity"], utc_now(), row["product_id"], row["quantity"]),
        )
        if not update.rowcount:
            db.rollback()
            self.send_json(409, {"error": "Tồn kho không đủ; đơn chưa được xác nhận."})
            return
        db.execute(
            "UPDATE orders SET status='confirmed',stock_reserved=1,updated_at=? WHERE id=? AND status='pending'",
            (utc_now(), order_id),
        )
        db.commit()
        result = db.execute(self.order_select() + " WHERE o.id=?", (order_id,)).fetchone()
        self.send_json(200, {"order": order_json(result)})

    def cancel_order(self, db: sqlite3.Connection, user: sqlite3.Row, order_id: str) -> None:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(self.order_select() + " WHERE o.id=?", (order_id,)).fetchone()
        allowed = row and (
            user["role"] == "admin" or row["buyer_id"] == user["id"]
            or row["seller_id"] == user["id"]
        )
        if not allowed:
            db.rollback()
            self.send_json(404, {"error": "Không tìm thấy đơn hàng."})
            return
        if row["status"] in ("completed", "cancelled", "shipping"):
            db.rollback()
            self.send_json(409, {"error": "Không thể hủy đơn ở trạng thái hiện tại."})
            return
        if row["stock_reserved"]:
            db.execute("UPDATE products SET stock=stock+?,updated_at=? WHERE id=?",
                       (row["quantity"], utc_now(), row["product_id"]))
        db.execute("UPDATE orders SET status='cancelled',stock_reserved=0,updated_at=? WHERE id=?",
                   (utc_now(), order_id))
        db.commit()
        self.send_json(200, {"ok": True, "stockRestored": bool(row["stock_reserved"])})

    def advance_order(self, db: sqlite3.Connection, user: sqlite3.Row, order_id: str) -> None:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(self.order_select() + " WHERE o.id=?", (order_id,)).fetchone()
        if not row or (user["role"] != "admin" and row["seller_id"] != user["id"]):
            db.rollback()
            self.send_json(404, {"error": "Không tìm thấy đơn hàng."})
            return
        next_states = {"confirmed": "preparing", "preparing": "shipping", "shipping": "completed"}
        next_status = next_states.get(row["status"])
        if not next_status:
            db.rollback()
            self.send_json(409, {"error": "Không thể chuyển trạng thái đơn hàng."})
            return
        db.execute("UPDATE orders SET status=?,stock_reserved=?,updated_at=? WHERE id=?",
                   (next_status, 0 if next_status == "completed" else row["stock_reserved"], utc_now(), order_id))
        db.commit()
        result = db.execute(self.order_select() + " WHERE o.id=?", (order_id,)).fetchone()
        self.send_json(200, {"order": order_json(result)})

    def end_headers(self) -> None:
        if self.command == "POST" and urlparse(self.path).path == "/api/auth/logout":
            secure = "; Secure" if os.environ.get("FOODLOOP_COOKIE_SECURE") == "1" else ""
            self.send_header("Set-Cookie", f"foodloop_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0{secure}")
        super().end_headers()

    def serve_static(self, requested: str) -> None:
        relative = unquote(requested).lstrip("/") or "index.html"
        target = (ROOT / relative).resolve()
        allowed_static = target.suffix.lower() in {".html", ".css", ".js"}
        features_asset = target.is_relative_to(ROOT / "features") and target.suffix.lower() == ".js"
        root_asset = target.parent == ROOT and allowed_static
        if not target.is_relative_to(ROOT) or not target.is_file() or not (root_asset or features_asset):
            self.send_error(404)
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in (".html", ".js", ".css"):
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    main()
