import hashlib
import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

PASSWORD = "correct-horse"

TRIP = {
    "transport": "hsr",
    "depart_at": "2026-10-01T08:00",
    "arrive_at": "2026-10-01T12:28",
    "price": "553.5",
    "from_place": "北京南",
    "to_place": "上海虹桥",
    "train_no": "g1",
    "vehicle_model": "CR400AF",
    "note": "国庆出行",
}


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = server.Database(Path(self.tmp.name) / "travel.db")
        self.db.set_password(PASSWORD, iterations=1000)
        self.httpd = server.TravelServer(("127.0.0.1", 0), self.db)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.db.close()
        self.tmp.cleanup()

    def request(self, method, path, body=None, *, raw=None, content_type="application/json", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1])
        request_headers = {}
        if self.cookie:
            request_headers["Cookie"] = self.cookie
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            request_headers["Content-Type"] = content_type
        request_headers.update(headers or {})
        conn.request(method, path, body=data, headers=request_headers)
        resp = conn.getresponse()
        payload = resp.read()
        conn.close()
        try:
            parsed = json.loads(payload)
        except ValueError:
            parsed = payload
        return resp, parsed

    def login(self):
        resp, _ = self.request("POST", "/api/login", {"password": PASSWORD})
        self.assertEqual(resp.status, 200)
        self.cookie = resp.getheader("Set-Cookie").split(";")[0]

    def test_requires_login(self):
        resp, body = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 401)
        resp, body = self.request("GET", "/api/session")
        self.assertEqual(body, {"authenticated": False})

    def test_wrong_password_and_rate_limit(self):
        for _ in range(server.LOGIN_MAX_FAILURES):
            resp, _ = self.request("POST", "/api/login", {"password": "nope"})
            self.assertEqual(resp.status, 401)
        resp, _ = self.request("POST", "/api/login", {"password": PASSWORD})
        self.assertEqual(resp.status, 429)

    def test_cookie_flags(self):
        resp, _ = self.request("POST", "/api/login", {"password": PASSWORD})
        cookie = resp.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)

    def test_crud(self):
        self.login()
        resp, body = self.request("POST", "/api/trips", TRIP)
        self.assertEqual(resp.status, 201, body)
        trip = body["trip"]
        self.assertEqual(trip["price_cents"], 55350)
        self.assertEqual(trip["train_no"], "G1")

        resp, body = self.request("PUT", f"/api/trips/{trip['id']}", {**TRIP, "price": "0", "train_no": ""})
        self.assertEqual(resp.status, 200, body)
        self.assertEqual(body["trip"]["price_cents"], 0)
        self.assertEqual(body["trip"]["train_no"], "")

        self.request("POST", "/api/trips", {**TRIP, "depart_at": "2026-10-05T08:00", "arrive_at": "2026-10-05T08:30"})
        resp, body = self.request("GET", "/api/trips")
        self.assertEqual([t["depart_at"] for t in body["trips"]], ["2026-10-05T08:00", "2026-10-01T08:00"])

        resp, _ = self.request("DELETE", f"/api/trips/{trip['id']}")
        self.assertEqual(resp.status, 200)
        resp, _ = self.request("DELETE", f"/api/trips/{trip['id']}")
        self.assertEqual(resp.status, 404)
        resp, _ = self.request("PUT", "/api/trips/9999", TRIP)
        self.assertEqual(resp.status, 404)

    def test_validation(self):
        self.login()
        bad = [
            {**TRIP, "transport": "plane"},
            {**TRIP, "arrive_at": "2026-10-01T07:59"},
            {**TRIP, "depart_at": "2026-02-30T08:00"},
            {**TRIP, "depart_at": "2026-10-01 08:00"},
            {**TRIP, "price": "-1"},
            {**TRIP, "price": "1.234"},
            {**TRIP, "price": "abc"},
            {**TRIP, "price": "NaN"},
            {**TRIP, "price": ""},
            {**TRIP, "note": "x" * 1001},
            {**TRIP, "train_no": 123},
        ]
        for data in bad:
            resp, body = self.request("POST", "/api/trips", data)
            self.assertEqual(resp.status, 400, (data, body))
            self.assertIn("error", body)
        _, body = self.request("GET", "/api/trips")
        self.assertEqual(body["trips"], [])

    def test_requires_json_content_type(self):
        self.login()
        resp, _ = self.request("POST", "/api/trips", raw=b"transport=hsr", content_type="application/x-www-form-urlencoded")
        self.assertEqual(resp.status, 415)

    def test_export_import_roundtrip(self):
        self.login()
        self.request("POST", "/api/trips", TRIP)
        resp, exported = self.request("GET", "/api/export")
        self.assertEqual(resp.status, 200)
        self.assertIn("attachment", resp.getheader("Content-Disposition"))
        resp, body = self.request("POST", "/api/import", exported)
        self.assertEqual(body, {"imported": 1})
        _, body = self.request("GET", "/api/trips")
        self.assertEqual(len(body["trips"]), 2)

        resp, body = self.request("POST", "/api/import", {"trips": [TRIP, {**TRIP, "price": "-5"}]})
        self.assertEqual(resp.status, 400)
        self.assertIn("第 2 条", body["error"])
        _, body = self.request("GET", "/api/trips")
        self.assertEqual(len(body["trips"]), 2)  # 有一条出错时整批都不导入

    def test_metro_legs(self):
        self.login()
        metro = {
            "transport": "metro",
            "depart_at": "2026-10-08T08:00",
            "arrive_at": "2026-10-08T08:50",
            "price": "6",
            "network": " 北京地铁 ",
            "train_no": "应被清空",
            "legs": [
                {"line": "2号线", "vehicle_model": "6b", "from_station": "西直门", "to_station": "建国门"},
                {"line": "1号线", "vehicle_model": "6as", "from_station": "建国门", "to_station": "国贸"},
            ],
        }
        resp, body = self.request("POST", "/api/trips", metro)
        self.assertEqual(resp.status, 201, body)
        trip = body["trip"]
        self.assertEqual(trip["network"], "北京地铁")
        self.assertEqual((trip["from_place"], trip["to_place"]), ("西直门", "国贸"))
        self.assertEqual(trip["train_no"], "")
        self.assertEqual([leg["vehicle_model"] for leg in trip["legs"]], ["6B", "6As"])

        resp, body = self.request("PUT", f"/api/trips/{trip['id']}", {**metro, "legs": metro["legs"][:1]})
        self.assertEqual(len(body["trip"]["legs"]), 1)
        self.assertEqual(body["trip"]["to_place"], "建国门")

        _, body = self.request("GET", "/api/trips")
        self.assertEqual(len(body["trips"][0]["legs"]), 1)

        resp, _ = self.request("POST", "/api/trips", {**TRIP, "legs": metro["legs"]})
        self.assertEqual(resp.status, 400)  # 非地铁不能有换乘区段
        resp, _ = self.request("POST", "/api/trips", {**metro, "legs": metro["legs"] * 6})
        self.assertEqual(resp.status, 400)

        resp, _ = self.request("DELETE", f"/api/trips/{trip['id']}")
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM trip_legs").fetchone()[0], 0)

    def test_seat_and_distance(self):
        self.login()
        resp, body = self.request("POST", "/api/trips", {**TRIP, "seat": "二等座", "distance_km": "1318.5"})
        self.assertEqual(resp.status, 201, body)
        self.assertEqual((body["trip"]["seat"], body["trip"]["distance_km"]), ("二等座", 1318.5))

        resp, body = self.request("POST", "/api/trips", TRIP)  # 都不填
        self.assertEqual((body["trip"]["seat"], body["trip"]["distance_km"]), ("", 0))

        resp, body = self.request("POST", "/api/trips", {**TRIP, "transport": "normal_train", "seat": "硬卧", "distance_km": 1200})
        self.assertEqual(resp.status, 201, body)

        bad = [
            {**TRIP, "seat": "硬卧"},  # 高铁没有硬卧
            {**TRIP, "transport": "normal_train", "seat": "二等座"},
            {**TRIP, "distance_km": "-1"},
            {**TRIP, "distance_km": "1.25"},
            {**TRIP, "distance_km": "abc"},
        ]
        for data in bad:
            resp, body = self.request("POST", "/api/trips", data)
            self.assertEqual(resp.status, 400, (data, body))

        metro = {**TRIP, "transport": "metro", "network": "北京地铁", "seat": "一等座",
                 "legs": [{"line": "2号线"}]}
        resp, body = self.request("POST", "/api/trips", metro)
        self.assertEqual(body["trip"]["seat"], "")  # 地铁不分坐席

    def test_legacy_metro_import(self):
        self.login()
        old = {**TRIP, "transport": "metro", "train_no": "2号线", "vehicle_model": "a型车",
               "from_place": "西直门", "to_place": "积水潭"}
        resp, body = self.request("POST", "/api/import", {"trips": [old]})
        self.assertEqual(resp.status, 200, body)
        _, body = self.request("GET", "/api/trips")
        self.assertEqual(body["trips"][0]["legs"], [
            {"line": "2号线", "vehicle_model": "a型车", "from_station": "西直门", "to_station": "积水潭"},
        ])

    def test_logout(self):
        self.login()
        self.request("POST", "/api/logout", {})
        resp, _ = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 401)

    def test_change_password_revokes_sessions(self):
        self.login()
        self.db.set_password("another-pass", iterations=1000)
        resp, _ = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 401)

    def test_static_files(self):
        resp, body = self.request("GET", "/")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type"))
        self.assertIn("default-src 'self'", resp.getheader("Content-Security-Policy"))
        resp, body = self.request("HEAD", "/")
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")
        for path in ("/../server.py", "/%2e%2e/server.py", "/icons/../../server.py"):
            resp, _ = self.request("GET", path)
            self.assertEqual(resp.status, 404, path)

    def test_favicon(self):
        resp, body = self.request("GET", "/favicon.ico")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "image/png")
        self.assertEqual(body, (server.STATIC_DIR / "icons" / "icon-192.png").read_bytes())

    def test_meta(self):
        resp, body = self.request("GET", "/api/meta")
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, {"app": "travel-log", "api_version": 1, "server_version": "1.0.0"})

    def issue_token(self, **extra):
        resp, body = self.request("POST", "/api/tokens", {"password": PASSWORD, **extra})
        self.assertEqual(resp.status, 201)
        return body["token"]

    def test_token_issuance(self):
        before = int(time.time())
        resp, body = self.request("POST", "/api/tokens", {"password": PASSWORD, "device_name": " Android App 1.0.0 "})
        self.assertEqual(resp.status, 201)
        self.assertEqual(set(body), {"token", "token_type", "expires_in"})
        self.assertEqual((body["token_type"], body["expires_in"]), ("Bearer", 7776000))
        self.assertIsNone(resp.getheader("Set-Cookie"))
        token = body["token"]
        self.assertTrue(isinstance(token, str) and len(token) == 43)
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self.db.conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (digest,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual((row["kind"], row["device_name"]), ("token", "Android App 1.0.0"))
        self.assertAlmostEqual(row["expires_at"] - before, 7776000, delta=2)
        self.assertEqual(row["created_at"], row["last_used_at"])
        self.assertTrue(token not in json.dumps(dict(row)))

    def test_token_device_name_defaults_to_empty(self):
        token = self.issue_token()
        row = self.db.conn.execute("SELECT device_name FROM sessions WHERE kind = 'token'").fetchone()
        self.assertIsNotNone(token)
        self.assertEqual(row["device_name"], "")

    def test_token_device_name_validation(self):
        for value in (None, 123, True, [], {}):
            resp, body = self.request("POST", "/api/tokens", {"password": PASSWORD, "device_name": value})
            self.assertEqual(resp.status, 400)
            self.assertEqual(body, {"error": "设备名称必须是文本"})
        resp, body = self.request("POST", "/api/tokens", {"password": PASSWORD, "device_name": "名" * 51})
        self.assertEqual(resp.status, 400)
        self.assertEqual(body, {"error": "设备名称最多 50 个字"})
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.issue_token(device_name=" " + "名" * 50 + " ")

    def test_token_wrong_password_shares_login_limit(self):
        for _ in range(5):
            resp, body = self.request("POST", "/api/tokens", {"password": "wrong"})
            self.assertEqual(resp.status, 401)
            self.assertEqual(body, {"error": "密码错误"})
        resp, _ = self.request("POST", "/api/login", {"password": PASSWORD})
        self.assertEqual(resp.status, 429)

    def test_token_login_limit_is_shared_in_reverse(self):
        for _ in range(5):
            self.request("POST", "/api/login", {"password": "wrong"})
        resp, _ = self.request("POST", "/api/tokens", {"password": PASSWORD})
        self.assertEqual(resp.status, 429)

    def test_token_requires_json(self):
        resp, _ = self.request("POST", "/api/tokens", raw=b"password=test", content_type="text/plain")
        self.assertEqual(resp.status, 415)

    def test_token_requires_configured_password(self):
        with self.db.lock, self.db.conn:
            self.db.conn.execute("DELETE FROM settings WHERE key = 'password_hash'")
        resp, _ = self.request("POST", "/api/tokens", {"password": PASSWORD})
        self.assertEqual(resp.status, 503)

    def test_token_authenticates_trips_and_session(self):
        token = self.issue_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp, body = self.request("GET", "/api/trips", headers=headers)
        self.assertEqual((resp.status, body), (200, {"trips": []}))
        resp, body = self.request("GET", "/api/session", headers=headers)
        self.assertEqual((resp.status, body), (200, {"authenticated": True}))

    def test_token_and_cookie_cannot_be_interchanged(self):
        self.login()
        cookie_value = self.cookie.split("=", 1)[1]
        resp, _ = self.request("GET", "/api/trips", headers={"Authorization": f"Bearer {cookie_value}"})
        self.assertEqual(resp.status, 401)
        token = self.issue_token()
        resp, _ = self.request("GET", "/api/trips", headers={"Cookie": f"tl_session={token}"})
        self.assertEqual(resp.status, 401)

    def test_authorization_never_falls_back_to_cookie(self):
        self.login()
        for value in ("", "Bearer invalid", "Basic invalid", "Bearer bad!", "Bearer a b", "bearer invalid"):
            resp, _ = self.request("GET", "/api/trips", headers={"Authorization": value})
            self.assertEqual(resp.status, 401)
            resp, body = self.request("GET", "/api/session", headers={"Authorization": value})
            self.assertEqual((resp.status, body), (200, {"authenticated": False}))

    def test_token_revocation(self):
        token = self.issue_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp, body = self.request("DELETE", "/api/tokens/current", headers=headers)
        self.assertEqual((resp.status, body), (200, {"ok": True}))
        resp, _ = self.request("GET", "/api/trips", headers=headers)
        self.assertEqual(resp.status, 401)
        resp, _ = self.request("DELETE", "/api/tokens/current", headers=headers)
        self.assertEqual(resp.status, 401)

    def test_token_revocation_rejects_cookie(self):
        self.login()
        resp, _ = self.request("DELETE", "/api/tokens/current")
        self.assertEqual(resp.status, 401)
        resp, _ = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 200)

    def test_token_and_cookie_revoked_by_password_change(self):
        self.login()
        token = self.issue_token()
        self.db.set_password("another-test-password", iterations=1000)
        resp, _ = self.request("GET", "/api/trips", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status, 401)
        resp, _ = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 401)

    def test_token_renews_only_when_below_89_days(self):
        token = self.issue_token()
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = 2_000_000_000
        with self.db.lock, self.db.conn:
            self.db.conn.execute("UPDATE sessions SET expires_at = ?, last_used_at = 0 WHERE token_hash = ?",
                                 (now + 10 * 86400, digest))
        headers = {"Authorization": f"Bearer {token}"}
        with patch("server.time.time", return_value=now):
            resp, _ = self.request("GET", "/api/trips", headers=headers)
            self.assertEqual(resp.status, 200)
            row = self.db.conn.execute("SELECT expires_at, last_used_at FROM sessions WHERE token_hash = ?", (digest,)).fetchone()
            self.assertEqual(tuple(row), (now + 7776000, now))
            changes = self.db.conn.total_changes
            self.request("GET", "/api/trips", headers=headers)
            self.assertEqual(self.db.conn.total_changes, changes)
        with patch("server.time.time", return_value=now + 86400):
            self.request("GET", "/api/trips", headers=headers)
            self.assertEqual(self.db.conn.total_changes, changes)
        with patch("server.time.time", return_value=now + 86401):
            self.request("GET", "/api/trips", headers=headers)
            row = self.db.conn.execute("SELECT expires_at FROM sessions WHERE token_hash = ?", (digest,)).fetchone()
            self.assertEqual(row["expires_at"], now + 86401 + 7776000)
            self.assertEqual(self.db.conn.total_changes, changes + 1)

    def test_token_expired_is_not_renewed(self):
        token = self.issue_token()
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db.lock, self.db.conn:
            self.db.conn.execute("UPDATE sessions SET expires_at = 1 WHERE token_hash = ?", (digest,))
        changes = self.db.conn.total_changes
        resp, _ = self.request("GET", "/api/trips", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status, 401)
        self.assertEqual(self.db.conn.total_changes, changes)

    def test_cookie_lifetime_remains_fixed(self):
        now = 2_000_000_000
        with patch("server.time.time", return_value=now):
            self.login()
        row = self.db.conn.execute("SELECT * FROM sessions WHERE kind = 'cookie'").fetchone()
        self.assertEqual(row["expires_at"], now + 2592000)
        changes = self.db.conn.total_changes
        with patch("server.time.time", return_value=now + 86400):
            resp, _ = self.request("GET", "/api/trips")
            self.assertEqual(resp.status, 200)
        self.assertEqual(self.db.conn.total_changes, changes)

    def configure_cors(self, origins=None):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.httpd = server.TravelServer(("127.0.0.1", 0), self.db, cors_origins=origins)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def assert_cors(self, response, origin):
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), origin)
        self.assertEqual(response.getheader("Vary"), "Origin")
        self.assertIsNone(response.getheader("Access-Control-Allow-Credentials"))

    def assert_no_cors(self, response):
        self.assertFalse(any(name.lower().startswith("access-control-") for name, _ in response.getheaders()))
        self.assertIsNone(response.getheader("Vary"))

    def test_cors_preflight_allowed_origins(self):
        for origin in ("https://localhost", "capacitor://localhost"):
            resp, body = self.request("OPTIONS", "/api/trips", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            })
            self.assertEqual((resp.status, body), (204, b""))
            self.assert_cors(resp, origin)
            self.assertEqual(resp.getheader("Access-Control-Allow-Methods"), "GET, POST, PUT, DELETE")
            self.assertEqual(resp.getheader("Access-Control-Allow-Headers"), "Authorization, Content-Type")
            self.assertEqual(resp.getheader("Access-Control-Max-Age"), "600")
            self.assertEqual(resp.getheader("Content-Length"), "0")

    def test_cors_preflight_rejects_other_origins(self):
        for origin in (None, "https://evil.example", "https://localhost.evil.example", "https://LOCALHOST", "https://localhost/", "null", "*"):
            headers = {} if origin is None else {"Origin": origin}
            resp, body = self.request("OPTIONS", "/api/trips", headers=headers)
            self.assertEqual((resp.status, body), (403, {"error": "来源不被允许"}))
            self.assert_no_cors(resp)

    def test_cors_preflight_does_not_apply_to_static(self):
        resp, _ = self.request("OPTIONS", "/", headers={"Origin": "https://localhost"})
        self.assertEqual(resp.status, 405)
        self.assert_no_cors(resp)

    def test_cors_success_and_error_responses(self):
        origin = "https://localhost"
        headers = {"Origin": origin}
        resp, _ = self.request("GET", "/api/meta", headers=headers)
        self.assertEqual(resp.status, 200)
        self.assert_cors(resp, origin)
        resp, _ = self.request("GET", "/api/trips", headers=headers)
        self.assertEqual(resp.status, 401)
        self.assert_cors(resp, origin)
        self.login()
        resp, _ = self.request("GET", "/api/missing", headers=headers)
        self.assertEqual(resp.status, 404)
        self.assert_cors(resp, origin)
        resp, _ = self.request("POST", "/api/trips", {}, headers=headers)
        self.assertEqual(resp.status, 400)
        self.assert_cors(resp, origin)
        resp, _ = self.request("POST", "/api/trips", raw=b"", content_type="text/plain", headers=headers)
        self.assertEqual(resp.status, 415)
        self.assert_cors(resp, origin)
        resp, _ = self.request("POST", "/api/trips", raw=b"", headers={**headers, "Content-Length": "5242881"})
        self.assertEqual(resp.status, 413)
        self.assert_cors(resp, origin)
        with patch.object(self.db, "list_trips", side_effect=RuntimeError("测试故障")):
            with self.assertLogs(server.log, level="ERROR"):
                resp, body = self.request("GET", "/api/trips", headers=headers)
        self.assertEqual((resp.status, body), (500, {"error": "服务器内部错误"}))
        self.assert_cors(resp, origin)
        for _ in range(5):
            self.request("POST", "/api/tokens", {"password": "wrong"}, headers=headers)
        resp, _ = self.request("POST", "/api/tokens", {"password": PASSWORD}, headers=headers)
        self.assertEqual(resp.status, 429)
        self.assert_cors(resp, origin)

    def test_cors_token_login_response(self):
        resp, body = self.request("POST", "/api/tokens", {"password": PASSWORD}, headers={"Origin": "capacitor://localhost"})
        self.assertEqual(resp.status, 201)
        self.assert_cors(resp, "capacitor://localhost")
        self.assertIsNone(resp.getheader("Set-Cookie"))
        resp, _ = self.request("GET", "/api/trips", headers={
            "Origin": "capacitor://localhost", "Authorization": f"Bearer {body['token']}",
        })
        self.assertEqual(resp.status, 200)
        self.assert_cors(resp, "capacitor://localhost")

    def test_cors_absent_for_no_origin_and_static(self):
        resp, _ = self.request("GET", "/api/meta")
        self.assert_no_cors(resp)
        resp, _ = self.request("GET", "/api/meta", headers={"Origin": "https://evil.example"})
        self.assert_no_cors(resp)
        for path in ("/", "/favicon.ico"):
            resp, _ = self.request("GET", path, headers={"Origin": "https://localhost"})
            self.assertEqual(resp.status, 200)
            self.assert_no_cors(resp)

    def test_cors_empty_and_custom_configuration(self):
        self.configure_cors([])
        resp, _ = self.request("GET", "/api/meta", headers={"Origin": "https://localhost"})
        self.assert_no_cors(resp)
        resp, _ = self.request("OPTIONS", "/api/trips", headers={"Origin": "https://localhost"})
        self.assertEqual(resp.status, 403)
        self.assert_no_cors(resp)
        self.configure_cors({"https://custom.example"})
        resp, _ = self.request("GET", "/api/meta", headers={"Origin": "https://custom.example"})
        self.assert_cors(resp, "https://custom.example")
        resp, _ = self.request("OPTIONS", "/api/trips", headers={"Origin": "https://localhost"})
        self.assertEqual(resp.status, 403)
        self.assert_no_cors(resp)

    def test_cors_environment_configuration(self):
        with patch.dict(server.os.environ, {"TRAVEL_CORS_ORIGINS": ""}):
            self.configure_cors()
        resp, _ = self.request("GET", "/api/meta", headers={"Origin": "https://localhost"})
        self.assert_no_cors(resp)
        with patch.dict(server.os.environ, {"TRAVEL_CORS_ORIGINS": " https://custom.example , capacitor://localhost "}):
            self.configure_cors()
        for origin in ("https://custom.example", "capacitor://localhost"):
            resp, _ = self.request("GET", "/api/meta", headers={"Origin": origin})
            self.assert_cors(resp, origin)

    def test_cors_never_allows_wildcard(self):
        self.configure_cors({"*"})
        resp, _ = self.request("GET", "/api/meta", headers={"Origin": "*"})
        self.assert_no_cors(resp)
        resp, _ = self.request("OPTIONS", "/api/trips", headers={"Origin": "*"})
        self.assertEqual(resp.status, 403)
        self.assert_no_cors(resp)

    def test_cors_state_resets_on_keep_alive_connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=3)
        try:
            conn.request("GET", "/api/meta", headers={"Origin": "https://localhost"})
            resp = conn.getresponse()
            resp.read()
            self.assert_cors(resp, "https://localhost")
            conn.request("GET", "/", headers={"Origin": "https://localhost"})
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 200)
            self.assert_no_cors(resp)
        finally:
            conn.close()

    def test_authorization_duplicate_headers_are_rejected(self):
        self.login()
        token = self.issue_token()
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=3)
        try:
            conn.putrequest("GET", "/api/trips")
            conn.putheader("Cookie", self.cookie)
            conn.putheader("Authorization", f"Bearer {token}")
            conn.putheader("Authorization", "Bearer invalid")
            conn.endheaders()
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 401)
        finally:
            conn.close()

    def test_token_revocation_does_not_revoke_other_sessions(self):
        self.login()
        first = self.issue_token()
        second = self.issue_token()
        self.request("DELETE", "/api/tokens/current", headers={"Authorization": f"Bearer {first}"})
        resp, _ = self.request("GET", "/api/trips", headers={"Authorization": f"Bearer {second}"})
        self.assertEqual(resp.status, 200)
        resp, _ = self.request("GET", "/api/trips")
        self.assertEqual(resp.status, 200)

    def test_token_rejects_malformed_bearer_with_valid_cookie(self):
        self.login()
        token = self.issue_token()
        for value in (f"Bearer {token} ", f"Bearer  {token}", f"Basic {token}", f"Bearer {token}!"):
            resp, _ = self.request("GET", "/api/trips", headers={"Authorization": value})
            self.assertEqual(resp.status, 401)

    def test_token_renewal_is_atomic(self):
        token = self.issue_token()
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db.lock, self.db.conn:
            self.db.conn.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                                 (int(time.time()) + 10 * 86400, digest))
        changes = self.db.conn.total_changes
        def request_once(_):
            resp, _ = self.request("GET", "/api/trips", headers={"Authorization": f"Bearer {token}"})
            return resp.status
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(request_once, range(6)))
        self.assertEqual(statuses, [200] * 6)
        self.assertEqual(self.db.conn.total_changes, changes + 1)

    def test_cors_password_not_configured(self):
        with self.db.lock, self.db.conn:
            self.db.conn.execute("DELETE FROM settings WHERE key = 'password_hash'")
        for path in ("/api/login", "/api/tokens"):
            resp, _ = self.request("POST", path, {"password": PASSWORD}, headers={"Origin": "https://localhost"})
            self.assertEqual(resp.status, 503)
            self.assert_cors(resp, "https://localhost")

    def test_cors_unsupported_method_response(self):
        resp, _ = self.request("PATCH", "/api/trips", headers={"Origin": "https://localhost"})
        self.assertEqual(resp.status, 501)
        self.assert_cors(resp, "https://localhost")
        resp, _ = self.request("PATCH", "/", headers={"Origin": "https://localhost"})
        self.assertEqual(resp.status, 501)
        self.assert_no_cors(resp)


class MigrationTest(unittest.TestCase):
    def test_v0_metro_rows_become_single_leg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            conn = sqlite3.connect(path)
            conn.executescript(server.SCHEMA)  # 第一版的表结构
            conn.execute(
                "INSERT INTO trips (transport, depart_at, arrive_at, from_place, to_place, price_cents, "
                "train_no, vehicle_model, note, created_at, updated_at) VALUES "
                "('metro', '2026-01-01T08:00', '2026-01-01T08:30', '西直门', '国贸', 500, "
                "'2号线', '6b', '', 'x', 'x'), "
                "('hsr', '2026-01-02T08:00', '2026-01-02T12:00', '北京南', '上海虹桥', 55300, "
                "'G1', 'CR400AF', '', 'x', 'x')"
            )
            conn.commit()
            conn.close()

            db = server.Database(path)
            trips = {t["transport"]: t for t in db.list_trips()}
            self.assertEqual(trips["metro"]["legs"], [
                {"line": "2号线", "vehicle_model": "6B", "from_station": "西直门", "to_station": "国贸"},
            ])
            self.assertEqual((trips["metro"]["train_no"], trips["metro"]["network"]), ("", ""))
            self.assertEqual(trips["hsr"]["legs"], [])
            self.assertEqual(trips["hsr"]["train_no"], "G1")
            self.assertEqual((trips["hsr"]["seat"], trips["hsr"]["distance_km"]), ("", 0))
            db.close()

            db = server.Database(path)  # 再次打开不应重复迁移
            self.assertEqual(len(db.list_trips()[1]["legs"]), 1)
            db.close()

    def test_v2_cookie_session_survives_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v2.db"
            token = "legacy-cookie-session"
            digest = hashlib.sha256(token.encode()).hexdigest()
            expires = int(time.time()) + 3600
            conn = sqlite3.connect(path)
            conn.executescript(server.SCHEMA)
            server.migrate_v1(conn)
            server.migrate_v2(conn)
            conn.execute("PRAGMA user_version = 2")
            conn.execute("INSERT INTO sessions (token_hash, expires_at) VALUES (?, ?)", (digest, expires))
            conn.commit()
            conn.close()

            db = server.Database(path)
            self.assertTrue(db.check_session(token))
            row = db.conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (digest,)).fetchone()
            self.assertIn("kind", row.keys())
            self.assertEqual(row["kind"], "cookie")
            self.assertEqual(row["expires_at"], expires)
            self.assertEqual((row["device_name"], row["created_at"], row["last_used_at"]), ("", 0, 0))
            self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], 3)
            db.close()

            db = server.Database(path)
            self.assertTrue(db.check_session(token))
            self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
