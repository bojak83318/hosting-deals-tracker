from __future__ import annotations

from pathlib import Path

from web.app import create_app
from database.db_manager import DBManager


def _seed(db_path: Path):
    m = DBManager(db_path=db_path)
    m.upsert_deals([
        {
            "thread_id": "901",
            "title": "RackNerd KVM VPS",
            "author": "author",
            "post_date": "2026-02-20",
            "fetch_date": "2026-02-20T10:00:00",
            "url": "https://lowendtalk.com/discussion/901/racknerd",
            "provider": "RackNerd",
            "category": "VPS",
            "cpu": 2,
            "ram_gb": 4,
            "storage_gb": 80,
            "storage_type": "NVMe",
            "bandwidth": 1024,
            "ipv4_count": 1,
            "ipv6": True,
            "price_monthly": 3.49,
            "price_yearly": None,
            "location": "USA",
            "status": "NEW",
            "content_preview": "great",
        },
        {
            "thread_id": "902",
            "title": "HostHatch Storage",
            "author": "author",
            "post_date": "2026-02-19",
            "fetch_date": "2026-02-19T09:00:00",
            "url": "https://lowendtalk.com/discussion/902/hosthatch",
            "provider": "HostHatch",
            "category": "Storage",
            "cpu": 1,
            "ram_gb": 2,
            "storage_gb": 1024,
            "storage_type": "HDD",
            "bandwidth": -1,
            "ipv4_count": 1,
            "ipv6": True,
            "price_monthly": 7.0,
            "price_yearly": None,
            "location": "Netherlands",
            "status": "ACTIVE",
            "content_preview": "storage",
        },
    ])


def test_index_route(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    _seed(db_path)
    app = create_app(db_path=db_path)
    client = app.test_client()

    r = client.get("/")
    assert r.status_code == 200
    assert b"Deals Dashboard" in r.data
    assert b"RackNerd" in r.data


def test_deal_detail_route(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    _seed(db_path)
    app = create_app(db_path=db_path)
    client = app.test_client()

    deal_id = DBManager(db_path=db_path).get_latest(limit=1)[0]["id"]
    r = client.get(f"/deal/{deal_id}")
    assert r.status_code == 200
    assert b"Price History" in r.data


def test_provider_route(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    _seed(db_path)
    app = create_app(db_path=db_path)
    client = app.test_client()

    r = client.get("/provider/RackNerd")
    assert r.status_code == 200
    assert b"RackNerd" in r.data


def test_api_deals_route(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    _seed(db_path)
    app = create_app(db_path=db_path)
    client = app.test_client()

    r = client.get("/api/deals")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["total"] >= 2
    assert isinstance(payload["items"], list)


def test_api_filters_search_sort(tmp_path: Path):
    db_path = tmp_path / "deals.db"
    _seed(db_path)
    app = create_app(db_path=db_path)
    client = app.test_client()

    r = client.get("/api/deals?q=RackNerd&sort=price_desc&price_min=1&price_max=5")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["total"] >= 1
    assert any("RackNerd" in (item.get("provider") or "") for item in payload["items"])
