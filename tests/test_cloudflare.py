"""Cloudflare 适配使用真实 SQLite 执行 D1 查询，验证契约及事务边界。"""
import asyncio
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from cloudflare_core import CloudflareApp, D1Store


class Statement:
    def __init__(self, db, sql, args=()):
        self.db, self.sql, self.args = db, sql, args

    def bind(self, *args):
        return Statement(self.db, self.sql, args)

    async def all(self):
        result = self.execute()
        await asyncio.sleep(0)
        return result

    def execute(self):
        c = self.db.conn.execute(self.sql, self.args)
        rows = [dict(r) for r in c.fetchall()] if c.description else []
        return {"results": rows, "meta": {"changes": c.rowcount, "last_row_id": c.lastrowid}}


class D1:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(Path("cloudflare/migrations/0001_initial.sql").read_text())
        self.fail_batch = False

    def prepare(self, sql):
        return Statement(self, sql)

    async def batch(self, statements):
        self.conn.commit()
        with self.conn:
            result = []
            for i, statement in enumerate(statements):
                if self.fail_batch and i == 1:
                    raise RuntimeError("事务中途失败")
                result.append(statement.execute())
            return result


TRIP = {"transport": "hsr", "depart_at": "2026-10-01T08:00", "arrive_at": "2026-10-01T09:30", "price": "553.50", "seat": "二等座", "distance_km": "1318.5"}
METRO = {"transport": "metro", "depart_at": "2026-10-02T08:00", "arrive_at": "2026-10-02T08:40", "price": "5", "network": "北京地铁", "legs": [{"line": "2号线", "vehicle_model": "6b", "from_station": "西直门", "to_station": "建国门"}, {"line": "1号线", "from_station": "建国门", "to_station": "国贸"}]}


class CloudflareTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # 仅测试数据库使用，永不配置到线上。
        cls.password = "temporary-fixture-only"
        cls.password_hash = server.hash_password(cls.password)

    async def asyncSetUp(self):
        self.db = D1()
        self.app = CloudflareApp(self.db, self.password_hash)

    async def asyncTearDown(self):
        self.db.conn.close()

    async def request(self, method, path, data=None, headers=None, ip="test-ip"):
        h = {"Content-Type": "application/json", **(headers or {})}
        raw = json.dumps(data).encode() if data is not None else b""
        r = await self.app.handle(method, path, h, raw, ip)
        return r, json.loads(r.body) if r.body else None

    async def login(self, token=False):
        r, data = await self.request("POST", "/api/tokens" if token else "/api/login", {"password": self.password})
        self.assertEqual(r.status, 201 if token else 200)
        return {"Authorization": "Bearer " + data["token"]} if token else {"Cookie": r.headers["Set-Cookie"].split(";")[0]}

    async def test_meta_and_no_password_fail_closed(self):
        r, data = await self.request("GET", "/api/meta")
        self.assertEqual((r.status, data["app"], data["api_version"]), (200, "travel-log", 1))
        self.app = CloudflareApp(self.db, "")
        r, _ = await self.request("POST", "/api/login", {"password": self.password})
        self.assertEqual(r.status, 503)

    async def test_cookie_and_token_security(self):
        r, _ = await self.request("POST", "/api/login", {"password": self.password})
        for attribute in ["HttpOnly", "SameSite=Strict", "Secure", "Max-Age=2592000"]:
            self.assertIn(attribute, r.headers["Set-Cookie"])
        auth = await self.login(True)
        raw = auth["Authorization"].removeprefix("Bearer ")
        rows = self.db.conn.execute("SELECT * FROM sessions WHERE kind='token'").fetchall()
        self.assertEqual(rows[0]["token_hash"], hashlib.sha256(raw.encode()).hexdigest())
        self.assertNotIn(raw, str([dict(r) for r in rows]))

    async def test_authorization_never_falls_back_to_cookie(self):
        cookie = await self.login()
        for authorization in ["", "Bearer invalid", "Basic invalid", "Bearer a, Bearer b"]:
            r, _ = await self.request("GET", "/api/trips", headers={**cookie, "Authorization": authorization})
            self.assertEqual(r.status, 401)

    async def test_session_kinds_are_not_interchangeable(self):
        cookie = await self.login()
        token = await self.login(True)
        for h in [{"Authorization": "Bearer " + cookie["Cookie"].split("=")[1]}, {"Cookie": "tl_session=" + token["Authorization"].split(" ")[1]}]:
            r, _ = await self.request("GET", "/api/trips", headers=h)
            self.assertEqual(r.status, 401)

    async def test_token_sliding_and_cookie_fixed_expiry(self):
        auth = await self.login(True)
        self.db.conn.execute("UPDATE sessions SET expires_at=1000+?", (server.TOKEN_TTL,))
        with patch("cloudflare_core.time.time", return_value=1001):
            await self.request("GET", "/api/trips", headers=auth)
        self.assertEqual(self.db.conn.execute("SELECT expires_at FROM sessions").fetchone()[0], 1000+server.TOKEN_TTL)
        with patch("cloudflare_core.time.time", return_value=1000+86401):
            await self.request("GET", "/api/trips", headers=auth)
        self.assertEqual(self.db.conn.execute("SELECT expires_at FROM sessions").fetchone()[0], 1000+86401+server.TOKEN_TTL)
        self.db.conn.execute("DELETE FROM sessions")
        cookie = await self.login()
        before = self.db.conn.execute("SELECT expires_at FROM sessions").fetchone()[0]
        await self.request("GET", "/api/trips", headers=cookie)
        self.assertEqual(self.db.conn.execute("SELECT expires_at FROM sessions").fetchone()[0], before)

    async def test_password_change_invalidates_both_kinds(self):
        cookie, token = await self.login(), await self.login(True)
        self.app = CloudflareApp(self.db, server.hash_password("another-fixture-only"))
        for auth in [cookie, token]:
            r, _ = await self.request("GET", "/api/trips", headers=auth)
            self.assertEqual(r.status, 401)

    async def test_login_failure_counter_shared_and_persistent(self):
        for i in range(5):
            r, _ = await self.request("POST", "/api/login" if i%2 else "/api/tokens", {"password": "wrong"})
            self.assertEqual(r.status, 401)
        self.app = CloudflareApp(self.db, self.password_hash)
        r, _ = await self.request("POST", "/api/login", {"password": self.password})
        self.assertEqual(r.status, 429)
        r, _ = await self.request("POST", "/api/login", {"password": self.password}, ip="other-ip")
        self.assertEqual(r.status, 200)

    async def test_crud_metro_and_export(self):
        auth = await self.login()
        r, data = await self.request("POST", "/api/trips", METRO, auth)
        self.assertEqual(r.status, 201)
        trip = data["trip"]
        self.assertEqual((trip["from_place"], trip["to_place"], len(trip["legs"])), ("西直门", "国贸", 2))
        self.assertEqual(trip["legs"][0]["vehicle_model"], "6B")
        self.assertEqual(set(trip), set(server.TRIP_COLUMNS)|{"id", "created_at", "updated_at", "legs"})
        r, data = await self.request("PUT", "/api/trips/"+str(trip["id"]), TRIP, auth)
        self.assertEqual((r.status, data["trip"]["seat"], data["trip"]["legs"]), (200, "二等座", []))
        r, data = await self.request("GET", "/api/export", headers=auth)
        self.assertEqual((r.status, data["version"], len(data["trips"])), (200, 1, 1))
        self.assertIn("Content-Disposition", r.headers)
        r, _ = await self.request("DELETE", "/api/trips/"+str(trip["id"]), headers=auth)
        self.assertEqual(r.status, 200)

    async def test_import_validation_and_atomic_rollback(self):
        auth = await self.login()
        r, _ = await self.request("POST", "/api/import", {"trips": [TRIP, {**TRIP, "price": "bad"}]}, auth)
        self.assertEqual(r.status, 400)
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM trips").fetchone()[0], 0)
        self.db.fail_batch = True
        r, _ = await self.request("POST", "/api/import", {"trips": [TRIP, METRO]}, auth)
        self.assertEqual(r.status, 500)
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM trips").fetchone()[0], 0)
        self.db.fail_batch = False
        r, data = await self.request("POST", "/api/import", {"trips": [TRIP, METRO, METRO]}, auth)
        self.assertEqual((r.status, data["imported"]), (200, 3))
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM trip_legs").fetchone()[0], 4)
        self.assertEqual(self.db.conn.execute("SELECT count(DISTINCT trip_id) FROM trip_legs").fetchone()[0], 2)

    async def test_cors_on_all_api_errors_and_preflight(self):
        for status, method, path, body, auth in [(401,"GET","/api/trips",None,{}),(404,"GET","/api/missing",None,await self.login())]:
            r, _ = await self.request(method,path,body,{**auth,"Origin":"https://localhost"})
            self.assertEqual(r.status,status)
            self.assertEqual(r.headers["Access-Control-Allow-Origin"],"https://localhost")
            self.assertEqual(r.headers["Vary"],"Origin")
            self.assertNotIn("Access-Control-Allow-Credentials",r.headers)
        r,_=await self.request("OPTIONS","/api/missing",headers={"Origin":"https://localhost"})
        self.assertEqual(r.status,204)
        r,_=await self.request("OPTIONS","/api/trips",headers={"Origin":"https://evil.example"})
        self.assertEqual(r.status,403)
        self.assertNotIn("Access-Control-Allow-Origin",r.headers)

    async def test_security_json_size_and_logout(self):
        auth=await self.login(True)
        r,_=await self.request("DELETE","/api/tokens/current",headers=auth)
        self.assertEqual(r.status,200)
        r,_=await self.request("GET","/api/trips",headers=auth)
        self.assertEqual(r.status,401)
        for key,value in server.SECURITY_HEADERS.items():self.assertEqual(r.headers[key],value)
        r=await self.app.handle("POST","/api/login",{"Content-Type":"text/plain"},b"{}","ip")
        self.assertEqual(r.status,415)
        r=await self.app.handle("POST","/api/login",{"Content-Type":"application/json"},b"x"*(server.MAX_BODY+1),"ip")
        self.assertEqual(r.status,413)

    async def test_large_import_spans_json_chunks_and_keeps_leg_links(self):
        trips = [server.validate_trip({**METRO,"note":"测"*800}) for _ in range(800)]
        await self.app.store.create_trips(trips)
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM trips").fetchone()[0],800)
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM trip_legs").fetchone()[0],1600)
        self.assertEqual(self.db.conn.execute("SELECT count(DISTINCT trip_id) FROM trip_legs").fetchone()[0],800)

    async def test_error_500_and_429_have_cors(self):
        auth=await self.login()
        self.db.fail_batch=True
        r,_=await self.request("POST","/api/trips",TRIP,{**auth,"Origin":"capacitor://localhost"})
        self.assertEqual(r.status,500)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"],"capacitor://localhost")
        self.db.fail_batch=False
        for _ in range(5):
            await self.request("POST","/api/tokens",{"password":"wrong"})
        r,_=await self.request("POST","/api/login",{"password":"wrong"},{"Origin":"https://localhost"})
        self.assertEqual(r.status,429)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"],"https://localhost")

    async def test_bad_json_and_missing_trip_match_existing_errors(self):
        r=await self.app.handle("POST","/api/login",{"Content-Type":"application/json"},b"{","test-ip")
        self.assertEqual(json.loads(r.body)["error"],"JSON 格式错误")
        auth=await self.login()
        r,data=await self.request("PUT","/api/trips/9999",TRIP,auth)
        self.assertEqual((r.status,data["error"]),(404,"记录不存在"))


    async def test_concurrent_failures_count_atomically(self):
        responses = await asyncio.gather(*[
            self.request("POST", "/api/login" if i % 2 else "/api/tokens", {"password": "wrong"})
            for i in range(9)
        ])
        statuses = [r.status for r, _ in responses]
        self.assertEqual(statuses.count(401), 5)
        self.assertEqual(statuses.count(429), 4)
        self.assertEqual(self.db.conn.execute("SELECT count(*) FROM login_failures").fetchone()[0], 5)
