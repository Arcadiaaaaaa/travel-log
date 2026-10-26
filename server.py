#!/usr/bin/env python3
"""旅行记录：自托管的个人行程记录服务。

只依赖 Python 3.9+ 标准库，数据保存在服务器本地的 SQLite 文件中。

    python3 server.py set-password   # 首次运行前设置登录密码
    python3 server.py serve          # 启动服务（默认监听 127.0.0.1:8765）
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB = BASE_DIR / "data" / "travel.db"
SERVER_VERSION = "1.0.0"
API_VERSION = 1

TRANSPORT_TYPES = {
    "normal_train": "普快火车",
    "emu": "动车组",
    "hsr": "高速动车组",
    "bus": "公交车",
    "metro": "地铁",
}

TEXT_FIELDS = {
    # 字段: (中文名, 最大长度)
    "from_place": ("出发地", 50),
    "to_place": ("到达地", 50),
    "train_no": ("车次号", 20),
    "vehicle_model": ("交通工具型号", 50),
    "note": ("备注", 1000),
    "network": ("地铁系统", 30),
}

LEG_FIELDS = {
    "line": ("线路", 20),
    "vehicle_model": ("车型", 20),
    "from_station": ("上车站", 50),
    "to_station": ("下车站", 50),
}
MAX_LEGS = 10
MAX_DISTANCE_KM = 100_000

# 坐席选项随交通方式不同；公交、地铁不分坐席
SEAT_OPTIONS = {
    "normal_train": ("硬座", "硬卧", "软卧", "无座"),
    "emu": ("二等座", "一等座", "商务座", "二等卧", "一等卧", "无座"),
    "hsr": ("二等座", "一等座", "商务座", "二等卧", "一等卧", "无座"),
}

SESSION_COOKIE = "tl_session"
SESSION_TTL = 30 * 24 * 3600
TOKEN_TTL = 90 * 24 * 3600
TOKEN_RENEW_THRESHOLD = 89 * 24 * 3600
MAX_BODY = 5 * 1024 * 1024
MAX_IMPORT = 20000
MAX_PRICE_CENTS = 100_000_000  # 100 万元
LOGIN_WINDOW = 10 * 60
LOGIN_MAX_FAILURES = 5
PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LEN = 8
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS trips (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    transport     TEXT    NOT NULL,
    depart_at     TEXT    NOT NULL,
    arrive_at     TEXT    NOT NULL,
    from_place    TEXT    NOT NULL DEFAULT '',
    to_place      TEXT    NOT NULL DEFAULT '',
    price_cents   INTEGER NOT NULL,
    train_no      TEXT    NOT NULL DEFAULT '',
    vehicle_model TEXT    NOT NULL DEFAULT '',
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trips_depart ON trips (depart_at);
"""


def migrate_v1(conn):
    """地铁按线网（如“北京地铁”）分类，并支持多段换乘。

    旧的地铁记录把线路存在车次号里，迁移成单段行程。
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(trips)")}
    if "network" not in columns:
        conn.execute("ALTER TABLE trips ADD COLUMN network TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS trip_legs (
            trip_id       INTEGER NOT NULL REFERENCES trips (id) ON DELETE CASCADE,
            seq           INTEGER NOT NULL,
            line          TEXT    NOT NULL DEFAULT '',
            vehicle_model TEXT    NOT NULL DEFAULT '',
            from_station  TEXT    NOT NULL DEFAULT '',
            to_station    TEXT    NOT NULL DEFAULT '',
            PRIMARY KEY (trip_id, seq)
        )"""
    )
    rows = conn.execute(
        "SELECT id, train_no, vehicle_model, from_place, to_place FROM trips "
        "WHERE transport = 'metro' AND id NOT IN (SELECT trip_id FROM trip_legs)"
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO trip_legs (trip_id, seq, line, vehicle_model, from_station, to_station) "
            "VALUES (?, 0, ?, ?, ?, ?)",
            (row[0], row[1], normalize_model(row[2]), row[3], row[4]),
        )
        conn.execute("UPDATE trips SET train_no = '', vehicle_model = '' WHERE id = ?", (row[0],))


def migrate_v2(conn):
    """新增坐席和里程（公里，未填写记为 0）。"""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(trips)")}
    if "seat" not in columns:
        conn.execute("ALTER TABLE trips ADD COLUMN seat TEXT NOT NULL DEFAULT ''")
    if "distance_km" not in columns:
        conn.execute("ALTER TABLE trips ADD COLUMN distance_km REAL NOT NULL DEFAULT 0")


def migrate_v3(conn):
    """区分 Web Cookie 与 App 令牌，保留已有 Cookie 会话。"""
    conn.execute("ALTER TABLE sessions ADD COLUMN kind TEXT NOT NULL DEFAULT 'cookie'")
    conn.execute("ALTER TABLE sessions ADD COLUMN device_name TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE sessions ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE sessions ADD COLUMN last_used_at INTEGER NOT NULL DEFAULT 0")


# 按顺序执行，PRAGMA user_version 记录已执行到第几个
MIGRATIONS = [migrate_v1, migrate_v2, migrate_v3]

TRIP_COLUMNS = (
    "transport", "depart_at", "arrive_at", "from_place", "to_place",
    "price_cents", "train_no", "vehicle_model", "note", "network", "seat", "distance_km",
)

log = logging.getLogger("travel-log")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- 密码 ----------

def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- 数据校验 ----------

def parse_time(value, label: str) -> datetime:
    if not isinstance(value, str) or not TIME_RE.match(value):
        raise ApiError(400, f"{label}格式应为 YYYY-MM-DDTHH:MM")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ApiError(400, f"{label}不是有效的日期时间") from None


def parse_price(value) -> int:
    """把以“元”为单位的票价（字符串或数字）转换为“分”。"""
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
        raise ApiError(400, "请填写票价")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ApiError(400, "票价必须是数字") from None
    if not amount.is_finite() or amount < 0:
        raise ApiError(400, "票价必须是不小于 0 的数字")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ApiError(400, "票价最多保留两位小数")
    if cents > MAX_PRICE_CENTS:
        raise ApiError(400, "票价过大")
    return int(cents)


def parse_distance(value) -> float:
    """里程（公里），留空记为 0，最多一位小数。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    if isinstance(value, bool):
        raise ApiError(400, "里程必须是数字")
    try:
        km = Decimal(str(value).strip())
    except InvalidOperation:
        raise ApiError(400, "里程必须是数字") from None
    if not km.is_finite() or km < 0:
        raise ApiError(400, "里程必须是不小于 0 的数字")
    if km * 10 != (km * 10).to_integral_value():
        raise ApiError(400, "里程最多保留一位小数")
    if km > MAX_DISTANCE_KM:
        raise ApiError(400, "里程过大")
    return float(km)


def parse_price_cents(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_PRICE_CENTS:
        raise ApiError(400, "price_cents 必须是不小于 0 的整数")
    return value


def clean_text(value, label: str, limit: int) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"{label}必须是文本")
    value = value.strip()
    if len(value) > limit:
        raise ApiError(400, f"{label}最多 {limit} 个字")
    return value


def normalize_model(value: str) -> str:
    """地铁车型统一写法：6b → 6B，6as → 6As。"""
    match = re.fullmatch(r"(\d+)([A-Za-z])([A-Za-z]*)", value)
    if not match:
        return value
    count, kind, suffix = match.groups()
    return f"{count}{kind.upper()}{suffix.lower()}"


def validate_legs(raw, trip: dict) -> list[dict]:
    if raw is None or raw == []:
        # 兼容旧格式：车次号即线路，起止地点即上下车站
        raw = [{
            "line": trip["train_no"],
            "vehicle_model": trip["vehicle_model"],
            "from_station": trip["from_place"],
            "to_station": trip["to_place"],
        }]
    if not isinstance(raw, list):
        raise ApiError(400, "换乘区段格式错误")
    if len(raw) > MAX_LEGS:
        raise ApiError(400, f"一次行程最多 {MAX_LEGS} 段")
    legs = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ApiError(400, f"第 {index} 段格式错误")
        leg = {field: clean_text(item.get(field), f"第 {index} 段的{label}", limit)
               for field, (label, limit) in LEG_FIELDS.items()}
        leg["vehicle_model"] = normalize_model(leg["vehicle_model"])
        legs.append(leg)
    return legs


def validate_trip(data) -> dict:
    if not isinstance(data, dict):
        raise ApiError(400, "请求格式错误")

    transport = data.get("transport")
    if transport not in TRANSPORT_TYPES:
        raise ApiError(400, "请选择交通方式")

    depart = parse_time(data.get("depart_at"), "出发时间")
    arrive = parse_time(data.get("arrive_at"), "到达时间")
    if arrive < depart:
        raise ApiError(400, "到达时间不能早于出发时间")

    if "price" in data:
        price_cents = parse_price(data["price"])
    elif "price_cents" in data:
        price_cents = parse_price_cents(data["price_cents"])
    else:
        raise ApiError(400, "请填写票价")

    trip = {
        "transport": transport,
        "depart_at": data["depart_at"],
        "arrive_at": data["arrive_at"],
        "price_cents": price_cents,
    }
    for field, (label, limit) in TEXT_FIELDS.items():
        trip[field] = clean_text(data.get(field), label, limit)
    trip["train_no"] = trip["train_no"].upper()
    trip["distance_km"] = parse_distance(data.get("distance_km"))

    seat = clean_text(data.get("seat"), "坐席", 10)
    allowed = SEAT_OPTIONS.get(transport)
    if allowed is None:
        seat = ""
    elif seat and seat not in allowed:
        raise ApiError(400, f"{TRANSPORT_TYPES[transport]}的坐席只能是：{'、'.join(allowed)}")
    trip["seat"] = seat

    if transport == "metro":
        legs = validate_legs(data.get("legs"), trip)
        # 整段行程的起止站取第一段的上车站和最后一段的下车站
        trip["from_place"] = legs[0]["from_station"]
        trip["to_place"] = legs[-1]["to_station"]
        trip["train_no"] = ""
        trip["vehicle_model"] = ""
    else:
        if data.get("legs"):
            raise ApiError(400, "只有地铁行程可以填写换乘区段")
        legs = []
        trip["network"] = ""
    trip["legs"] = legs
    return trip


# ---------- 数据库 ----------

class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for number, migration in enumerate(MIGRATIONS[version:], start=version + 1):
            self.conn.execute("BEGIN")
            try:
                migration(self.conn)
                self.conn.execute(f"PRAGMA user_version = {number}")
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def close(self):
        self.conn.close()

    # 设置
    def get_setting(self, key: str):
        with self.lock:
            row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_password(self, password: str, iterations: int = PBKDF2_ITERATIONS):
        hashed = hash_password(password, iterations)
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES ('password_hash', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (hashed,),
            )
            # 改密码后所有设备都需要重新登录
            self.conn.execute("DELETE FROM sessions")

    # 会话（库里只存令牌的哈希）
    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_session(self, *, kind="cookie", device_name="") -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            self.conn.execute(
                "INSERT INTO sessions (token_hash, expires_at, kind, device_name, created_at, last_used_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (self._token_hash(token), now + (TOKEN_TTL if kind == "token" else SESSION_TTL),
                 kind, device_name, now, now),
            )
        return token

    def check_session(self, token: str, *, kind="cookie") -> bool:
        now = time.time()
        with self.lock, self.conn:
            row = self.conn.execute(
                "SELECT expires_at FROM sessions WHERE token_hash = ? AND kind = ?",
                (self._token_hash(token), kind),
            ).fetchone()
            if not row or row["expires_at"] < now:
                return False
            # 令牌不足 89 天才续到 90 天；Cookie 不续期，重复请求不写库。
            if kind == "token" and row["expires_at"] - now < TOKEN_RENEW_THRESHOLD:
                self.conn.execute(
                    "UPDATE sessions SET expires_at = ?, last_used_at = ? WHERE token_hash = ? AND kind = 'token'",
                    (int(now) + TOKEN_TTL, int(now), self._token_hash(token)),
                )
            return True

    def delete_session(self, token: str, *, kind="cookie"):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM sessions WHERE token_hash = ? AND kind = ?", (self._token_hash(token), kind))

    # 行程
    def _with_legs(self, rows, leg_rows) -> list[dict]:
        trips = [dict(r) for r in rows]
        by_id = {t["id"]: t for t in trips}
        for t in trips:
            t["legs"] = []
        for leg in leg_rows:
            trip = by_id.get(leg["trip_id"])
            if trip is not None:
                trip["legs"].append({field: leg[field] for field in LEG_FIELDS})
        return trips

    def list_trips(self) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM trips ORDER BY depart_at DESC, id DESC"
            ).fetchall()
            legs = self.conn.execute("SELECT * FROM trip_legs ORDER BY trip_id, seq").fetchall()
        return self._with_legs(rows, legs)

    def get_trip(self, trip_id: int):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchall()
            legs = self.conn.execute(
                "SELECT * FROM trip_legs WHERE trip_id = ? ORDER BY seq", (trip_id,)
            ).fetchall()
        trips = self._with_legs(rows, legs)
        return trips[0] if trips else None

    def _write_legs(self, trip_id: int, legs: list[dict]):
        self.conn.execute("DELETE FROM trip_legs WHERE trip_id = ?", (trip_id,))
        self.conn.executemany(
            f"INSERT INTO trip_legs (trip_id, seq, {', '.join(LEG_FIELDS)}) "
            f"VALUES (?, ?, {', '.join('?' * len(LEG_FIELDS))})",
            [(trip_id, seq, *(leg[f] for f in LEG_FIELDS)) for seq, leg in enumerate(legs)],
        )

    def _insert(self, trip: dict) -> int:
        now = now_iso()
        cur = self.conn.execute(
            f"INSERT INTO trips ({', '.join(TRIP_COLUMNS)}, created_at, updated_at) "
            f"VALUES ({', '.join('?' * len(TRIP_COLUMNS))}, ?, ?)",
            (*(trip[c] for c in TRIP_COLUMNS), now, now),
        )
        self._write_legs(cur.lastrowid, trip["legs"])
        return cur.lastrowid

    def create_trip(self, trip: dict) -> dict:
        with self.lock, self.conn:
            trip_id = self._insert(trip)
        return self.get_trip(trip_id)

    def update_trip(self, trip_id: int, trip: dict):
        with self.lock, self.conn:
            cur = self.conn.execute(
                f"UPDATE trips SET {', '.join(c + ' = ?' for c in TRIP_COLUMNS)}, updated_at = ? "
                "WHERE id = ?",
                (*(trip[c] for c in TRIP_COLUMNS), now_iso(), trip_id),
            )
            if cur.rowcount:
                self._write_legs(trip_id, trip["legs"])
        return self.get_trip(trip_id) if cur.rowcount else None

    def delete_trip(self, trip_id: int) -> bool:
        with self.lock, self.conn:
            cur = self.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        return cur.rowcount > 0

    def import_trips(self, trips: list[dict]) -> int:
        with self.lock, self.conn:
            for trip in trips:
                self._insert(trip)
        return len(trips)


# ---------- HTTP ----------

class TravelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, db: Database, *, trust_proxy=False, cookie_secure="auto", cors_origins=None):
        super().__init__(address, Handler)
        self.db = db
        self.trust_proxy = trust_proxy
        self.cookie_secure = cookie_secure
        if cors_origins is None:
            cors_origins = os.environ.get("TRAVEL_CORS_ORIGINS", "https://localhost,capacitor://localhost").split(",")
        self.cors_origins = frozenset(origin.strip() for origin in cors_origins if origin.strip() and origin.strip() != "*")
        self._failures: dict[str, list[float]] = {}
        self._failures_lock = threading.Lock()

    # 在校验密码之前调用：名额已满返回 False；密码正确后由 clear_failures 清除。
    def record_failure(self, ip: str) -> bool:
        with self._failures_lock:
            now = time.time()
            recent = [t for t in self._failures.get(ip, []) if now - t < LOGIN_WINDOW]
            self._failures[ip] = recent
            if len(recent) >= LOGIN_MAX_FAILURES:
                return False
            recent.append(now)
            return True

    def clear_failures(self, ip: str):
        with self._failures_lock:
            self._failures.pop(ip, None)


class Handler(BaseHTTPRequestHandler):
    server: TravelServer
    server_version = "TravelLog/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        log.info("%s %s", self.client_ip(), fmt % args)

    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("GET", head_only=True)

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def do_OPTIONS(self):
        self.dispatch("OPTIONS")

    # --- 路由 ---

    def dispatch(self, method: str, head_only: bool = False):
        # 同一个 Handler 会在 keep-alive 连接上处理多个请求，每次都要重置状态
        self._head_only = head_only
        self._body_consumed = False
        path = unquote(urlparse(self.path).path)
        self._api_request = path.startswith("/api/")
        try:
            if self._api_request:
                self.handle_api(method, path)
            elif method == "GET":
                self.serve_static(path)
            else:
                raise ApiError(405, "不支持的请求方法")
        except ApiError as e:
            self.send_json(e.status, {"error": e.message})
        except Exception:
            log.exception("处理请求出错")
            self.send_json(500, {"error": "服务器内部错误"})

    def handle_api(self, method: str, path: str):
        db = self.server.db

        if method == "OPTIONS":
            if self.headers.get("Origin") not in self.server.cors_origins:
                raise ApiError(403, "来源不被允许")
            return self.send_bytes(204, b"", "application/json; charset=utf-8", {
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Max-Age": "600",
            })
        if path == "/api/meta" and method == "GET":
            return self.send_json(200, {"app": "travel-log", "api_version": API_VERSION, "server_version": SERVER_VERSION})
        if path == "/api/session" and method == "GET":
            return self.send_json(200, {"authenticated": self.current_token() is not None})
        if path == "/api/login" and method == "POST":
            return self.login()
        if path == "/api/tokens" and method == "POST":
            return self.issue_token()
        if path == "/api/logout" and method == "POST":
            return self.logout()

        credential = self.current_token()
        if credential is None:
            raise ApiError(401, "请先登录")

        if path == "/api/tokens/current" and method == "DELETE":
            if credential[0] != "token":
                raise ApiError(401, "请先登录")
            db.delete_session(credential[1], kind="token")
            return self.send_json(200, {"ok": True})

        if path == "/api/trips":
            if method == "GET":
                return self.send_json(200, {"trips": db.list_trips()})
            if method == "POST":
                trip = validate_trip(self.read_json())
                return self.send_json(201, {"trip": db.create_trip(trip)})

        match = re.fullmatch(r"/api/trips/(\d+)", path)
        if match:
            trip_id = int(match.group(1))
            if method == "PUT":
                trip = db.update_trip(trip_id, validate_trip(self.read_json()))
                if trip is None:
                    raise ApiError(404, "记录不存在")
                return self.send_json(200, {"trip": trip})
            if method == "DELETE":
                if not db.delete_trip(trip_id):
                    raise ApiError(404, "记录不存在")
                return self.send_json(200, {"ok": True})

        if path == "/api/export" and method == "GET":
            return self.export()
        if path == "/api/import" and method == "POST":
            return self.import_()

        raise ApiError(404, "接口不存在")

    # --- 登录 ---

    def login(self):
        self.authenticate_password()
        token = self.server.db.create_session()
        self.send_json(200, {"ok": True}, cookie=self.session_cookie(token, SESSION_TTL))

    def issue_token(self):
        data = self.authenticate_password()
        device_name = data.get("device_name", "")
        if not isinstance(device_name, str):
            raise ApiError(400, "设备名称必须是文本")
        device_name = device_name.strip()
        if len(device_name) > 50:
            raise ApiError(400, "设备名称最多 50 个字")
        token = self.server.db.create_session(kind="token", device_name=device_name)
        self.send_json(201, {"token": token, "token_type": "Bearer", "expires_in": TOKEN_TTL})

    def authenticate_password(self):
        # Web 与 App 共用密码检查和同一份失败计数。
        ip = self.client_ip()
        data = self.read_json()
        password = data.get("password") if isinstance(data, dict) else None
        stored = self.server.db.get_setting("password_hash")
        if not stored:
            raise ApiError(503, "尚未设置密码，请先在服务器上运行 python3 server.py set-password")
        # 先原子占用名额，避免并发请求越过限流后一起计算密码哈希。
        if not self.server.record_failure(ip):
            raise ApiError(429, "尝试次数过多，请 10 分钟后再试")
        if not isinstance(password, str) or not verify_password(password, stored):
            raise ApiError(401, "密码错误")
        self.server.clear_failures(ip)
        return data

    def logout(self):
        credential = self.current_token()
        if credential and credential[0] == "cookie":
            self.server.db.delete_session(credential[1])
        self.send_json(200, {"ok": True}, cookie=self.session_cookie("", 0))

    def current_token(self):
        authorization = self.headers.get_all("Authorization")
        if authorization is not None:
            # 只要带了此头，即使为空或无效，也不能回退到 Cookie。
            if len(authorization) != 1:
                return None
            match = re.fullmatch(r"Bearer ([A-Za-z0-9_-]+)", authorization[0])
            if not match:
                return None
            token = match.group(1)
            return ("token", token) if self.server.db.check_session(token, kind="token") else None
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            morsel = SimpleCookie(raw).get(SESSION_COOKIE)
        except CookieError:
            return None
        if morsel is None or not morsel.value:
            return None
        return ("cookie", morsel.value) if self.server.db.check_session(morsel.value) else None

    def session_cookie(self, value: str, max_age: int) -> str:
        parts = [f"{SESSION_COOKIE}={value}", "Path=/", f"Max-Age={max_age}", "HttpOnly", "SameSite=Strict"]
        mode = self.server.cookie_secure
        if mode == "always" or (
            mode == "auto" and self.headers.get("X-Forwarded-Proto", "").lower() == "https"
        ):
            parts.append("Secure")
        return "; ".join(parts)

    def client_ip(self) -> str:
        if self.server.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[-1].strip()
        return self.client_address[0]

    # --- 导入导出 ---

    def export(self):
        body = {
            "app": "travel-log",
            "version": 1,
            "exported_at": now_iso(),
            "trips": self.server.db.list_trips(),
        }
        filename = f"travel-log-{datetime.now():%Y%m%d}.json"
        self.send_json(200, body, extra={"Content-Disposition": f'attachment; filename="{filename}"'})

    def import_(self):
        data = self.read_json()
        trips = data.get("trips") if isinstance(data, dict) else data
        if not isinstance(trips, list):
            raise ApiError(400, "导入文件中没有找到 trips 列表")
        if len(trips) > MAX_IMPORT:
            raise ApiError(400, f"一次最多导入 {MAX_IMPORT} 条")
        valid = []
        for index, item in enumerate(trips, start=1):
            try:
                valid.append(validate_trip(item))
            except ApiError as e:
                raise ApiError(400, f"第 {index} 条：{e.message}") from None
        count = self.server.db.import_trips(valid)
        self.send_json(200, {"imported": count})

    # --- 底层 ---

    def read_json(self):
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(415, "请求必须是 JSON")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "Content-Length 无效") from None
        if length < 0 or length > MAX_BODY:
            raise ApiError(413, "请求内容过大")
        raw = self.rfile.read(length)
        self._body_consumed = True
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON 格式错误") from None

    def serve_static(self, path: str):
        if path == "/":
            path = "/index.html"
        elif path == "/favicon.ico":
            path = "/icons/icon-192.png"
        target = (STATIC_DIR / path.lstrip("/")).resolve()
        if STATIC_DIR not in target.parents or not target.is_file():
            raise ApiError(404, "页面不存在")
        content_type = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self.send_bytes(200, target.read_bytes(), content_type, {"Cache-Control": "no-cache"})

    def send_json(self, status: int, body, *, cookie: str | None = None, extra: dict | None = None):
        headers = {"Cache-Control": "no-store", **(extra or {})}
        if cookie:
            headers["Set-Cookie"] = cookie
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, data, "application/json; charset=utf-8", headers)

    def send_bytes(self, status: int, data: bytes, content_type: str, headers: dict):
        # 请求体没被读掉时不能复用连接，否则残留数据会被当成下一个请求
        try:
            has_body = int(self.headers.get("Content-Length", "0")) > 0
        except ValueError:
            has_body = True
        if has_body and not self._body_consumed:
            self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in {**SECURITY_HEADERS, **headers}.items():
            self.send_header(key, value)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if not self._head_only:
            self.wfile.write(data)

    def end_headers(self):
        # 内置处理器产生的错误响应也要遵守 API 的 CORS 规则。
        headers = getattr(self, "headers", None)
        origin = headers.get("Origin") if headers is not None else None
        if origin in self.server.cors_origins and unquote(urlparse(self.path).path).startswith("/api/"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        super().end_headers()


# ---------- 命令行 ----------

def read_new_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("新密码：")
    second = getpass.getpass("再输入一次：")
    if first != second:
        sys.exit("两次输入的密码不一致")
    return first


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=os.environ.get("TRAVEL_DB", str(DEFAULT_DB)),
                        help="SQLite 数据库路径（环境变量 TRAVEL_DB）")
    parser = argparse.ArgumentParser(description="旅行记录服务")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", parents=[common], help="启动服务（默认）")
    serve.add_argument("--host", default=os.environ.get("TRAVEL_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("TRAVEL_PORT", "8765")))
    sub.add_parser("set-password", parents=[common], help="设置或修改登录密码（所有设备需重新登录）")

    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv.insert(0, "serve")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    os.umask(0o077)  # 数据库及 WAL 文件只允许当前用户读写
    db = Database(Path(args.db).expanduser())

    if args.command == "set-password":
        password = read_new_password()
        if len(password) < MIN_PASSWORD_LEN:
            sys.exit(f"密码至少 {MIN_PASSWORD_LEN} 位")
        db.set_password(password)
        print("密码已设置。")
        return

    if not db.get_setting("password_hash"):
        sys.exit("还没有设置密码，请先运行：python3 server.py set-password")

    server = TravelServer(
        (args.host, args.port),
        db,
        trust_proxy=os.environ.get("TRAVEL_TRUST_PROXY") == "1",
        cookie_secure=os.environ.get("TRAVEL_COOKIE_SECURE", "auto"),
    )
    log.info("旅行记录已启动：http://%s:%d  数据库：%s", args.host, args.port, args.db)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        db.close()


if __name__ == "__main__":
    main()
