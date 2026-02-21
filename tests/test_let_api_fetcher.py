from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import fetcher.let_api_fetcher as fetcher_module
from fetcher.let_api_fetcher import LETFetcher, RSS_URLS


def test_parse_rss_xml(fixture_bytes):
    fetcher = LETFetcher()
    rows = fetcher._parse_rss_xml(fixture_bytes("rss_sample.xml"), limit=10)
    assert len(rows) == 2
    assert rows[0]["thread_id"] == "12345"
    assert "RackNerd" in rows[0]["title"]


def test_fetch_rss_tries_alternatives_and_succeeds(monkeypatch, fixture_bytes):
    fetcher = LETFetcher()
    calls: list[str] = []

    class Resp:
        def __init__(self, code: int, content: bytes = b""):
            self.status_code = code
            self.content = content

    def fake_get(url: str, timeout: int = 30):
        calls.append(url)
        if url == RSS_URLS[0]:
            return Resp(404)
        if url == RSS_URLS[1]:
            return Resp(200, fixture_bytes("rss_sample.xml"))
        return Resp(500)

    monkeypatch.setattr(fetcher.session, "get", fake_get)
    rows = fetcher.fetch_rss(limit=10)

    assert len(rows) == 2
    assert calls[:2] == RSS_URLS[:2]


def test_fetch_rss_all_fail_returns_empty(monkeypatch):
    fetcher = LETFetcher()

    class Resp:
        def __init__(self, code: int):
            self.status_code = code
            self.content = b""

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp(404))
    rows = fetcher.fetch_rss(limit=10)
    assert rows == []


def test_fetch_discussion_page_parses_primary_markup(monkeypatch, fixture_text):
    fetcher = LETFetcher()

    class Resp:
        status_code = 200
        text = fixture_text("discussions_page.html")

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    rows = fetcher.fetch_discussion_page(page=1)
    assert len(rows) == 2
    assert rows[0]["thread_id"] == "12345"
    assert rows[0]["author"] == "RackNerd"


def test_fetch_discussion_page_fallback_anchor_parser(monkeypatch, fixture_text):
    fetcher = LETFetcher()

    class Resp:
        status_code = 200
        text = fixture_text("discussions_page_fallback.html")

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    rows = fetcher.fetch_discussion_page(page=1)
    assert len(rows) == 2
    assert {r["thread_id"] for r in rows} == {"11111", "22222"}


def test_fetch_discussion_page_malformed_returns_empty(monkeypatch, fixture_text):
    fetcher = LETFetcher()

    class Resp:
        status_code = 200
        text = fixture_text("malformed_page.html")

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    rows = fetcher.fetch_discussion_page(page=1)
    assert rows == []


def test_fetch_discussion_detail_extracts_content(monkeypatch, fixture_text):
    fetcher = LETFetcher()

    class Resp:
        status_code = 200
        text = fixture_text("discussion_detail.html")

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    detail = fetcher.fetch_discussion_detail("https://lowendtalk.com/discussion/12345/x")

    assert detail is not None
    assert detail["author"] == "OfferAuthor"
    assert "2 vCPU" in detail["content"]


@pytest.mark.parametrize(
    "title,content,expected",
    [
        (
            "RackNerd KVM VPS",
            "2 vCPU 4 GB RAM 80 GB NVMe 4 TB bandwidth 1 IPv4 + IPv6 USA $3.49/mo",
            {"cpu": 2, "ram_gb": 4, "storage_gb": 80, "storage_type": "NVMe", "bandwidth": 4096, "ipv6": True},
        ),
        (
            "Storage VPS",
            "1 core 1024 MB RAM 1 TB HDD 500 GB transfer Netherlands $30/yr",
            {"cpu": 1, "ram_gb": 1, "storage_gb": 1024, "storage_type": "HDD", "bandwidth": 500},
        ),
        (
            "Bare metal server",
            "quad core 16 GB memory 500 GB SSD Canada",
            {"cpu": 4, "ram_gb": 16, "storage_gb": 500, "location": "Canada"},
        ),
    ],
)
def test_extract_specs_various_formats(title: str, content: str, expected: dict[str, Any]):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(content, title)
    for key, value in expected.items():
        assert specs[key] == value


def test_determine_category_cases():
    fetcher = LETFetcher()
    assert fetcher.determine_category("kvm vps 2GB RAM", "Offer") == "VPS"
    assert fetcher.determine_category("bare metal server", "Offer") == "Dedicated"
    assert fetcher.determine_category("shared hosting with cpanel", "Offer") == "Shared"
    # Current rule order prioritizes VPS keywords before Storage.
    assert fetcher.determine_category("storage vps backup", "Offer") == "VPS"


def test_calculate_status_ranges():
    fetcher = LETFetcher()
    now = datetime.now()
    new_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    active_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    expired_date = (now - timedelta(days=40)).strftime("%Y-%m-%d")

    assert fetcher.calculate_status(new_date) == "NEW"
    assert fetcher.calculate_status(active_date) == "ACTIVE"
    assert fetcher.calculate_status(expired_date) == "EXPIRED"
    assert fetcher.calculate_status("") == "UNKNOWN"


def test_fetch_and_parse_deduplicates_urls(monkeypatch, sample_deals):
    fetcher = LETFetcher()

    monkeypatch.setattr(fetcher, "fetch_rss", lambda limit=50: sample_deals[:2])
    monkeypatch.setattr(fetcher, "fetch_discussion_page", lambda page=1: [sample_deals[1], sample_deals[2]])

    rows = fetcher.fetch_and_parse(pages=1, fetch_details=False)
    urls = [r["url"] for r in rows]

    assert len(rows) == 2
    assert len(set(urls)) == 2


def test_fetch_and_parse_with_details(monkeypatch):
    fetcher = LETFetcher()
    discussion = {
        "thread_id": "12345",
        "title": "RackNerd KVM VPS - 2 vCPU 4GB RAM",
        "url": "https://lowendtalk.com/discussion/12345/racknerd-offer",
        "author": "Unknown",
        "date": "2026-02-20T10:00:00+0000",
        "description": "fallback description",
    }

    monkeypatch.setattr(fetcher, "fetch_rss", lambda limit=50: [discussion])
    monkeypatch.setattr(fetcher, "fetch_discussion_page", lambda page=1: [])
    monkeypatch.setattr(
        fetcher,
        "fetch_discussion_detail",
        lambda url: {
            "content": "2 vCPU 4 GB RAM 80 GB NVMe 4 TB bandwidth in USA $3.49/mo",
            "author": "OfferAuthor",
            "date": "2026-02-20T10:00:00+0000",
        },
    )

    rows = fetcher.fetch_and_parse(pages=1, fetch_details=True)
    assert len(rows) == 1
    assert rows[0]["author"] == "OfferAuthor"
    assert rows[0]["cpu"] == 2


def test_save_deals_writes_json(tmp_path, monkeypatch):
    fetcher = LETFetcher()
    monkeypatch.setattr(fetcher_module, "DATA_DIR", tmp_path)
    output = fetcher.save_deals([{"thread_id": "1", "title": "x"}], filename="unit.json")
    assert output == tmp_path / "unit.json"
    assert output.exists()


def test_parse_rss_item_and_discussion_element_helpers(fixture_text):
    from bs4 import BeautifulSoup

    fetcher = LETFetcher()
    rss_soup = BeautifulSoup(
        "<item><title>A</title><link>https://lowendtalk.com/discussion/1/a</link>"
        "<description>B</description><pubDate>C</pubDate></item>",
        "html.parser",
    )
    parsed_item = fetcher._parse_rss_item(rss_soup.find("item"))
    assert parsed_item is not None
    assert parsed_item["title"] == "A"

    page_soup = BeautifulSoup(fixture_text("discussions_page.html"), "html.parser")
    li = page_soup.find("li")
    parsed_elem = fetcher._parse_discussion_element(li)
    assert parsed_elem is not None
    assert parsed_elem["thread_id"] == "12345"


def test_parse_helpers_error_paths():
    fetcher = LETFetcher()
    assert fetcher._parse_rss_item(None) is None
    assert fetcher._parse_discussion_element(None) is None
    assert fetcher._extract_thread_id("https://lowendtalk.com/no-discussion-path") is None


def test_fetch_discussion_page_handles_http_error(monkeypatch):
    fetcher = LETFetcher()

    class Resp:
        @staticmethod
        def raise_for_status():
            import requests

            raise requests.HTTPError("boom")

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    assert fetcher.fetch_discussion_page(1) == []


def test_fetch_discussion_detail_handles_http_error(monkeypatch):
    fetcher = LETFetcher()

    class Resp:
        @staticmethod
        def raise_for_status():
            import requests

            raise requests.HTTPError("boom")

    monkeypatch.setattr(fetcher.session, "get", lambda *args, **kwargs: Resp())
    assert fetcher.fetch_discussion_detail("https://lowendtalk.com/discussion/1/x") is None


def test_parse_rss_xml_handles_invalid_xml():
    fetcher = LETFetcher()
    assert fetcher._parse_rss_xml(b"not xml", limit=10) == []


def test_save_deals_default_filename(tmp_path, monkeypatch):
    fetcher = LETFetcher()
    monkeypatch.setattr(fetcher_module, "DATA_DIR", tmp_path)
    output = fetcher.save_deals([{"thread_id": "1"}], filename=None)
    assert output.exists()
    assert output.name.startswith("let_deals_")


def test_main_rss_only_and_since(monkeypatch, tmp_path):
    saved = {}

    class FakeFetcher:
        def fetch_rss(self, limit=100):
            return [
                {
                    "title": "Offer A",
                    "description": "2 vCPU 4 GB RAM",
                    "published": "Fri, 20 Feb 2026 10:00:00 +0000",
                    "post_date": "2026-02-20",
                },
                {
                    "title": "Offer B",
                    "description": "1 vCPU 1 GB RAM",
                    "published": "Fri, 10 Jan 2025 10:00:00 +0000",
                    "post_date": "2025-01-10",
                },
            ]

        def extract_specs(self, content, title):
            return {"cpu": 2 if "2 vCPU" in content else 1, "provider": None}

        def determine_category(self, content, title):
            return "VPS"

        def calculate_status(self, date_str):
            return "ACTIVE"

        def save_deals(self, deals, filename, persist_db=True):
            saved["deals"] = deals
            p = tmp_path / (filename or "out.json")
            p.write_text("[]", encoding="utf-8")
            return p

    monkeypatch.setattr(fetcher_module, "LETFetcher", FakeFetcher)
    monkeypatch.setattr(
        fetcher_module,
        "datetime",
        type(
            "DT",
            (),
            {
                "now": staticmethod(lambda: datetime(2026, 2, 20, 12, 0, 0)),
                "strptime": staticmethod(datetime.strptime),
                "fromisoformat": staticmethod(datetime.fromisoformat),
            },
        ),
    )
    monkeypatch.setattr(
        fetcher_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {"pages": 3, "details": False, "output": "out.json", "since": "2026-01-01", "rss_only": True, "no_db": True},
        )(),
    )

    fetcher_module.main()
    assert "deals" in saved
    assert len(saved["deals"]) == 1


def test_main_default_branch(monkeypatch, tmp_path):
    saved = {}

    class FakeFetcher:
        def fetch_and_parse(self, pages=3, fetch_details=False):
            return [{"title": "X", "post_date": "2026-02-20", "category": "VPS", "status": "NEW"}]

        def save_deals(self, deals, filename, persist_db=True):
            saved["deals"] = deals
            p = tmp_path / (filename or "out.json")
            p.write_text("[]", encoding="utf-8")
            return p

    monkeypatch.setattr(fetcher_module, "LETFetcher", FakeFetcher)
    monkeypatch.setattr(
        fetcher_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {"pages": 1, "details": False, "output": "out2.json", "since": None, "rss_only": False, "no_db": True},
        )(),
    )

    fetcher_module.main()
    assert len(saved["deals"]) == 1


@pytest.mark.parametrize(
    "text,expected_cpu",
    [
        ("2 core KVM", 2),
        ("2 vCPU plan", 2),
        ("Dual Core dedicated", 2),
        ("2x Intel Xeon", 2),
    ],
)
def test_edge_cpu_variations(text: str, expected_cpu: int):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "CPU Offer")
    assert specs["cpu"] == expected_cpu


@pytest.mark.parametrize(
    "text,expected_ram",
    [
        ("2GB RAM", 2),
        ("2 GB RAM", 2),
        ("2048MB RAM", 2),
        ("2G RAM", 2),
    ],
)
def test_edge_ram_variations(text: str, expected_ram: float):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "RAM Offer")
    assert specs["ram_gb"] == expected_ram


@pytest.mark.parametrize(
    "text,expected_storage,expected_type",
    [
        ("40GB SSD", 40, "SSD"),
        ("40 GB NVMe", 40, "NVMe"),
        ("40gb ssd", 40, "SSD"),
        ("40G storage", 40, "SSD"),
    ],
)
def test_edge_storage_variations(text: str, expected_storage: float, expected_type: str):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "Storage Offer")
    assert specs["storage_gb"] == expected_storage
    assert specs["storage_type"] == expected_type


@pytest.mark.parametrize(
    "text,monthly,yearly",
    [
        ("$10 monthly", 10.0, None),
        ("$10.99/mo", 10.99, None),
        ("€10/mo", 10.0, None),
        ("£10/mo", 10.0, None),
        ("10 USD/mo", 10.0, None),
        ("£120 yearly", None, 120.0),
        ("10 USD", 10.0, None),
    ],
)
def test_edge_price_variations(text: str, monthly: float | None, yearly: float | None):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "Price Offer")
    assert specs["price_monthly"] == monthly
    assert specs["price_yearly"] == yearly


@pytest.mark.parametrize(
    "text,expected_bandwidth",
    [
        ("1TB bandwidth", 1024),
        ("1000GB transfer", 1000),
        ("Unlimited transfer", -1),
        ("Unmetered bandwidth", -1),
    ],
)
def test_edge_bandwidth_variations(text: str, expected_bandwidth: int):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "Bandwidth Offer")
    assert specs["bandwidth"] == expected_bandwidth


@pytest.mark.parametrize(
    "text,expected_location",
    [
        ("US location", "USA"),
        ("USA datacenter", "USA"),
        ("United States region", "USA"),
        ("Los Angeles, CA node", "Los Angeles, CA"),
    ],
)
def test_edge_location_variations(text: str, expected_location: str):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "Location Offer")
    assert specs["location"] == expected_location


@pytest.mark.parametrize(
    "text",
    [
        "/64 subnet",
        "/48 delegation",
        "IPv6 enabled",
        "IPv6 /64 subnet",
    ],
)
def test_edge_ipv6_variations(text: str):
    fetcher = LETFetcher()
    specs = fetcher.extract_specs(text, "IPv6 Offer")
    assert specs["ipv6"] is True


def test_edge_case_fixture_blob(fixture_text):
    fetcher = LETFetcher()
    blob = fixture_text("edge_case_specs.txt")
    specs = fetcher.extract_specs(blob, "Edge case mixed offer")
    assert specs["cpu"] == 2
    assert specs["ram_gb"] == 2
    assert specs["storage_gb"] == 40
    assert specs["bandwidth"] == -1
    assert specs["ipv6"] is True
    assert specs["location"] == "Los Angeles, CA"
    assert specs["price_monthly"] == 10.0
