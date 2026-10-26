-- 初始D1结构来自现有SQLite三个迁移；部署字段和限流表仅供Cloudflare使用。
PRAGMA foreign_keys=ON;
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
, kind TEXT NOT NULL DEFAULT 'cookie', device_name TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL DEFAULT 0, last_used_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE trip_legs (
            trip_id       INTEGER NOT NULL REFERENCES trips (id) ON DELETE CASCADE,
            seq           INTEGER NOT NULL,
            line          TEXT    NOT NULL DEFAULT '',
            vehicle_model TEXT    NOT NULL DEFAULT '',
            from_station  TEXT    NOT NULL DEFAULT '',
            to_station    TEXT    NOT NULL DEFAULT '',
            PRIMARY KEY (trip_id, seq)
        );
CREATE TABLE trips (
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
, network TEXT NOT NULL DEFAULT '', seat TEXT NOT NULL DEFAULT '', distance_km REAL NOT NULL DEFAULT 0);
CREATE INDEX idx_trips_depart ON trips (depart_at);
ALTER TABLE sessions ADD COLUMN password_epoch TEXT NOT NULL DEFAULT '';
ALTER TABLE trips ADD COLUMN write_batch TEXT NOT NULL DEFAULT '';
ALTER TABLE trips ADD COLUMN input_index INTEGER NOT NULL DEFAULT 0;
CREATE INDEX idx_trips_write_batch ON trips(write_batch,input_index);
CREATE TABLE login_failures(id INTEGER PRIMARY KEY,ip_hash TEXT NOT NULL,failed_at REAL NOT NULL);
CREATE INDEX idx_login_failures_ip ON login_failures(ip_hash,failed_at);
