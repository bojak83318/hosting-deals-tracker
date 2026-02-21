#!/usr/bin/env python3
"""Extract normalized LET deals from spectral discovery output."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency in some environments
    yaml = None

SPECTRAL_OUTPUT_ROOT = Path.home() / ".spectral-nodriver" / "output"
SPECTRAL_CAPTURE_ROOT = Path.home() / ".spectral-nodriver" / "captures"
SPECTRAL_COOKIE_FILE = Path.home() / ".spectral-nodriver" / "cookies" / "lowendtalk_com_cookies.json"
DEFAULT_OUTPUT_JSON = Path.home() / ".let-automation" / "data" / "spectral_deals.json"


class LocalSpecExtractor:
    """Local copy of LET spec extraction logic without BS4 dependency."""

    SPEC_PATTERNS = {
        "cpu": re.compile(r"(\d+)\s*vCPU|\b(dual|quad|hexa|octa)\s*core|\b(\d+)\s*core", re.I),
        "ram": re.compile(r"(\d+)\s*(GB|MB)\s*(RAM|memory)", re.I),
        "storage": re.compile(r"(\d+)\s*(GB|MB|TB)\s*(SSD|NVMe|HDD|storage)", re.I),
        "bandwidth": re.compile(r"(\d+)\s*(GB|MB|TB)\s*(bandwidth|transfer)", re.I),
        "ipv4": re.compile(r"(\d+)\s*IPv4|\b(\d+)\s*IP\s*address", re.I),
        "ipv6": re.compile(r"IPv6|/64|/48", re.I),
        "price_monthly": re.compile(r"\$(\d+\.?\d*)\s*/\s*month|\$(\d+\.?\d*)\s*mo", re.I),
        "price_yearly": re.compile(r"\$(\d+\.?\d*)\s*/\s*year|\$(\d+\.?\d*)\s*yr|\$(\d+\.?\d*)\s*annually", re.I),
        "location": re.compile(r"(USA|UK|Germany|Netherlands|Singapore|Japan|Australia|Canada|France)", re.I),
    }
    PROVIDERS = [
        "RackNerd", "BuyVM", "VirMach", "GreenCloud", "Hetzner", "Contabo",
        "OVH", "Linode", "DigitalOcean", "Vultr", "CloudCone",
        "LetBox", "Servarica", "HostHatch", "Wishosting", "PulsedMedia",
        "UltraVPS", "SpeedyKVM", "HostSolutions", "Virtono",
    ]

    def extract_specs(self, content: str, title: str) -> dict[str, Any]:
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
        cpu_match = self.SPEC_PATTERNS["cpu"].search(text)
        if cpu_match:
            if cpu_match.group(1):
                specs["cpu"] = int(cpu_match.group(1))
            elif cpu_match.group(2):
                specs["cpu"] = {"dual": 2, "quad": 4, "hexa": 6, "octa": 8}.get(cpu_match.group(2).lower(), 1)
            elif cpu_match.group(3):
                specs["cpu"] = int(cpu_match.group(3))

        ram_match = self.SPEC_PATTERNS["ram"].search(text)
        if ram_match:
            value = int(ram_match.group(1))
            specs["ram_gb"] = value if ram_match.group(2).upper() == "GB" else value / 1024

        storage_match = self.SPEC_PATTERNS["storage"].search(text)
        if storage_match:
            value = int(storage_match.group(1))
            unit = storage_match.group(2).upper()
            kind = storage_match.group(3).upper()
            if unit == "TB":
                value *= 1024
            elif unit == "MB":
                value /= 1024
            specs["storage_gb"] = value
            if kind == "NVME":
                kind = "NVMe"
            specs["storage_type"] = kind if kind in ["SSD", "NVMe", "HDD"] else "SSD"

        bw_match = self.SPEC_PATTERNS["bandwidth"].search(text)
        if bw_match:
            value = int(bw_match.group(1))
            unit = bw_match.group(2).upper()
            if unit == "TB":
                value *= 1024
            specs["bandwidth"] = value

        ipv4_match = self.SPEC_PATTERNS["ipv4"].search(text)
        if ipv4_match:
            specs["ipv4_count"] = int(ipv4_match.group(1) or ipv4_match.group(2) or 1)
        specs["ipv6"] = bool(self.SPEC_PATTERNS["ipv6"].search(text))

        monthly = self.SPEC_PATTERNS["price_monthly"].search(text)
        if monthly:
            specs["price_monthly"] = float(monthly.group(1) or monthly.group(2))
        yearly = self.SPEC_PATTERNS["price_yearly"].search(text)
        if yearly:
            specs["price_yearly"] = float(yearly.group(1) or yearly.group(2) or yearly.group(3))

        loc_match = self.SPEC_PATTERNS["location"].search(text)
        if loc_match:
            specs["location"] = loc_match.group(1)

        for provider in self.PROVIDERS:
            if provider.lower() in text.lower():
                specs["provider"] = provider
                break
        return specs

    def determine_category(self, content: str, title: str) -> str:
        text = (title + " " + content).lower()
        if any(word in text for word in ["dedicated", "dedi", "bare metal", "server"]) and "vps" not in text:
            return "Dedicated"
        if any(word in text for word in ["vps", "kvm", "openvz", "lxc", "container"]):
            return "VPS"
        if any(word in text for word in ["shared hosting", "web hosting", "cpanel"]):
            return "Shared"
        if any(word in text for word in ["storage", "storage vps", "backup"]):
            return "Storage"
        if any(word in text for word in ["reseller", "whm"]):
            return "Reseller"
        return "VPS"

    def calculate_status(self, date_str: str) -> str:
        if not date_str:
            return "ACTIVE"
        try:
            for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"]:
                try:
                    post_date = datetime.strptime(date_str[:19], fmt[:19])
                    break
                except ValueError:
                    continue
            else:
                return "ACTIVE"
            age_days = (datetime.now() - post_date).days
            if age_days < 7:
                return "NEW"
            if age_days < 30:
                return "ACTIVE"
            return "EXPIRED"
        except Exception:
            return "ACTIVE"


class SpectralDealsExtractor:
    """Extract deal rows from spectral-generated artifacts."""

    def __init__(
        self,
        output_dir: Path | None = None,
        stale_hours: int = 24,
        request_delay: float = 0.25,
    ):
        self.output_dir = output_dir or self.find_latest_output_dir()
        self.stale_hours = stale_hours
        self.request_delay = request_delay
        self.spec_extractor = LocalSpecExtractor()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        self._load_cookies()

    @staticmethod
    def find_latest_output_dir() -> Path | None:
        if not SPECTRAL_OUTPUT_ROOT.exists():
            return None
        candidates = sorted(
            SPECTRAL_OUTPUT_ROOT.glob("lowendtalk_com_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def output_is_stale(self) -> bool:
        if not self.output_dir or not self.output_dir.exists():
            return True
        age = datetime.now() - datetime.fromtimestamp(self.output_dir.stat().st_mtime)
        return age > timedelta(hours=self.stale_hours)

    def extract(self, limit: int = 200) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        metadata: dict[str, Any] = {
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "stale": self.output_is_stale(),
            "source": None,
            "warnings": [],
            "errors": [],
        }

        if metadata["stale"]:
            metadata["warnings"].append(
                f"Spectral capture appears stale (> {self.stale_hours}h)."
            )

        if self.output_dir and self.output_dir.exists():
            strategies = [
                ("generated_client", self._extract_from_generated_client),
                ("openapi_spec", self._extract_from_openapi),
            ]
            for source, strategy in strategies:
                try:
                    deals = strategy(limit=limit)
                    if deals:
                        metadata["source"] = source
                        return self._dedupe_and_limit(deals, limit), metadata
                    metadata["warnings"].append(f"{source} returned zero rows")
                except Exception as exc:
                    metadata["errors"].append(f"{source} failed: {exc}")

        try:
            deals = self._extract_from_capture_json(limit=limit)
            if deals:
                metadata["source"] = "captured_json"
                return self._dedupe_and_limit(deals, limit), metadata
            metadata["warnings"].append("captured_json returned zero rows")
        except Exception as exc:
            metadata["errors"].append(f"captured_json failed: {exc}")

        return [], metadata

    def save(self, deals: list[dict[str, Any]], output_file: Path | None = None) -> Path:
        output_file = output_file or DEFAULT_OUTPUT_JSON
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(deals, indent=2, ensure_ascii=True, default=str))
        return output_file

    def _load_cookies(self) -> None:
        if not SPECTRAL_COOKIE_FILE.exists():
            return
        try:
            cookies = json.loads(SPECTRAL_COOKIE_FILE.read_text())
            for cookie in cookies:
                self.session.cookies.set(
                    cookie.get("name", ""),
                    cookie.get("value", ""),
                    domain=cookie.get("domain", ""),
                    path=cookie.get("path", "/"),
                )
        except Exception:
            return

    def _extract_from_generated_client(self, limit: int = 200) -> list[dict[str, Any]]:
        client_file = self._find_client_file()
        if not client_file:
            return []

        module = self._import_module_from_path(client_file)
        client = self._instantiate_generated_client(module)
        if client is None:
            return []

        paths = self._discover_paths()
        discussion_rows = self._fetch_discussions_via_client(client, paths)

        deals: list[dict[str, Any]] = []
        for item in discussion_rows:
            detail_payload = self._fetch_detail_via_client(client, item, paths)
            comments_payload = self._fetch_comments_via_client(client, item, paths)
            deals.append(self._to_deal_row(item, detail_payload, comments_payload))
            if len(deals) >= limit:
                break
            time.sleep(self.request_delay)
        return deals

    def _extract_from_openapi(self, limit: int = 200) -> list[dict[str, Any]]:
        spec = self._load_spec_yaml()
        if not spec:
            return []

        base_url = self._get_base_url(spec)
        paths = self._discover_paths(spec)
        if not paths["discussions"]:
            return []

        discussions_payload = self._request_json(base_url, paths["discussions"][0])
        discussion_rows = self._extract_discussion_items(discussions_payload)

        deals: list[dict[str, Any]] = []
        for item in discussion_rows:
            detail_payload = self._fetch_detail_via_http(base_url, item, paths)
            comments_payload = self._fetch_comments_via_http(base_url, item, paths)
            deals.append(self._to_deal_row(item, detail_payload, comments_payload))
            if len(deals) >= limit:
                break
            time.sleep(self.request_delay)
        return deals

    def _extract_from_capture_json(self, limit: int = 200) -> list[dict[str, Any]]:
        if not SPECTRAL_CAPTURE_ROOT.exists():
            return []

        archives = sorted(
            SPECTRAL_CAPTURE_ROOT.glob("lowendtalk_com_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        deals: list[dict[str, Any]] = []

        for archive in archives[:3]:
            with zipfile.ZipFile(archive, "r") as zf:
                for member in zf.namelist():
                    if not member.lower().endswith((".json", ".har")):
                        continue
                    try:
                        payload = json.loads(zf.read(member).decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    discussion_rows = self._extract_discussion_items(payload)
                    for item in discussion_rows:
                        deals.append(self._to_deal_row(item, payload, None))
                        if len(deals) >= limit:
                            return deals
        return deals

    def _find_client_file(self) -> Path | None:
        if not self.output_dir:
            return None
        matches = sorted(self.output_dir.glob("*_automation.py"))
        return matches[0] if matches else None

    def _import_module_from_path(self, path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        if not spec or not spec.loader:
            raise RuntimeError(f"Cannot import generated module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _instantiate_generated_client(self, module):
        class_name = None
        for name in dir(module):
            if name.endswith("Client"):
                class_name = name
                break
        if not class_name:
            return None

        client_cls = getattr(module, class_name)
        try:
            return client_cls()
        except TypeError:
            spec = self._load_spec_yaml()
            base_url = self._get_base_url(spec) if spec else "https://lowendtalk.com"
            return client_cls(base_url=base_url)

    def _load_spec_yaml(self) -> dict[str, Any] | None:
        if not yaml or not self.output_dir:
            return None
        spec_file = self.output_dir / "api.yaml"
        if not spec_file.exists():
            return None
        return yaml.safe_load(spec_file.read_text()) or {}

    def _get_base_url(self, spec: dict[str, Any] | None) -> str:
        if not spec:
            return "https://lowendtalk.com"
        servers = spec.get("servers") or []
        if servers and isinstance(servers[0], dict):
            return servers[0].get("url", "https://lowendtalk.com").rstrip("/")
        return "https://lowendtalk.com"

    def _discover_paths(self, spec: dict[str, Any] | None = None) -> dict[str, list[str]]:
        spec = spec or self._load_spec_yaml() or {}
        paths = spec.get("paths", {}) if isinstance(spec, dict) else {}

        discovered = {
            "discussions": [],
            "discussion_detail": [],
            "comments": [],
        }

        for path, methods in paths.items():
            if not isinstance(methods, dict) or "get" not in methods:
                continue
            lower = path.lower()
            if "discussion" in lower and "{" not in lower and "comment" not in lower:
                discovered["discussions"].append(path)
            if "discussion" in lower and "{" in lower:
                discovered["discussion_detail"].append(path)
            if "comment" in lower:
                discovered["comments"].append(path)

        # explicit preference order
        discovered["discussions"] = self._prefer_paths(
            discovered["discussions"],
            ["/discussions", "/api/v2/discussions", "/api/discussions"],
        )
        discovered["discussion_detail"] = self._prefer_paths(
            discovered["discussion_detail"],
            ["/discussion/{id}", "/discussions/{id}", "/api/v2/discussions/{id}"],
        )
        discovered["comments"] = self._prefer_paths(
            discovered["comments"],
            ["/comments", "/discussion/{id}/comments", "/api/v2/comments"],
        )
        return discovered

    def _prefer_paths(self, paths: list[str], preferred: list[str]) -> list[str]:
        ranked = []
        for pref in preferred:
            for path in paths:
                if path == pref and path not in ranked:
                    ranked.append(path)
        for path in paths:
            if path not in ranked:
                ranked.append(path)
        return ranked

    def _fetch_discussions_via_client(self, client, paths: dict[str, list[str]]) -> list[dict[str, Any]]:
        method_candidates = ["get_discussions", "list_discussions", "discussions", "get"]
        for name in method_candidates:
            if not hasattr(client, name):
                continue
            method = getattr(client, name)
            try:
                if name == "get":
                    for path in paths["discussions"]:
                        payload = method(path)
                        rows = self._extract_discussion_items(payload)
                        if rows:
                            return rows
                else:
                    payload = method()
                    rows = self._extract_discussion_items(payload)
                    if rows:
                        return rows
            except Exception:
                continue
        return []

    def _fetch_detail_via_client(self, client, item: dict[str, Any], paths: dict[str, list[str]]) -> Any:
        discussion_id = self._extract_discussion_id(item)
        if not discussion_id:
            return None

        if hasattr(client, "get_discussion"):
            try:
                return getattr(client, "get_discussion")(discussion_id)
            except Exception:
                pass

        if hasattr(client, "get"):
            for template in paths["discussion_detail"]:
                path = self._fill_path_params(template, discussion_id)
                try:
                    return getattr(client, "get")(path)
                except Exception:
                    continue
        return None

    def _fetch_comments_via_client(self, client, item: dict[str, Any], paths: dict[str, list[str]]) -> Any:
        discussion_id = self._extract_discussion_id(item)
        if not discussion_id:
            return None

        if hasattr(client, "get_comments"):
            try:
                return getattr(client, "get_comments")()
            except Exception:
                pass

        if hasattr(client, "get"):
            for template in paths["comments"]:
                path = self._fill_path_params(template, discussion_id)
                try:
                    return getattr(client, "get")(path)
                except Exception:
                    continue
        return None

    def _fetch_detail_via_http(self, base_url: str, item: dict[str, Any], paths: dict[str, list[str]]) -> Any:
        discussion_id = self._extract_discussion_id(item)
        if not discussion_id:
            return None
        for template in paths["discussion_detail"]:
            path = self._fill_path_params(template, discussion_id)
            try:
                return self._request_json(base_url, path)
            except Exception:
                continue
        return None

    def _fetch_comments_via_http(self, base_url: str, item: dict[str, Any], paths: dict[str, list[str]]) -> Any:
        discussion_id = self._extract_discussion_id(item)
        if not discussion_id:
            return None
        for template in paths["comments"]:
            path = self._fill_path_params(template, discussion_id)
            try:
                return self._request_json(base_url, path)
            except Exception:
                continue
        return None

    def _fill_path_params(self, template: str, discussion_id: str) -> str:
        path = template
        for token in ["id", "discussion_id", "discussionId", "discussionID"]:
            path = path.replace(f"{{{token}}}", str(discussion_id))
        if "{" in path and "}" in path:
            # unresolved placeholders: fallback to simple comments endpoint
            path = re.sub(r"\{[^}]+\}", str(discussion_id), path)
        return path

    def _request_json(self, base_url: str, path: str, retries: int = 3) -> Any:
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)

                # Rate limiting support
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else (attempt + 1) * 2
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                if not response.content:
                    return None
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep((attempt + 1) * 1.5)
                continue

        if last_error:
            raise last_error
        return None

    def _extract_discussion_items(self, payload: Any) -> list[dict[str, Any]]:
        payload = self._normalize_payload(payload)
        rows: list[dict[str, Any]] = []

        def walk(node: Any):
            if isinstance(node, list):
                for child in node:
                    walk(child)
                return
            if not isinstance(node, dict):
                return

            if self._looks_like_discussion(node):
                rows.append(node)

            for value in node.values():
                if isinstance(value, (list, dict)):
                    walk(value)

        walk(payload)
        return rows

    def _normalize_payload(self, payload: Any) -> Any:
        if hasattr(payload, "json"):
            try:
                return payload.json()
            except Exception:
                return payload
        return payload

    def _looks_like_discussion(self, item: dict[str, Any]) -> bool:
        keys = {k.lower() for k in item.keys()}
        has_id = any(k in keys for k in ["id", "discussionid", "discussion_id", "thread_id"])
        has_title = any(k in keys for k in ["title", "name", "discussiontitle"])
        return has_id and has_title

    def _extract_discussion_id(self, item: dict[str, Any]) -> str | None:
        for key in ["thread_id", "discussionID", "discussionId", "discussion_id", "id"]:
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value)

        for key in ["url", "Url", "link"]:
            value = item.get(key)
            if isinstance(value, str):
                match = re.search(r"/discussion/(\d+)", value)
                if match:
                    return match.group(1)
        return None

    def _pick_text(self, data: Any, keys: list[str]) -> str:
        if isinstance(data, dict):
            for key in keys:
                if key in data and data[key] not in (None, ""):
                    return str(data[key])
            for key in data:
                val = data[key]
                if isinstance(val, (dict, list)):
                    hit = self._pick_text(val, keys)
                    if hit:
                        return hit
        elif isinstance(data, list):
            for item in data:
                hit = self._pick_text(item, keys)
                if hit:
                    return hit
        return ""

    def _to_deal_row(self, discussion: dict[str, Any], detail_payload: Any, comments_payload: Any) -> dict[str, Any]:
        discussion_id = self._extract_discussion_id(discussion)
        title = self._pick_text(discussion, ["title", "name", "discussionTitle"]) or ""
        author = (
            self._pick_text(discussion, ["author", "insertUser", "username", "createdBy"])
            or self._pick_text(detail_payload, ["author", "insertUser", "username", "createdBy"])
            or "Unknown"
        )
        post_date = (
            self._pick_text(discussion, ["dateInserted", "post_date", "createdAt", "published", "date"])
            or self._pick_text(detail_payload, ["dateInserted", "createdAt", "published", "date"])
        )

        url = (
            self._pick_text(discussion, ["url", "Url", "link"])
            or (f"https://lowendtalk.com/discussion/{discussion_id}" if discussion_id else "")
        )

        detail_text = self._pick_text(detail_payload, ["body", "message", "content", "excerpt", "text"])
        comments_text = self._pick_text(comments_payload, ["body", "message", "content", "text"])
        content = detail_text or comments_text or self._pick_text(discussion, ["body", "excerpt", "content", "text"])

        specs = self.spec_extractor.extract_specs(content, title)
        category = self.spec_extractor.determine_category(content, title)
        status = self._normalize_status(self.spec_extractor.calculate_status(post_date))

        return {
            "thread_id": str(discussion_id) if discussion_id else "",
            "title": title,
            "author": author,
            "post_date": post_date,
            "fetch_date": datetime.now().isoformat(),
            "url": url,
            "provider": specs.get("provider"),
            "category": category,
            "cpu": specs.get("cpu"),
            "ram_gb": specs.get("ram_gb"),
            "storage_gb": specs.get("storage_gb"),
            "storage_type": specs.get("storage_type"),
            "bandwidth": specs.get("bandwidth"),
            "ipv4_count": specs.get("ipv4_count", 1),
            "ipv6": bool(specs.get("ipv6", False)),
            "price_monthly": specs.get("price_monthly"),
            "price_yearly": specs.get("price_yearly"),
            "location": specs.get("location"),
            "status": status,
            "content_preview": (content or "")[:500],
            "raw_content": content or None,
        }

    def _normalize_status(self, status: str | None) -> str:
        if status in {"NEW", "ACTIVE", "EXPIRED"}:
            return status
        return "ACTIVE"

    def _dedupe_and_limit(self, deals: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for deal in deals:
            key = f"{deal.get('thread_id')}::{deal.get('url')}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(deal)
            if len(deduped) >= limit:
                break
        return deduped


def extract_deals(
    output_dir: Path | None = None,
    limit: int = 200,
    stale_hours: int = 24,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    extractor = SpectralDealsExtractor(output_dir=output_dir, stale_hours=stale_hours)
    return extractor.extract(limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract deals from spectral output")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT_JSON, help="Output JSON file")
    parser.add_argument("--output-dir", type=Path, help="Specific spectral output directory")
    parser.add_argument("--limit", type=int, default=200, help="Max number of deals")
    parser.add_argument("--stale-hours", type=int, default=24, help="Warn threshold for stale captures")

    args = parser.parse_args()

    extractor = SpectralDealsExtractor(output_dir=args.output_dir, stale_hours=args.stale_hours)
    deals, meta = extractor.extract(limit=args.limit)

    if not deals:
        print("No deals extracted from spectral artifacts.")
        if meta.get("warnings"):
            print("Warnings:")
            for warning in meta["warnings"]:
                print(f"  - {warning}")
        if meta.get("errors"):
            print("Errors:")
            for err in meta["errors"]:
                print(f"  - {err}")
        return 1

    output_path = extractor.save(deals, args.output)
    print(f"Extracted {len(deals)} deals using source: {meta.get('source')}")
    print(f"Output: {output_path}")

    if meta.get("warnings"):
        for warning in meta["warnings"]:
            print(f"Warning: {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
