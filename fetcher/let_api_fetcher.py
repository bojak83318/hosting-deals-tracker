#!/usr/bin/env python3
"""
LowEndTalk API Fetcher - Power Query Replacement

Deterministic data fetching from LowEndTalk without browser automation.
Uses discovered API endpoints or RSS feeds for reliable data extraction.

This replaces Excel Power Query with a programmatic approach that:
- Fetches discussion data reliably
- Parses deal content with structured extraction
- Handles pagination automatically
- Outputs clean JSON for Excel/GitHub consumption

Usage:
    python let_api_fetcher.py --pages 5 --output deals.json
    python let_api_fetcher.py --since 2024-02-01 --category offers
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

try:
    from database.db_manager import DBManager
except Exception:  # pragma: no cover - optional in isolated usage
    DBManager = None

# Configuration
BASE_URL = "https://lowendtalk.com"
RSS_URLS = [
    f"{BASE_URL}/categories/discussions/feed.rss",
    f"{BASE_URL}/discussions/feed.rss",
    f"{BASE_URL}/categories/all/feed.rss",
    f"{BASE_URL}/feed.rss",
]
API_BASE = f"{BASE_URL}/api/v2"  # Common pattern, may need discovery

# Output directory
DATA_DIR = Path.home() / ".let-automation" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class LETFetcher:
    """Deterministic fetcher for LowEndTalk data."""
    
    # Regex patterns for spec extraction
    SPEC_PATTERNS = {
        "cpu": re.compile(
            r'(\d+)\s*vCPU|\b(dual|quad|hexa|octa)\s*core|\b(\d+)\s*core|\b(\d+)\s*x\s*(?:Intel|AMD|Xeon|EPYC)\b',
            re.I,
        ),
        "ram": re.compile(r'(\d+)\s*(GB|G|MB|M)\s*(RAM|memory)\b', re.I),
        "storage": re.compile(r'(\d+)\s*(GB|G|MB|M|TB|T)\s*(SSD|NVMe|HDD|storage|disk)\b', re.I),
        "bandwidth": re.compile(r'(\d+)\s*(GB|G|MB|M|TB|T)\s*(bandwidth|transfer)\b', re.I),
        "bandwidth_unmetered": re.compile(r'\b(unlimited|unmetered)\b', re.I),
        "ipv4": re.compile(r'(\d+)\s*IPv4|\b(\d+)\s*IP\s*address', re.I),
        "ipv6": re.compile(r'IPv6|IPv6 enabled|IPv6 /64 subnet|/64|/48', re.I),
        "price_monthly": re.compile(
            r'(?:(\$|€|£)\s*(\d+(?:\.\d+)?))\s*(?:/\s*month|/mo|\s*mo\b|\s*monthly)|'
            r'(\d+(?:\.\d+)?)\s*(USD|EUR|GBP)\s*(?:/\s*month|/mo|\s*mo\b|\s*monthly)',
            re.I,
        ),
        "price_yearly": re.compile(
            r'(?:(\$|€|£)\s*(\d+(?:\.\d+)?))\s*(?:/\s*year|/yr|\s*annually|\s*yearly)|'
            r'(\d+(?:\.\d+)?)\s*(USD|EUR|GBP)\s*(?:/\s*year|/yr|\s*annually|\s*yearly)',
            re.I,
        ),
        "price_generic": re.compile(r'(?:(\$|€|£)\s*(\d+(?:\.\d+)?))|((\d+(?:\.\d+)?)\s*(USD|EUR|GBP))', re.I),
        "location": re.compile(
            r'(USA|US|United States|UK|United Kingdom|Germany|Netherlands|Singapore|Japan|Australia|Canada|France|'
            r'Los Angeles,?\s*CA|New York,?\s*NY|Dallas,?\s*TX)',
            re.I,
        ),
    }
    
    # Known provider patterns
    PROVIDERS = [
        "RackNerd", "BuyVM", "VirMach", "GreenCloud", "Hetzner", "Contabo",
        "OVH", "Linode", "DigitalOcean", "Vultr", "BuyVM", "CloudCone",
        "LetBox", "Servarica", "HostHatch", "Wishosting", "PulsedMedia",
        "UltraVPS", "Wishosting", "SpeedyKVM", "HostSolutions", "Virtono"
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.discussions: list[dict] = []
    
    def fetch_rss(self, limit: int = 50) -> list[dict]:
        """Fetch discussions from RSS feed."""
        
        print("📡 Fetching RSS feed...")

        for rss_url in RSS_URLS:
            try:
                print(f"   Trying: {rss_url}")
                response = self.session.get(rss_url, timeout=30)
                if response.status_code != 200:
                    print(f"   RSS status {response.status_code} for {rss_url}")
                    continue

                discussions = self._parse_rss_xml(response.content, limit=limit)

                print(f"   Found {len(discussions)} discussions from RSS ({rss_url})")
                if discussions:
                    return discussions
            except Exception as e:
                print(f"   RSS fetch error for {rss_url}: {e}")
                continue

        print("   RSS fetch failed for all known feed URLs")
        return []

    def _parse_rss_xml(self, xml_bytes: bytes, limit: int = 50) -> list[dict]:
        discussions: list[dict] = []
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            print(f"   RSS parse error: {e}")
            return discussions

        # Handle namespaced and non-namespaced RSS item tags.
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{*}item")

        for item in items[:limit]:
            title = (item.findtext("title") or item.findtext("{*}title") or "").strip()
            url = (item.findtext("link") or item.findtext("{*}link") or "").strip()
            description = (item.findtext("description") or item.findtext("{*}description") or "").strip()
            published = (item.findtext("pubDate") or item.findtext("{*}pubDate") or "").strip() or None

            if not url and not title:
                continue

            discussions.append(
                {
                    "title": title,
                    "url": url,
                    "description": description,
                    "published": published,
                    "thread_id": self._extract_thread_id(url),
                    "author": "Unknown",
                }
            )
        return discussions
    
    def fetch_discussion_page(self, page: int = 1) -> list[dict]:
        """Fetch discussions from a listing page."""
        
        url = f"{BASE_URL}/discussions/p{page}"
        print(f"📡 Fetching page {page}: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find discussion items
            discussions = []
            discussion_elements = soup.find_all("li", class_=re.compile("ItemDiscussion|discussion", re.I))
            
            for elem in discussion_elements:
                discussion = self._parse_discussion_element(elem)
                if discussion:
                    discussions.append(discussion)

            # Fallback parser for changed LET markup: collect unique /discussion/<id>/ links.
            if not discussions:
                discussions.extend(self._parse_discussion_anchors(soup))
            
            print(f"   Found {len(discussions)} discussions")
            return discussions
            
        except Exception as e:
            print(f"   Error fetching page {page}: {e}")
            return []

    def _parse_discussion_anchors(self, soup: BeautifulSoup) -> list[dict]:
        """Fallback parser when list-item CSS classes change."""
        results: list[dict] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            if "/discussion/" not in href:
                continue

            url = urljoin(BASE_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = anchor.get_text(strip=True)
            if not title:
                continue

            results.append(
                {
                    "title": title,
                    "url": url,
                    "author": "Unknown",
                    "date": None,
                    "description": "",
                    "thread_id": self._extract_thread_id(url),
                }
            )
        return results
    
    def fetch_discussion_detail(self, url: str) -> dict | None:
        """Fetch full discussion content."""
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract main content
            content_elem = soup.find("div", class_=re.compile("Message|Comment"))
            if not content_elem:
                content_elem = soup.find("div", class_="Item-Body")
            
            content = content_elem.get_text(separator="\n", strip=True) if content_elem else ""
            
            # Extract author
            author_elem = soup.find("a", class_=re.compile("Username|Author"))
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"
            
            # Extract date
            time_elem = soup.find("time")
            date_str = time_elem.get("datetime") if time_elem else None
            
            return {
                "content": content,
                "author": author,
                "date": date_str,
            }
            
        except Exception as e:
            print(f"   Error fetching detail {url}: {e}")
            return None
    
    def extract_specs(self, content: str, title: str) -> dict[str, Any]:
        """Extract hosting specs from content using regex patterns."""
        
        text = f"{title} {content}"
        specs = {
            "cpu": None,
            "ram_gb": None,
            "storage_gb": None,
            "storage_type": None,
            "bandwidth": None,
            "ipv4_count": 1,
            "ipv6": False,
            "price_monthly": None,
            "price_yearly": None,
            "location": None,
            "provider": None,
        }
        
        # Extract CPU
        cpu_match = self.SPEC_PATTERNS["cpu"].search(text)
        if cpu_match:
            if cpu_match.group(1):
                specs["cpu"] = int(cpu_match.group(1))
            elif cpu_match.group(2):
                core_map = {"dual": 2, "quad": 4, "hexa": 6, "octa": 8}
                specs["cpu"] = core_map.get(cpu_match.group(2).lower(), 1)
            elif cpu_match.group(3):
                specs["cpu"] = int(cpu_match.group(3))
            elif cpu_match.group(4):
                specs["cpu"] = int(cpu_match.group(4))
        
        # Extract RAM
        ram_match = self.SPEC_PATTERNS["ram"].search(text)
        if ram_match:
            value = int(ram_match.group(1))
            unit = ram_match.group(2).upper()
            specs["ram_gb"] = value if unit in {"GB", "G"} else value / 1024
        
        # Extract Storage
        storage_match = self.SPEC_PATTERNS["storage"].search(text)
        if storage_match:
            value = int(storage_match.group(1))
            unit = storage_match.group(2).upper()
            type_raw = storage_match.group(3)
            type_match = type_raw.upper() if type_raw else "SSD"
            
            if unit in {"TB", "T"}:
                value *= 1024
            elif unit in {"MB", "M"}:
                value /= 1024
            
            specs["storage_gb"] = value
            if type_match == "NVME":
                specs["storage_type"] = "NVMe"
            else:
                specs["storage_type"] = type_match if type_match in ["SSD", "HDD"] else "SSD"
        
        # Extract Bandwidth
        bw_match = self.SPEC_PATTERNS["bandwidth"].search(text)
        if bw_match:
            value = int(bw_match.group(1))
            unit = bw_match.group(2).upper()
            if unit in {"TB", "T"}:
                value *= 1024
            elif unit in {"MB", "M"}:
                value /= 1024
            specs["bandwidth"] = value
        elif self.SPEC_PATTERNS["bandwidth_unmetered"].search(text):
            specs["bandwidth"] = -1
        
        # Extract IPv4
        ipv4_match = self.SPEC_PATTERNS["ipv4"].search(text)
        if ipv4_match:
            specs["ipv4_count"] = int(ipv4_match.group(1) or ipv4_match.group(2) or 1)
        
        # Check IPv6
        specs["ipv6"] = bool(self.SPEC_PATTERNS["ipv6"].search(text))
        
        # Extract Price
        price_monthly = self.SPEC_PATTERNS["price_monthly"].search(text)
        if price_monthly:
            specs["price_monthly"] = float(price_monthly.group(2) or price_monthly.group(3))
        
        price_yearly = self.SPEC_PATTERNS["price_yearly"].search(text)
        if price_yearly:
            specs["price_yearly"] = float(price_yearly.group(2) or price_yearly.group(3))

        # Fallback for plain prices without billing suffix.
        if specs["price_monthly"] is None and specs["price_yearly"] is None:
            price_generic = self.SPEC_PATTERNS["price_generic"].search(text)
            if price_generic:
                specs["price_monthly"] = float(price_generic.group(2) or price_generic.group(4))
        
        # Extract Location
        loc_match = self.SPEC_PATTERNS["location"].search(text)
        if loc_match:
            location = loc_match.group(1)
            normalized = {
                "US": "USA",
                "United States": "USA",
                "United Kingdom": "UK",
            }
            specs["location"] = normalized.get(location, location)
        
        # Detect Provider
        for provider in self.PROVIDERS:
            if provider.lower() in text.lower():
                specs["provider"] = provider
                break
        
        return specs
    
    def determine_category(self, content: str, title: str) -> str:
        """Determine product category from content."""
        
        text = (title + " " + content).lower()
        
        if any(word in text for word in ["dedicated", "dedi", "bare metal", "server"]) and "vps" not in text:
            return "Dedicated"
        elif any(word in text for word in ["vps", "kvm", "openvz", "lxc", "container"]):
            return "VPS"
        elif any(word in text for word in ["shared hosting", "web hosting", "cpanel"]):
            return "Shared"
        elif any(word in text for word in ["storage", "storage vps", "backup"]):
            return "Storage"
        elif any(word in text for word in ["reseller", "whm"]):
            return "Reseller"
        else:
            return "VPS"  # Default
    
    def calculate_status(self, date_str: str) -> str:
        """Calculate deal status based on age."""
        
        if not date_str:
            return "UNKNOWN"
        
        try:
            # Parse various date formats
            for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"]:
                try:
                    post_date = datetime.strptime(date_str[:19], fmt[:19])
                    break
                except ValueError:
                    continue
            else:
                return "UNKNOWN"
            
            age_days = (datetime.now() - post_date).days
            
            if age_days < 7:
                return "NEW"
            elif age_days < 30:
                return "ACTIVE"
            else:
                return "EXPIRED"
                
        except Exception:
            return "UNKNOWN"
    
    def fetch_and_parse(self, pages: int = 3, fetch_details: bool = False) -> list[dict]:
        """Main method: fetch and parse all discussions."""
        
        print(f"\n{'='*60}")
        print("🔍 LowEndTalk Deal Fetcher")
        print(f"{'='*60}")
        print(f"Pages to fetch: {pages}")
        print(f"Fetch details: {fetch_details}")
        print(f"{'='*60}\n")
        
        all_discussions = []
        
        # Try RSS first (faster)
        rss_discussions = self.fetch_rss(limit=50)
        all_discussions.extend(rss_discussions)
        
        # Then fetch pages
        for page in range(1, pages + 1):
            page_discussions = self.fetch_discussion_page(page)
            all_discussions.extend(page_discussions)
            time.sleep(1)  # Be nice to the server
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_discussions = []
        for d in all_discussions:
            if d.get("url") and d["url"] not in seen_urls:
                seen_urls.add(d["url"])
                unique_discussions.append(d)
        
        print(f"\n📊 Total unique discussions: {len(unique_discussions)}")
        
        # Enrich with details if requested
        parsed_deals = []
        for i, discussion in enumerate(unique_discussions, 1):
            print(f"\n[{i}/{len(unique_discussions)}] Processing: {discussion.get('title', 'Unknown')[:50]}...")
            
            # Fetch detail if needed
            detail = None
            if fetch_details and discussion.get("url"):
                detail = self.fetch_discussion_detail(discussion["url"])
                time.sleep(0.5)
            
            content = detail.get("content", "") if detail else discussion.get("description", "")
            
            # Extract specs
            specs = self.extract_specs(content, discussion.get("title", ""))
            
            # Determine category
            category = self.determine_category(content, discussion.get("title", ""))
            
            # Calculate status
            status = self.calculate_status(discussion.get("published") or discussion.get("date"))
            
            # Build final deal object
            deal = {
                "thread_id": discussion.get("thread_id") or self._extract_thread_id(discussion.get("url", "")),
                "title": discussion.get("title", ""),
                "author": detail.get("author") if detail else discussion.get("author", "Unknown"),
                "post_date": discussion.get("published") or discussion.get("date"),
                "fetch_date": datetime.now().isoformat(),
                "url": discussion.get("url", ""),
                "category": category,
                "status": status,
                "content_preview": content[:500] if content else "",
                **specs,
                "raw_content": content if fetch_details else None,
            }
            
            parsed_deals.append(deal)
            
            # Show extracted info
            print(f"   Provider: {specs.get('provider') or 'Unknown'}")
            print(f"   Category: {category}")
            print(f"   Price: ${specs.get('price_monthly') or specs.get('price_yearly')}/mo")
            print(f"   Specs: {specs.get('cpu')}vCPU, {specs.get('ram_gb')}GB RAM, {specs.get('storage_gb')}GB {specs.get('storage_type')}")
            print(f"   Status: {status}")
        
        return parsed_deals
    
    def _parse_rss_item(self, item) -> dict | None:
        """Parse an RSS item element."""
        
        try:
            title = item.find("title")
            title_text = title.get_text(strip=True) if title else ""
            
            link = item.find("link")
            url = link.get_text(strip=True) if link else ""
            
            description = item.find("description")
            desc_text = description.get_text(strip=True) if description else ""
            
            pub_date = item.find("pubDate")
            published = pub_date.get_text(strip=True) if pub_date else None
            
            # Extract thread ID from URL
            thread_id = self._extract_thread_id(url)
            
            return {
                "title": title_text,
                "url": url,
                "description": desc_text,
                "published": published,
                "thread_id": thread_id,
                "author": "Unknown",  # RSS often doesn't include author
            }
            
        except Exception as e:
            print(f"   Error parsing RSS item: {e}")
            return None
    
    def _parse_discussion_element(self, elem) -> dict | None:
        """Parse a discussion HTML element."""
        
        try:
            # Title and link
            title_elem = elem.find("a", class_="Title") or elem.find("h3").find("a") if elem.find("h3") else None
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            url = urljoin(BASE_URL, title_elem.get("href", ""))
            
            # Author
            author_elem = elem.find("a", class_="Username")
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"
            
            # Date
            time_elem = elem.find("time")
            date = time_elem.get("datetime") if time_elem else None
            
            # Preview
            preview_elem = elem.find("div", class_="Preview")
            preview = preview_elem.get_text(strip=True) if preview_elem else ""
            
            return {
                "title": title,
                "url": url,
                "author": author,
                "date": date,
                "description": preview,
                "thread_id": self._extract_thread_id(url),
            }
            
        except Exception as e:
            return None
    
    def _extract_thread_id(self, url: str) -> str | None:
        """Extract thread ID from URL."""
        
        match = re.search(r'/discussion/(\d+)', url)
        return match.group(1) if match else None
    
    def save_deals(self, deals: list[dict], filename: str | None = None, persist_db: bool = True) -> Path:
        """Save deals to JSON file."""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"let_deals_{timestamp}.json"
        
        output_path = DATA_DIR / filename
        output_path.write_text(json.dumps(deals, indent=2, default=str))
        
        print(f"\n💾 Saved {len(deals)} deals to: {output_path}")

        if persist_db and DBManager is not None:
            try:
                stats = DBManager().upsert_deals(deals)
                print(
                    "🗄️  DB upsert: "
                    f"{stats['inserted']} inserted, {stats['updated']} updated, {stats['price_history_added']} history"
                )
            except Exception as e:
                print(f"   DB upsert skipped due to error: {e}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="Fetch LowEndTalk deals")
    parser.add_argument("--pages", "-p", type=int, default=3, help="Number of pages to fetch")
    parser.add_argument("--details", "-d", action="store_true", help="Fetch full discussion content")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--since", "-s", help="Only fetch deals since date (YYYY-MM-DD)")
    parser.add_argument("--rss-only", action="store_true", help="Only use RSS feed")
    parser.add_argument("--no-db", action="store_true", help="Skip SQLite upsert when saving")
    
    args = parser.parse_args()
    
    fetcher = LETFetcher()
    
    if args.rss_only:
        deals = fetcher.fetch_rss(limit=100)
        # Parse basic info for RSS items
        parsed = []
        for d in deals:
            specs = fetcher.extract_specs(d.get("description", ""), d.get("title", ""))
            category = fetcher.determine_category(d.get("description", ""), d.get("title", ""))
            status = fetcher.calculate_status(d.get("published"))
            parsed.append({
                **d,
                **specs,
                "category": category,
                "status": status,
                "fetch_date": datetime.now().isoformat(),
            })
        deals = parsed
    else:
        deals = fetcher.fetch_and_parse(pages=args.pages, fetch_details=args.details)
    
    # Filter by date if specified
    if args.since:
        since_date = datetime.strptime(args.since, "%Y-%m-%d")
        deals = [
            d for d in deals 
            if d.get("post_date") and datetime.fromisoformat(d["post_date"][:10]) >= since_date
        ]
        print(f"\n📅 Filtered to {len(deals)} deals since {args.since}")
    
    # Save
    output_path = fetcher.save_deals(deals, args.output, persist_db=not args.no_db)
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 FETCH SUMMARY")
    print(f"{'='*60}")
    print(f"Total deals: {len(deals)}")
    
    # Category breakdown
    categories = {}
    for d in deals:
        cat = d.get("category", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1
    print(f"\nBy Category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    # Provider breakdown
    providers = {}
    for d in deals:
        prov = d.get("provider") or "Unknown"
        providers[prov] = providers.get(prov, 0) + 1
    print(f"\nBy Provider:")
    for prov, count in sorted(providers.items(), key=lambda x: -x[1])[:10]:
        print(f"  {prov}: {count}")
    
    # Status breakdown
    statuses = {}
    for d in deals:
        status = d.get("status", "Unknown")
        statuses[status] = statuses.get(status, 0) + 1
    print(f"\nBy Status:")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")
    
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    main()
