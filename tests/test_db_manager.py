from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from database.db_manager import DBManager


def _deal(thread_id: str = "123", price_monthly: float | None = 5.0, provider: str = "RackNerd") -> dict:
    return {
        "thread_id": thread_id,
        "title": f"Deal {thread_id}",
        "author": "author",
        "post_date": "2026-02-20",
        "fetch_date": "2026-02-20T10:00:00",
        "url": f"https://lowendtalk.com/discussion/{thread_id}/deal",
        "provider": provider,
        "category": "VPS",
        "cpu": 2,
        "ram_gb": 4,
        "storage_gb": 80,
        "storage_type": "NVMe",
        "bandwidth": 1024,
        "ipv4_count": 1,
        "ipv6": True,
        "price_monthly": price_monthly,
        "price_yearly": None,
        "location": "USA",
        "status": "NEW",
        "content_preview": "preview",
    }


def test_db_file_created_and_schema_initialized(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    manager = DBManager(db_path=db_path)
    assert db_path.exists()

    with manager.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"deals", "price_history", "providers"}.issubset(tables)


def test_upsert_inserts_then_updates_without_duplicates(tmp_path: Path):
    manager = DBManager(db_path=tmp_path / "deals.db")

    first = manager.upsert_deals([_deal(thread_id="100", price_monthly=5.0)])
    second = manager.upsert_deals([_deal(thread_id="100", price_monthly=5.0)])

    assert first["inserted"] == 1
    assert second["updated"] == 1

    with manager.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        assert count == 1


def test_price_history_tracks_changes(tmp_path: Path):
    manager = DBManager(db_path=tmp_path / "deals.db")
    manager.upsert_deals([_deal(thread_id="200", price_monthly=5.0)])
    manager.upsert_deals([_deal(thread_id="200", price_monthly=6.0)])

    history = manager.get_price_history(thread_id="200")
    assert len(history) == 2
    assert history[0]["price_monthly"] == 5.0
    assert history[1]["price_monthly"] == 6.0


def test_query_methods(tmp_path: Path):
    manager = DBManager(db_path=tmp_path / "deals.db")
    manager.upsert_deals([_deal(thread_id="301", provider="RackNerd"), _deal(thread_id="302", provider="HostHatch")])

    latest = manager.get_latest(limit=1)
    assert len(latest) == 1

    racknerd_rows = manager.get_by_provider("RackNerd")
    assert len(racknerd_rows) == 1
    assert racknerd_rows[0]["thread_id"] == "301"


def test_migration_support_adds_missing_columns(tmp_path: Path):
    db_path = tmp_path / "legacy.db"

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT)")
    conn.execute("CREATE TABLE providers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
    conn.execute("CREATE TABLE price_history (id INTEGER PRIMARY KEY AUTOINCREMENT, deal_id INTEGER, date_recorded TEXT)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    manager = DBManager(db_path=db_path)
    with manager.connect() as conn2:
        deal_cols = {r[1] for r in conn2.execute("PRAGMA table_info(deals)").fetchall()}
        provider_cols = {r[1] for r in conn2.execute("PRAGMA table_info(providers)").fetchall()}

    assert "deal_key" in deal_cols
    assert "raw_json" in deal_cols
    assert "reputation_score" in provider_cols


def test_price_history_requires_identifier(tmp_path: Path):
    manager = DBManager(db_path=tmp_path / "deals.db")
    with pytest.raises(ValueError):
        manager.get_price_history()
