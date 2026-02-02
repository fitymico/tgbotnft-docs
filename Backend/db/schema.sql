CREATE TABLE IF NOT EXISTS frontends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT UNIQUE NOT NULL,
    telegram_id INTEGER,
    udp_host TEXT,
    udp_port INTEGER,
    registered_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS seen_gifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gift_id TEXT UNIQUE NOT NULL,
    first_seen_at TEXT DEFAULT (datetime('now'))
);
