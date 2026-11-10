import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend import server


class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "test.sqlite3"
        server.init_db()
        salt, digest = server.password_digest("test-admin-password-very-long")
        with server.database() as db:
            db.execute(
                """INSERT INTO users(id,name,email,password_hash,password_salt,role,status,created_at)
                   VALUES('admin-1','Admin','admin@example.test',?,?,'admin','active',?)""",
                (digest, salt, server.utc_now()),
            )
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = cls.httpd.server_address

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)
        cls.temp_dir.cleanup()

    def request(self, method, path, body=None, cookie=None):
        connection = http.client.HTTPConnection(*self.base_url, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, payload, headers)
        response = connection.getresponse()
        raw = response.read()
        set_cookie = response.getheader("Set-Cookie")
        try:
            result = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = {}
        connection.close()
        return response.status, result, set_cookie

    def register(self, email, role):
        status, data, cookie = self.request("POST", "/api/auth/register", {
            "name": role.title(), "email": email, "password": "valid-password-123", "role": role,
        })
        self.assertEqual(status, 200, data)
        return cookie.split(";", 1)[0]

    def test_registration_login_moderation_orders_and_stats(self):
        status, _, _ = self.request("GET", "/backend/server.py")
        self.assertEqual(status, 404)
        status, _, _ = self.request("POST", "/api/auth/register", {
            "name": "Fake Admin", "email": "fake-admin@example.test",
            "password": "valid-password-123", "role": "admin",
        })
        self.assertEqual(status, 400)
        seller_cookie = self.register("seller@example.test", "seller")
        status, _, buyer_set_cookie = self.request("POST", "/api/auth/register", {
            "name": "Buyer", "email": "buyer@example.test",
            "password": "valid-password-123", "role": "buyer",
        })
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", buyer_set_cookie)
        buyer_cookie = buyer_set_cookie.split(";", 1)[0]
        admin_status, _, admin_cookie = self.request(
            "POST", "/api/auth/login",
            {"email": "admin@example.test", "password": "test-admin-password-very-long"},
        )
        self.assertEqual(admin_status, 200)
        admin_cookie = admin_cookie.split(";", 1)[0]

        status, account_data, _ = self.request("GET", "/api/admin/users", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertNotIn("password", json.dumps(account_data).lower())

        product = {
            "name": "Rau demo", "category": "Rau củ", "purpose": "human",
            "description": "Lô thử nghiệm", "weight": 1, "unit": "kg",
            "price": 1000, "stock": 2, "packed": "2026-11-10",
            "expiry": "2026-11-12", "storage": "Giữ mát",
        }
        status, listing, _ = self.request("POST", "/api/products", product, seller_cookie)
        self.assertEqual(status, 201)
        self.assertEqual(listing["status"], "pending")
        status, public_list, _ = self.request("GET", "/api/products")
        self.assertEqual(status, 200)
        self.assertEqual(public_list["products"], [])
        status, _, _ = self.request(
            "PATCH", f"/api/admin/products/{listing['id']}/approve", {}, admin_cookie,
        )
        self.assertEqual(status, 200)

        buyer_product = {**product, "name": "Buyer-owned item", "stock": 1}
        status, buyer_listing, _ = self.request("POST", "/api/products", buyer_product, buyer_cookie)
        self.assertEqual(status, 201)
        status, _, _ = self.request(
            "PATCH", f"/api/admin/products/{buyer_listing['id']}/approve", {}, admin_cookie,
        )
        self.assertEqual(status, 200)
        status, seller_order, _ = self.request("POST", "/api/orders", {
            "productId": buyer_listing["id"], "quantity": 1,
        }, seller_cookie)
        self.assertEqual(status, 201)
        status, _, _ = self.request(
            "POST", f"/api/orders/{seller_order['order']['id']}/accept", {}, buyer_cookie,
        )
        self.assertEqual(status, 200)
        status, _, _ = self.request(
            "POST", f"/api/orders/{seller_order['order']['id']}/cancel", {}, buyer_cookie,
        )
        self.assertEqual(status, 200)

        status, first, _ = self.request("POST", "/api/orders", {
            "productId": listing["id"], "quantity": 2,
        }, buyer_cookie)
        self.assertEqual(status, 201)
        status, second, _ = self.request("POST", "/api/orders", {
            "productId": listing["id"], "quantity": 2,
        }, buyer_cookie)
        self.assertEqual(status, 201)
        barrier = threading.Barrier(3)
        accept_results = {}

        def accept(name, order_id):
            barrier.wait()
            accept_results[name] = self.request(
                "POST", f"/api/orders/{order_id}/accept", {}, seller_cookie,
            )[0]

        workers = [
            threading.Thread(target=accept, args=("first", first["order"]["id"])),
            threading.Thread(target=accept, args=("second", second["order"]["id"])),
        ]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=5)
        self.assertEqual(sorted(accept_results.values()), [200, 409])
        accepted_id = first["order"]["id"] if accept_results["first"] == 200 else second["order"]["id"]
        status, _, _ = self.request(
            "POST", f"/api/orders/{accepted_id}/cancel", {}, seller_cookie,
        )
        self.assertEqual(status, 200)
        status, seller_products, _ = self.request("GET", "/api/products?mine=true", cookie=seller_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(seller_products["products"][0]["stock"], 2)

        status, third, _ = self.request("POST", "/api/orders", {
            "productId": listing["id"], "quantity": 2,
        }, buyer_cookie)
        self.assertEqual(status, 201)
        order_id = third["order"]["id"]
        self.request("POST", f"/api/orders/{order_id}/accept", {}, seller_cookie)
        self.request("POST", f"/api/orders/{order_id}/advance", {}, seller_cookie)
        self.request("POST", f"/api/orders/{order_id}/advance", {}, seller_cookie)
        self.request("POST", f"/api/orders/{order_id}/advance", {}, seller_cookie)
        status, stats, _ = self.request("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(stats["completed"]["orders"], 1)
        self.assertEqual(stats["completed"]["kg"], 2)

        seller_id = next(user["id"] for user in account_data["users"] if user["email"] == "seller@example.test")
        status, _, _ = self.request(
            "PATCH", f"/api/admin/users/{seller_id}/password",
            {"newPassword": "new-secure-password-456"}, admin_cookie,
        )
        self.assertEqual(status, 200)
        status, _, _ = self.request("POST", "/api/auth/login", {
            "email": "seller@example.test", "password": "valid-password-123",
        })
        self.assertEqual(status, 401)
        status, _, seller_new_cookie = self.request("POST", "/api/auth/login", {
            "email": "seller@example.test", "password": "new-secure-password-456",
        })
        self.assertEqual(status, 200)
        status, _, _ = self.request(
            "PATCH", "/api/admin/users/" + seller_id + "/status",
            {"status": "suspended"}, admin_cookie,
        )
        self.assertEqual(status, 200)
        status, session, _ = self.request(
            "GET", "/api/auth/me", cookie=seller_new_cookie.split(";", 1)[0],
        )
        self.assertEqual(status, 200)
        self.assertIsNone(session["user"])


if __name__ == "__main__":
    unittest.main()
