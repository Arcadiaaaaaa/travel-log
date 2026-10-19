import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

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

    def request(self, method, path, body=None, *, raw=None, content_type="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1])
        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = content_type
        conn.request(method, path, body=data, headers=headers)
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


if __name__ == "__main__":
    unittest.main()
