#!/usr/bin/env python3
"""
Spectral Bridge for LowEndTalk

Manages API discovery and session handling specifically for LowEndTalk.com.
Integrates with the existing spectral-nodriver tool.

Usage:
    python let_spectral.py discover
    python let_spectral.py capture --duration 300
    python let_spectral.py analyze
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Paths
SPECTRAL_NODRIVER_DIR = Path.home() / "workspace" / "spectral-nodriver"
SPECTRAL_NODRIVER_SCRIPT = SPECTRAL_NODRIVER_DIR / "spectral_nodriver.py"
LET_SITE_ID = "lowendtalk_com"

# Output directories
DATA_DIR = Path.home() / ".let-automation"
CAPTURES_DIR = DATA_DIR / "captures"
SPECS_DIR = DATA_DIR / "specs"
SESSIONS_DIR = DATA_DIR / "sessions"
SPECTRAL_OUTPUT_DIR = Path.home() / ".spectral-nodriver" / "output"

for d in [DATA_DIR, CAPTURES_DIR, SPECS_DIR, SESSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# local imports
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE / "extractor"))


class LETSpectralBridge:
    """Manages spectral discovery for LowEndTalk."""
    
    LET_URL = "https://lowendtalk.com"
    
    # Key pages to capture for API discovery
    KEY_PAGES = [
        "/",  # Homepage with recent discussions
        "/categories",  # Category listings
        "/discussions",  # All discussions
        "/entry/signin",  # Login flow
    ]
    
    def __init__(self):
        self.session_file = SESSIONS_DIR / f"{LET_SITE_ID}_session.json"
        self.spec_file = None

    def latest_output_dir(self) -> Path | None:
        output_dirs = sorted(
            SPECTRAL_OUTPUT_DIR.glob(f"{LET_SITE_ID}_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return output_dirs[0] if output_dirs else None
    
    def discover(self, interactive: bool = True) -> Path | None:
        """Run full discovery workflow on LowEndTalk."""
        
        print("=" * 60)
        print("🔍 LowEndTalk API Discovery via Spectral")
        print("=" * 60)
        
        if not SPECTRAL_NODRIVER_SCRIPT.exists():
            print(f"❌ spectral-nodriver not found at {SPECTRAL_NODRIVER_SCRIPT}")
            print("Run: git clone https://github.com/romain-gilliotte/spectral ~/workspace/spectral")
            return None

        # Automated discovery needs a display-capable runtime for nodriver/Chrome.
        if not interactive and (
            not os.environ.get("DISPLAY")
            or not sys.stdin.isatty()
            or os.environ.get("CI") == "true"
        ):
            print("⚠️  Headless environment detected. Skipping browser-based discovery.")
            print("   Run with --interactive on a machine with display for full discovery.")
            return None
        
        # Build command
        cmd = [
            sys.executable,
            str(SPECTRAL_NODRIVER_SCRIPT),
            "discover",
            self.LET_URL,
        ]
        
        if interactive:
            cmd.append("--interactive")
        else:
            cmd.append("--no-interactive")
            # Add automated navigation
            for page in self.KEY_PAGES:
                cmd.extend(["--action", f"navigate:{self.LET_URL}{page}"])
                cmd.extend(["--action", "wait:3"])
        
        print(f"\n📡 Starting spectral discovery...")
        print(f"   Target: {self.LET_URL}")
        print(f"   Mode: {'Interactive' if interactive else 'Automated'}")
        
        # Run discovery
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            print("❌ Discovery failed")
            return None
        
        # Find generated spec
        output_dirs = sorted(
            SPECTRAL_OUTPUT_DIR.glob(f"{LET_SITE_ID}_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if output_dirs:
            latest = output_dirs[0]
            spec_path = latest / "api.yaml"
            if spec_path.exists():
                self.spec_file = spec_path
                print(f"\n✅ Spec generated: {spec_path}")
                
                # Copy to our specs dir
                dest = SPECS_DIR / f"let_spec_{datetime.now():%Y%m%d_%H%M%S}.yaml"
                dest.write_bytes(spec_path.read_bytes())
                print(f"   Copied to: {dest}")
                
                # Save session info
                self._save_session({
                    "last_discovery": datetime.now().isoformat(),
                    "spec_path": str(spec_path),
                    "output_dir": str(latest)
                })
                
                return spec_path
        
        print("⚠️  Spec not found in expected location")
        return None
    
    def capture_authenticated(self, actions: list[str] | None = None) -> Path | None:
        """Capture traffic with authenticated session."""
        
        print("=" * 60)
        print("🔐 Authenticated Session Capture")
        print("=" * 60)
        
        # Check if we have existing cookies
        cookie_file = Path.home() / ".spectral-nodriver" / "cookies" / f"{LET_SITE_ID}_cookies.json"
        
        if cookie_file.exists():
            print(f"   Found existing cookies: {cookie_file}")
            print("   Will use saved session (bypass Cloudflare)")
        else:
            print("   No existing session. You'll need to login manually.")
        
        cmd = [
            sys.executable,
            str(SPECTRAL_NODRIVER_SCRIPT),
            "discover",
            f"{self.LET_URL}/discussions",
            "--interactive"
        ]
        
        print(f"\n📡 Starting capture...")
        print("   1. Browser will open to LET discussions")
        print("   2. Login if needed (cookies will be saved)")
        print("   3. Browse to trigger API calls")
        print("   4. Press Enter when done")
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n✅ Capture complete")
            return self._get_latest_capture()
        
        return None
    
    def get_deals_api_endpoints(self) -> list[dict]:
        """Extract deal-related API endpoints from spec."""
        
        if not self.spec_file or not self.spec_file.exists():
            # Try to find latest spec
            specs = sorted(SPECS_DIR.glob("let_spec_*.yaml"), reverse=True)
            if specs:
                self.spec_file = specs[0]
            else:
                print("❌ No spec found. Run discover first.")
                return []
        
        import yaml
        
        spec = yaml.safe_load(self.spec_file.read_text())
        paths = spec.get("paths", {})
        
        # Find deal-related endpoints
        deal_endpoints = []
        keywords = ["discussion", "comment", "category", "tag", "deal", "offer"]
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method not in ["get", "post", "put", "patch"]:
                    continue
                
                # Check if path or description contains keywords
                path_lower = path.lower()
                desc = details.get("summary", "") + " " + details.get("description", "")
                desc_lower = desc.lower()
                
                if any(k in path_lower or k in desc_lower for k in keywords):
                    deal_endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", "N/A"),
                        "description": details.get("description", "")[:100]
                    })
        
        print(f"\n📊 Found {len(deal_endpoints)} deal-related endpoints:")
        for ep in deal_endpoints[:10]:  # Show first 10
            print(f"   {ep['method']:6} {ep['path']:40} - {ep['summary'][:40]}")
        
        if len(deal_endpoints) > 10:
            print(f"   ... and {len(deal_endpoints) - 10} more")
        
        return deal_endpoints
    
    def generate_deals_client(self) -> Path | None:
        """Generate a Python client for deals API."""
        
        endpoints = self.get_deals_api_endpoints()
        
        if not endpoints:
            return None
        
        client_code = '''#!/usr/bin/env python3
"""
Auto-generated LowEndTalk API Client
Generated by let_spectral.py
"""

import json
from pathlib import Path
import requests

class LETClient:
    """LowEndTalk API Client (unofficial)"""
    
    BASE_URL = "https://lowendtalk.com"
    
    def __init__(self):
        self.session = requests.Session()
        self._load_cookies()
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        })
    
    def _load_cookies(self):
        """Load saved cookies from spectral-nodriver session."""
        cookie_file = Path.home() / ".spectral-nodriver" / "cookies" / "lowendtalk_com_cookies.json"
        if cookie_file.exists():
            cookies = json.loads(cookie_file.read_text())
            for c in cookies:
                self.session.cookies.set(
                    c["name"], c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/")
                )
    
'''
        # Add methods for each endpoint
        for ep in endpoints[:20]:  # Limit to 20 methods
            path = ep["path"]
            method = ep["method"].lower()
            name = ep["summary"].replace(" ", "_").lower()[:30] or f"{method}_{path.replace('/', '_')}"
            
            # Convert path params to Python args
            params = []
            path_format = path
            for match in __import__('re').finditer(r'\{(\w+)\}', path):
                param = match.group(1)
                params.append(f"{param}: str")
                path_format = path_format.replace(f"{{{param}}}", f"{{{param}}}")
            
            params_str = ", ".join([""] + params) if params else ""
            
            client_code += f'''
    def {name}(self{params_str}):
        """{ep["summary"]}"""
        url = f"{{self.BASE_URL}}{path_format}"
        response = self.session.{method}(url)
        response.raise_for_status()
        return response.json() if response.content else None
    
'''
        
        # Save client
        client_file = DATA_DIR / "let_client.py"
        client_file.write_text(client_code)
        print(f"\n✅ Generated client: {client_file}")
        
        return client_file
    
    def _get_latest_capture(self) -> Path | None:
        """Get path to latest capture file."""
        captures = sorted(
            (Path.home() / ".spectral-nodriver" / "captures").glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return captures[0] if captures else None
    
    def _save_session(self, data: dict):
        """Save session metadata."""
        self.session_file.write_text(json.dumps(data, indent=2))

    def extract_to_json(
        self,
        output_file: Path | None = None,
        stale_hours: int = 24,
        auto_discover: bool = True,
    ) -> Path | None:
        """Extract normalized deals from latest spectral artifacts and save JSON."""

        output_file = output_file or (Path.home() / ".let-automation" / "data" / "spectral_deals.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        latest = self.latest_output_dir()
        if not latest and auto_discover:
            print("⚠️  No spectral output found. Running discovery first...")
            discovered = self.discover(interactive=False)
            if discovered:
                latest = discovered.parent

        if not latest:
            print("❌ No spectral output available. Run discovery first.")
            return None

        age_hours = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).total_seconds() / 3600.0
        if age_hours > stale_hours:
            print(
                f"⚠️  Latest spectral capture is stale ({age_hours:.1f}h old). "
                f"Consider re-running: python let_spectral.py discover --no-interactive"
            )

        try:
            from spectral_deals_extractor import SpectralDealsExtractor
        except Exception as exc:
            print(f"❌ Failed to import spectral extractor: {exc}")
            return None

        extractor = SpectralDealsExtractor(output_dir=latest, stale_hours=stale_hours)
        deals, metadata = extractor.extract(limit=200)

        if not deals:
            print("❌ Spectral extractor did not return any deals")
            for err in metadata.get("errors", []):
                print(f"   error: {err}")
            for warning in metadata.get("warnings", []):
                print(f"   warning: {warning}")
            return None

        output_path = extractor.save(deals, output_file)
        print(f"✅ Extracted {len(deals)} deals from {metadata.get('source')}")
        print(f"   Output: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description="Spectral bridge for LowEndTalk")
    parser.add_argument("command", choices=["discover", "capture", "analyze", "client", "extract-to-json"])
    parser.add_argument("--interactive", "-i", action="store_true", default=True)
    parser.add_argument("--no-interactive", dest="interactive", action="store_false")
    parser.add_argument("--output", type=Path, help="Output file for extract-to-json")
    parser.add_argument("--stale-hours", type=int, default=24, help="Stale threshold for spectral output")
    
    args = parser.parse_args()
    
    bridge = LETSpectralBridge()
    
    if args.command == "discover":
        bridge.discover(interactive=args.interactive)
    
    elif args.command == "capture":
        bridge.capture_authenticated()
    
    elif args.command == "analyze":
        bridge.get_deals_api_endpoints()
    
    elif args.command == "client":
        bridge.generate_deals_client()

    elif args.command == "extract-to-json":
        bridge.extract_to_json(output_file=args.output, stale_hours=args.stale_hours, auto_discover=True)


if __name__ == "__main__":
    main()
