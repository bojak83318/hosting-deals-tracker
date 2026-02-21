-- Schema v1
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_key TEXT NOT NULL UNIQUE,
    thread_id TEXT,
    url TEXT,
    title TEXT NOT NULL,
    author TEXT,
    provider TEXT,
    category TEXT,
    cpu INTEGER,
    ram_gb REAL,
    storage_gb REAL,
    storage_type TEXT,
    bandwidth INTEGER,
    ipv4_count INTEGER DEFAULT 1,
    ipv6 INTEGER DEFAULT 0,
    price_monthly REAL,
    price_yearly REAL,
    location TEXT,
    status TEXT,
    content_preview TEXT,
    date_posted TEXT,
    date_fetched TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deals_thread_id ON deals(thread_id);
CREATE INDEX IF NOT EXISTS idx_deals_provider ON deals(provider);
CREATE INDEX IF NOT EXISTS idx_deals_date_posted ON deals(date_posted);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    price_monthly REAL,
    price_yearly REAL,
    date_recorded TEXT NOT NULL,
    FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_deal_id ON price_history(deal_id);
CREATE INDEX IF NOT EXISTS idx_price_history_date_recorded ON price_history(date_recorded);

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    reputation_score REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_providers_category ON providers(category);
