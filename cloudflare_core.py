"""Cloudflare 请求与 D1 适配；校验、常量及密码算法直接复用本地服务。"""
import hashlib
import json
import re
import secrets
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from http.cookies import CookieError, SimpleCookie

import server
from cloudflare_crypto import verify_password

def plain(value):
    return value.to_py() if hasattr(value, "to_py") else value


@dataclass
class Reply:
    status: int
    body: bytes
    headers: dict


class D1Store:
    def __init__(self, db, password_hash):
        self.db = db
        self.epoch = hashlib.sha256(password_hash.encode()).hexdigest()

    def statement(self, sql, *args):
        return self.db.prepare(sql).bind(*args)

    async def query(self, sql, *args):
        result = plain(await self.statement(sql, *args).all())
        return result.get("results", [])

    async def batch(self, statements):
        return plain(await self.db.batch(statements))

    async def create_session(self, kind, device_name=""):
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        await self.batch([
            self.statement("DELETE FROM sessions WHERE expires_at < ? OR password_epoch != ?", now, self.epoch),
            self.statement("INSERT INTO sessions (token_hash,expires_at,kind,device_name,created_at,last_used_at,password_epoch) VALUES (?,?,?,?,?,?,?)",
                           self.token_hash(token), now+(server.TOKEN_TTL if kind == "token" else server.SESSION_TTL), kind, device_name, now, now, self.epoch),
        ])
        return token

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    async def check_session(self, token, kind):
        now = time.time()
        rows = await self.query("SELECT expires_at FROM sessions WHERE token_hash=? AND kind=? AND password_epoch=?",
                                self.token_hash(token), kind, self.epoch)
        if not rows or rows[0]["expires_at"] < now:
            return False
        if kind == "token" and rows[0]["expires_at"]-now < server.TOKEN_RENEW_THRESHOLD:
            await self.query("UPDATE sessions SET expires_at=?,last_used_at=? WHERE token_hash=? AND kind='token' AND password_epoch=? AND expires_at<?",
                             int(now)+server.TOKEN_TTL, int(now), self.token_hash(token), self.epoch, now+server.TOKEN_RENEW_THRESHOLD)
        return True

    async def delete_session(self, token, kind):
        await self.query("DELETE FROM sessions WHERE token_hash=? AND kind=?", self.token_hash(token), kind)

    async def too_many_failures(self, ip):
        rows = await self.query("SELECT count(*) AS count FROM login_failures WHERE ip_hash=? AND failed_at>?", ip, time.time()-server.LOGIN_WINDOW)
        return rows[0]["count"] >= server.LOGIN_MAX_FAILURES

    async def record_failure(self, ip):
        now = time.time()
        result = await self.batch([
            self.statement("DELETE FROM login_failures WHERE failed_at<=?", now-server.LOGIN_WINDOW),
            self.statement("INSERT INTO login_failures (ip_hash,failed_at) SELECT ?,? WHERE (SELECT count(*) FROM login_failures WHERE ip_hash=?)<?", ip, now, ip, server.LOGIN_MAX_FAILURES),
        ])
        return result[1]["meta"]["changes"] == 1

    async def clear_failures(self, ip):
        await self.query("DELETE FROM login_failures WHERE ip_hash=?", ip)

    async def list_trips(self, trip_id=None, batch_id=None):
        columns = "id,"+",".join(server.TRIP_COLUMNS)+",created_at,updated_at"
        where, args = "", []
        if trip_id is not None:
            where, args = " WHERE id=?", [trip_id]
        elif batch_id is not None:
            where, args = " WHERE write_batch=?", [batch_id]
        rows = await self.query("SELECT "+columns+" FROM trips"+where+" ORDER BY depart_at DESC,id DESC", *args)
        if not rows:
            return []
        # 一次读区段，避免逐条查询导致导出超过D1子请求配额。
        leg_where = " WHERE trip_id=?" if trip_id is not None else ""
        legs = await self.query("SELECT trip_id,"+",".join(server.LEG_FIELDS)+" FROM trip_legs"+leg_where+" ORDER BY trip_id,seq", *([trip_id] if trip_id is not None else []))
        by_id = {t["id"]: t for t in rows}
        for t in rows:
            t["legs"] = []
        for leg in legs:
            if leg["trip_id"] in by_id:
                by_id[leg["trip_id"]]["legs"].append({k: leg[k] for k in server.LEG_FIELDS})
        return rows

    async def create_trips(self, trips):
        statements, batch_ids = [], []
        now = server.now_iso()
        # 每个JSON绑定值控制在1MB内，整次导入仍用一个事务。
        chunks, current, size = [], [], 0
        for trip in trips:
            encoded = json.dumps(trip, ensure_ascii=False, separators=(",", ":"))
            length = len(encoded.encode())+1
            if current and size+length > 1000000:
                chunks.append(current)
                current, size = [], 0
            current.append(encoded)
            size += length
        if current:
            chunks.append(current)
        columns = ",".join(server.TRIP_COLUMNS)
        fields = ",".join("json_extract(value,'$."+c+"')" for c in server.TRIP_COLUMNS)
        leg_fields = ",".join(server.LEG_FIELDS)
        leg_values = ",".join("json_extract(l.value,'$."+c+"')" for c in server.LEG_FIELDS)
        for chunk in chunks:
            batch_id = secrets.token_hex(16)
            batch_ids.append(batch_id)
            data = "["+",".join(chunk)+"]"
            statements.append(self.statement("INSERT INTO trips ("+columns+",created_at,updated_at,write_batch,input_index) SELECT "+fields+",?,?,?,CAST(key AS INTEGER) FROM json_each(?)", now, now, batch_id, data))
            statements.append(self.statement("INSERT INTO trip_legs (trip_id,seq,"+leg_fields+") SELECT t.id,CAST(l.key AS INTEGER),"+leg_values+" FROM json_each(?) q JOIN trips t ON t.write_batch=? AND t.input_index=CAST(q.key AS INTEGER),json_each(q.value,'$.legs') l", data, batch_id))
        if statements:
            await self.batch(statements)
        return batch_ids

    async def update_trip(self, trip_id, trip):
        columns = ",".join(c+"=?" for c in server.TRIP_COLUMNS)
        fields = ",".join(server.LEG_FIELDS)
        values = ",".join("json_extract(value,'$."+k+"')" for k in server.LEG_FIELDS)
        await self.batch([
            self.statement("UPDATE trips SET "+columns+",updated_at=? WHERE id=?", *(trip[c] for c in server.TRIP_COLUMNS), server.now_iso(), trip_id),
            self.statement("DELETE FROM trip_legs WHERE trip_id=?", trip_id),
            self.statement("INSERT INTO trip_legs (trip_id,seq,"+fields+") SELECT ?,CAST(key AS INTEGER),"+values+" FROM json_each(?) WHERE EXISTS (SELECT 1 FROM trips WHERE id=?)", trip_id, json.dumps(trip["legs"],ensure_ascii=False), trip_id),
        ])
        rows = await self.list_trips(trip_id)
        return rows[0] if rows else None


class CloudflareApp:
    def __init__(self, db, password_hash, cors_origins="https://localhost,capacitor://localhost"):
        self.store = D1Store(db, password_hash)
        self.password_hash = password_hash
        self.cors_origins = {v.strip() for v in cors_origins.split(",") if v.strip() and v.strip() != "*"}

    def reply(self, status, data=None, extra=None):
        headers = {**server.SECURITY_HEADERS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", **(extra or {})}
        body = b"" if data is None else json.dumps(data,ensure_ascii=False).encode()
        return Reply(status, body, headers)

    async def handle(self, method, path, headers, body, ip):
        headers = {k.lower(): v for k,v in headers.items()}
        try:
            result = await self.route(method,path,headers,body,hashlib.sha256(ip.encode()).hexdigest())
        except server.ApiError as e:
            result = self.reply(e.status,{"error":e.message})
        except Exception as error:
            # 只记录异常类型及源码位置，不输出错误内容、请求或用户数据。
            frames = [(f.name, f.lineno) for f in traceback.extract_tb(error.__traceback__) if f.filename.endswith(("cloudflare_core.py", "cloudflare_crypto.py"))]
            categories = [tag for tag in ("D1_ERROR", "SQLITE", "DataCloneError", "TypeError", "serialize", "bind", "Array", "Promise") if tag in str(error)]
            print("Worker 内部错误：", type(error).__name__, frames, categories)
            result = self.reply(500,{"error":"服务器内部错误"})
        origin = headers.get("origin")
        if path.startswith("/api/") and origin in self.cors_origins:
            result.headers.update({"Access-Control-Allow-Origin":origin,"Vary":"Origin"})
        return result

    def read_json(self, headers, body):
        if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise server.ApiError(415,"请求必须是 JSON")
        if len(body) > server.MAX_BODY:
            raise server.ApiError(413,"请求内容过大")
        try:
            return json.loads(body)
        except (ValueError,UnicodeError):
            raise server.ApiError(400,"JSON 格式错误") from None

    async def credential(self, headers):
        if "authorization" in headers:
            match = re.fullmatch(r"Bearer ([A-Za-z0-9_-]+)",headers["authorization"])
            if not match:
                return None
            token,kind = match.group(1),"token"
        else:
            try:
                value = SimpleCookie(headers.get("cookie", "")).get(server.SESSION_COOKIE)
            except CookieError:
                return None
            if value is None or not value.value:
                return None
            token,kind = value.value,"cookie"
        if not self.password_hash or not await self.store.check_session(token,kind):
            return None
        return kind,token

    @staticmethod
    def cookie(token, ttl):
        return f"{server.SESSION_COOKIE}={token}; Path=/; Max-Age={ttl}; HttpOnly; SameSite=Strict; Secure"

    async def route(self, method, path, headers, body, ip):
        if method == "OPTIONS":
            if headers.get("origin") not in self.cors_origins:
                raise server.ApiError(403,"来源不被允许")
            return self.reply(204,extra={"Access-Control-Allow-Methods":"GET, POST, PUT, DELETE","Access-Control-Allow-Headers":"Authorization, Content-Type","Access-Control-Max-Age":"600"})
        if path == "/api/meta" and method == "GET":
            return self.reply(200,{"app":"travel-log","api_version":server.API_VERSION,"server_version":server.SERVER_VERSION})
        if path == "/api/session" and method == "GET":
            return self.reply(200,{"authenticated":await self.credential(headers) is not None})
        if path in ("/api/login","/api/tokens") and method == "POST":
            if await self.store.too_many_failures(ip):
                raise server.ApiError(429,"尝试次数过多，请 10 分钟后再试")
            data = self.read_json(headers,body)
            password = data.get("password") if isinstance(data,dict) else None
            if not self.password_hash:
                raise server.ApiError(503,"尚未设置密码，请先在服务器上运行 python3 server.py set-password")
            if not isinstance(password,str) or not verify_password(password,self.password_hash):
                if not await self.store.record_failure(ip):
                    raise server.ApiError(429,"尝试次数过多，请 10 分钟后再试")
                raise server.ApiError(401,"密码错误")
            await self.store.clear_failures(ip)
            if path == "/api/login":
                token = await self.store.create_session("cookie")
                return self.reply(200,{"ok":True},{"Set-Cookie":self.cookie(token,server.SESSION_TTL)})
            name = data.get("device_name", "")
            if not isinstance(name,str):
                raise server.ApiError(400,"设备名称必须是文字")
            name = name.strip()
            if len(name)>50:
                raise server.ApiError(400,"设备名称最多 50 个字")
            token = await self.store.create_session("token",name)
            return self.reply(201,{"token":token,"token_type":"Bearer","expires_in":server.TOKEN_TTL})
        credential = await self.credential(headers)
        if path == "/api/logout" and method == "POST":
            if credential and credential[0] == "cookie":
                await self.store.delete_session(credential[1],"cookie")
            return self.reply(200,{"ok":True},{"Set-Cookie":self.cookie("",0)})
        if credential is None:
            raise server.ApiError(401,"请先登录")
        if path == "/api/tokens/current" and method == "DELETE":
            if credential[0] != "token":
                raise server.ApiError(401,"请先登录")
            await self.store.delete_session(credential[1],"token")
            return self.reply(200,{"ok":True})
        if path == "/api/trips":
            if method == "GET":
                return self.reply(200,{"trips":await self.store.list_trips()})
            if method == "POST":
                batch = await self.store.create_trips([server.validate_trip(self.read_json(headers,body))])
                rows = await self.store.list_trips(batch_id=batch[0])
                return self.reply(201,{"trip":rows[0]})
        match = re.fullmatch(r"/api/trips/(\d+)",path)
        if match:
            trip_id = int(match.group(1))
            if method == "PUT":
                trip = await self.store.update_trip(trip_id,server.validate_trip(self.read_json(headers,body)))
                if trip is None:
                    raise server.ApiError(404,"记录不存在")
                return self.reply(200,{"trip":trip})
            if method == "DELETE":
                rows = await self.store.query("DELETE FROM trips WHERE id=? RETURNING id",trip_id)
                if not rows:
                    raise server.ApiError(404,"记录不存在")
                return self.reply(200,{"ok":True})
        if path == "/api/export" and method == "GET":
            data = {"app":"travel-log","version":1,"exported_at":server.now_iso(),"trips":await self.store.list_trips()}
            return self.reply(200,data,{"Content-Disposition":f'attachment; filename="travel-log-{datetime.now():%Y%m%d}.json"'})
        if path == "/api/import" and method == "POST":
            data = self.read_json(headers,body)
            trips = data.get("trips") if isinstance(data,dict) else data
            if not isinstance(trips,list):
                raise server.ApiError(400,"导入文件中没有找到 trips 列表")
            if len(trips)>server.MAX_IMPORT:
                raise server.ApiError(400,f"一次最多导入 {server.MAX_IMPORT} 条")
            valid=[]
            for i,trip in enumerate(trips,1):
                try:
                    valid.append(server.validate_trip(trip))
                except server.ApiError as e:
                    raise server.ApiError(400,f"第 {i} 条：{e.message}") from None
            await self.store.create_trips(valid)
            return self.reply(200,{"imported":len(valid)})
        raise server.ApiError(404,"接口不存在")
