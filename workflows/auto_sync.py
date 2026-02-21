#!/usr/bin/env python3
"""
Auto Sync Workflow - The Deterministic Pipeline

One command that does it all:
1. Fetches latest deals from LowEndTalk (deterministic, no Power Query)
2. Parses and extracts structured specs (vCPU, RAM, etc.)
3. Deduplicates programmatically (no Excel formulas)
4. Generates Excel with:
   - Deals Tracker (all deals, color-coded)
   - Deduplicated View (unique only)
   - Offer Details (technical specs)
   - Dashboard (metrics & charts)
5. Optionally syncs to GitHub

Usage:
    python auto_sync.py                    # Full sync
    python auto_sync.py --github           # Sync to GitHub too
    python auto_sync.py --dry-run          # Preview only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add paths for imports
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "fetcher"))
sys.path.insert(0, str(WORKSPACE / "database"))
sys.path.insert(0, str(WORKSPACE / "extractor"))
sys.path.insert(0, str(WORKSPACE / "excel-sync"))
sys.path.insert(0, str(WORKSPACE / "github-sync"))
sys.path.insert(0, str(WORKSPACE / "notifications"))


class AutoSyncWorkflow:
    """Deterministic end-to-end workflow."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.results: dict[str, Any] = {}
        self.errors: list[str] = []
        log_dir = Path.home() / ".let-automation" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / f"auto_sync_{datetime.now():%Y%m%d_%H%M%S}.md"
    
    def _log(self, message: str) -> None:
        timestamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        line = f"[{timestamp}] {message}"
        print(line)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    
    def run(
        self,
        dry_run: bool = False,
        github: bool = False,
        force_spectral: bool = False,
        force_bs4: bool = False,
        no_backup: bool = False,
    ) -> bool:
        """Execute the full workflow."""
        
        print("=" * 70)
        print("🤖 AUTO SYNC WORKFLOW")
        print("   Deterministic LowEndTalk → Excel Pipeline")
        print("=" * 70)
        self._log(f"Started workflow | dry_run={dry_run} github={github}")
        self._log(f"Source flags | force_spectral={force_spectral} force_bs4={force_bs4}")
        print("=" * 70)
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - Previewing workflow steps...\n")
        
        # Step 1: Fetch deals
        if not self._step_fetch(dry_run, force_spectral=force_spectral, force_bs4=force_bs4):
            return False
        
        # Step 2: Persist to database
        if not self._step_database(dry_run):
            return False

        # Step 3: Notify Discord
        if not self._step_notify(dry_run):
            return False

        # Step 4: Deduplicate
        if not self._step_deduplicate(dry_run):
            return False
        
        # Step 5: Generate Excel
        if not self._step_excel(dry_run, no_backup=no_backup):
            return False
        
        # Step 6: Sync to GitHub (optional)
        if github and not self._step_github(dry_run):
            return False
        
        # Summary
        self._print_summary()
        
        return len(self.errors) == 0
    
    def _step_fetch(self, dry_run: bool, force_spectral: bool = False, force_bs4: bool = False) -> bool:
        """Step 1: Fetch deals from LowEndTalk."""
        
        print("\n📍 STEP 1: Fetch Deals from LowEndTalk")
        print("-" * 50)
        
        if force_spectral and force_bs4:
            self.errors.append("Invalid options: --force-spectral and --force-bs4 cannot be combined")
            print("   ❌ Error: --force-spectral and --force-bs4 cannot be combined")
            return False
        
        if dry_run:
            print("   Source strategy:")
            print("     1. Try spectral extractor (client -> api.yaml -> capture JSON)")
            print("     2. Fallback to BS4 fetcher if spectral unavailable/fails")
            print(f"   Force spectral: {force_spectral}")
            print(f"   Force BS4: {force_bs4}")
            if force_bs4:
                print("   Would use BS4 fetcher (forced)")
            elif force_spectral:
                print("   Would use spectral extractor only (forced)")
            else:
                try:
                    from spectral_deals_extractor import SpectralDealsExtractor

                    latest = SpectralDealsExtractor.find_latest_output_dir()
                    if latest:
                        print(f"   Spectral output detected: {latest}")
                        print("   Would use spectral extractor")
                    else:
                        print("   No spectral output detected")
                        print("   Would fall back to BS4 fetcher")
                except Exception as e:
                    print(f"   Could not inspect spectral output: {e}")
                    print("   Would fall back to BS4 fetcher")
            print("   ✓ Preview complete")
            return True

        if force_bs4:
            self._log("Using BS4 fetcher (--force-bs4)")
            return self._run_bs4_fetch()

        spectral_ok = self._run_spectral_extraction()
        if spectral_ok:
            return True

        if force_spectral:
            self.errors.append("Spectral extraction failed and --force-spectral was set")
            print("   ❌ Error: spectral extraction failed (forced mode, no fallback)")
            return False

        self._log("Falling back to BS4 fetcher")
        return self._run_bs4_fetch()

    def _run_spectral_extraction(self) -> bool:
        """Try spectral extraction first."""
        try:
            from spectral_deals_extractor import SpectralDealsExtractor

            extractor = SpectralDealsExtractor()
            deals, metadata = extractor.extract(limit=200)

            if not deals:
                self._log("Spectral extractor returned no deals")
                for err in metadata.get("errors", []):
                    self._log(f"Spectral error: {err}")
                for warning in metadata.get("warnings", []):
                    self._log(f"Spectral warning: {warning}")
                return False

            self._log(f"Using spectral extractor | source={metadata.get('source')} rows={len(deals)}")
            for warning in metadata.get("warnings", []):
                self._log(f"Spectral warning: {warning}")

            self.results["fetched_deals"] = deals
            self.results["fetch_count"] = len(deals)
            self.results["fetch_source"] = "spectral"
            self.results["fetch_source_detail"] = metadata.get("source")
            self.results["fetch_step_type"] = "spectral_extract"

            data_dir = Path.home() / ".let-automation" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            raw_file = data_dir / f"spectral_deals_{datetime.now():%Y%m%d_%H%M%S}.json"
            raw_file.write_text(json.dumps(deals, indent=2, default=str))
            self._log(f"Saved spectral raw data: {raw_file}")
            return True

        except Exception as e:
            self._log(f"Spectral extraction failed: {e}")
            return False

    def _run_bs4_fetch(self) -> bool:
        """Fallback fetch using existing deterministic BS4/RSS fetcher."""
        try:
            from let_api_fetcher import LETFetcher

            fetcher = LETFetcher()
            deals = fetcher.fetch_and_parse(pages=3, fetch_details=False)

            self.results["fetched_deals"] = deals
            self.results["fetch_count"] = len(deals)
            self.results["fetch_source"] = "bs4"
            self.results["fetch_source_detail"] = "rss_html"
            self.results["fetch_step_type"] = "bs4_fetch"

            data_dir = Path.home() / ".let-automation" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            raw_file = data_dir / f"raw_deals_{datetime.now():%Y%m%d_%H%M%S}.json"
            raw_file.write_text(json.dumps(deals, indent=2, default=str))

            print(f"   ✓ Fetched {len(deals)} deals")
            print(f"   ✓ Saved raw data: {raw_file}")
            self._log(f"BS4 fetch complete | rows={len(deals)}")
            return True

        except Exception as e:
            self.errors.append(f"Fetch failed: {e}")
            print(f"   ❌ Error: {e}")
            self._log(f"BS4 fetch failed: {e}")
            return False
    
    def _step_deduplicate(self, dry_run: bool) -> bool:
        """Step 4: Deduplicate deals."""
        
        print("\n📍 STEP 4: Deduplicate")
        print("-" * 50)
        
        deals = self.results.get("fetched_deals", [])
        
        if dry_run:
            print(f"   Would process {len(deals)} deals")
            print("   Deduplication method: thread_id + title hash")
            print("   ✓ Preview complete")
            return True
        
        try:
            from deterministic_excel import DeterministicExcelManager
            
            manager = DeterministicExcelManager()
            unique_deals, duplicate_deals = manager.deduplicate(deals)
            
            self.results["unique_deals"] = unique_deals
            self.results["duplicate_deals"] = duplicate_deals
            self.results["unique_count"] = len(unique_deals)
            self.results["duplicate_count"] = len(duplicate_deals)
            
            print(f"   ✓ Unique deals: {len(unique_deals)}")
            print(f"   ✓ Duplicates removed: {len(duplicate_deals)}")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Deduplication failed: {e}")
            print(f"   ❌ Error: {e}")
            return False

    def _step_database(self, dry_run: bool) -> bool:
        """Step 2: Persist deals to SQLite history store."""

        print("\n📍 STEP 2: Persist to SQLite")
        print("-" * 50)

        deals = self.results.get("fetched_deals", [])
        if dry_run:
            print(f"   Would upsert {len(deals)} deals into ~/.let-automation/data/deals.db")
            print("   Would track price history changes in price_history table")
            print("   ✓ Preview complete")
            return True

        try:
            from db_manager import DBManager

            manager = DBManager()
            stats = manager.upsert_deals(deals)
            inserted_ids = [int(v) for v in stats.get("inserted_ids", [])]
            new_deals_for_notify = []
            for deal_id in inserted_ids:
                row = manager.get_deal_by_id(deal_id)
                if row:
                    new_deals_for_notify.append(row)

            self.results["db_stats"] = stats
            self.results["db_path"] = str(manager.db_path)
            self.results["new_deals_for_notify"] = new_deals_for_notify
            self._log(
                "Database upsert complete | "
                f"inserted={stats['inserted']} updated={stats['updated']} history={stats['price_history_added']}"
            )
            self._log(f"Notification candidates (new deals): {len(new_deals_for_notify)}")
            print(f"   ✓ DB upsert complete: {stats}")
            print(f"   ✓ Database path: {manager.db_path}")
            return True
        except Exception as e:
            self.errors.append(f"Database step failed: {e}")
            print(f"   ❌ Error: {e}")
            self._log(f"Database step failed: {e}")
            return False

    def _step_notify(self, dry_run: bool) -> bool:
        """Step 3: Send Discord notifications for newly inserted deals."""

        print("\n📍 STEP 3: Notify Discord")
        print("-" * 50)

        new_deals = self.results.get("new_deals_for_notify", [])
        if dry_run:
            configured = bool(self.config.get("discord_webhook_url"))
            print(f"   New deals eligible for notification: {len(new_deals)}")
            print(f"   Webhook configured via config: {configured}")
            print("   ✓ Preview complete")
            return True

        try:
            import config as runtime_config
            from notifications.discord import DiscordNotifier

            webhook_url = (
                self.config.get("discord_webhook_url")
                or runtime_config.DISCORD_WEBHOOK_URL
            )
            max_messages = int(
                self.config.get(
                    "discord_max_messages_per_run",
                    runtime_config.DISCORD_MAX_MESSAGES_PER_RUN,
                )
            )
            rate_limit_seconds = float(
                self.config.get(
                    "discord_rate_limit_seconds",
                    runtime_config.DISCORD_RATE_LIMIT_SECONDS,
                )
            )

            if not webhook_url:
                self.results["notify_stats"] = {"sent": 0, "skipped": len(new_deals), "failed": 0, "status": "disabled"}
                self._log("Discord webhook not configured; skipping notifications")
                print("   ⚠ Discord webhook not configured; skipping")
                return True

            if not new_deals:
                self.results["notify_stats"] = {"sent": 0, "skipped": 0, "failed": 0, "status": "no_new_deals"}
                self._log("No newly inserted deals; skipping Discord notifications")
                print("   ✓ No new deals to notify")
                return True

            notifier = DiscordNotifier(
                webhook_url=webhook_url,
                max_messages_per_run=max_messages,
                rate_limit_seconds=rate_limit_seconds,
            )
            result = notifier.send_deals(new_deals)
            self.results["notify_stats"] = {
                "sent": result.sent,
                "skipped": result.skipped,
                "failed": result.failed,
                "status": "sent",
            }
            self._log(
                "Discord notification step complete | "
                f"sent={result.sent} skipped={result.skipped} failed={result.failed}"
            )
            print(
                "   ✓ Discord notifications: "
                f"sent={result.sent}, skipped={result.skipped}, failed={result.failed}"
            )
            return True
        except Exception as e:
            self._log(f"Discord notification step failed (non-fatal): {e}")
            self.results["notify_stats"] = {"sent": 0, "skipped": len(new_deals), "failed": 0, "status": "error"}
            print(f"   ⚠ Discord notification failed (non-fatal): {e}")
            return True
    
    def _step_excel(self, dry_run: bool, no_backup: bool = False) -> bool:
        """Step 5: Generate Excel file."""
        
        print("\n📍 STEP 5: Generate Excel")
        print("-" * 50)
        
        if dry_run:
            print("   Would create sheets:")
            print("     1. Deals Tracker (all deals)")
            print("     2. Deduplicated View (unique only)")
            print("     3. Offer Details (technical specs)")
            print("     4. Dashboard (metrics & stats)")
            print("     5. Raw Data (reference)")
            print("   Color coding:")
            print("     🟢 NEW (< 7 days)")
            print("     🔵 ACTIVE (7-30 days)")
            print("     ⚪ EXPIRED (> 30 days)")
            print("     🔴 DUPLICATE")
            print("   ✓ Preview complete")
            return True
        
        try:
            from deterministic_excel import DeterministicExcelManager
            
            deals = self.results.get("fetched_deals", [])

            excel_file = self.config.get("excel_file")
            manager = DeterministicExcelManager(Path(excel_file) if excel_file else None)
            excel_path = manager.generate_excel(deals=deals, backup=not no_backup)
            
            self.results["excel_path"] = str(excel_path)
            
            print(f"   ✓ Excel generated: {excel_path}")
            print(f"   ✓ Sheets: Deals Tracker, Deduplicated View, Offer Details, Dashboard, Raw Data")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Excel generation failed: {e}")
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _step_github(self, dry_run: bool) -> bool:
        """Step 6: Sync to GitHub."""
        
        print("\n📍 STEP 6: Sync to GitHub")
        print("-" * 50)
        
        if dry_run:
            print("   Would push to GitHub:")
            print("     - deals.json (latest)")
            print("     - deals.yaml (YAML format)")
            print("     - summary.json (metrics)")
            print("   ✓ Preview complete")
            return True
        
        try:
            from github_uploader import GitHubDealsSync
            
            deals = self.results.get("unique_deals", [])
            
            sync = GitHubDealsSync()
            
            # Ensure repo exists
            sync.ensure_repo_exists()
            
            # Upload
            sync.upload_deals(deals)
            sync.upload_deals_yaml(deals)
            
            # Upload summary
            summary = {
                "total_deals": self.results.get("unique_count", 0),
                "fetch_date": datetime.now().isoformat(),
                "providers": {},
            }
            sync.upload_summary(summary)
            
            print(f"   ✓ Uploaded {len(deals)} deals to GitHub")
            
            return True
            
        except Exception as e:
            self.errors.append(f"GitHub sync failed: {e}")
            print(f"   ❌ Error: {e}")
            return False
    
    def _print_summary(self):
        """Print final summary."""
        
        print("\n" + "=" * 70)
        print("📊 WORKFLOW SUMMARY")
        print("=" * 70)
        
        if "fetch_count" in self.results:
            print(f"   Deals fetched: {self.results['fetch_count']}")
        if "fetch_source" in self.results:
            print(f"   Fetch source: {self.results['fetch_source']} ({self.results.get('fetch_source_detail')})")
        
        if "unique_count" in self.results:
            print(f"   Unique deals: {self.results['unique_count']}")
            print(f"   Duplicates removed: {self.results['duplicate_count']}")
        if "db_stats" in self.results:
            stats = self.results["db_stats"]
            print(
                "   DB upsert: "
                f"{stats.get('inserted', 0)} inserted, {stats.get('updated', 0)} updated, "
                f"{stats.get('price_history_added', 0)} history rows"
            )
        if "notify_stats" in self.results:
            notify = self.results["notify_stats"]
            print(
                "   Discord notifications: "
                f"{notify.get('sent', 0)} sent, {notify.get('skipped', 0)} skipped, "
                f"{notify.get('failed', 0)} failed ({notify.get('status', 'unknown')})"
            )
        
        if "excel_path" in self.results:
            print(f"   Excel file: {self.results['excel_path']}")
        
        if self.errors:
            print(f"\n   ❌ Errors ({len(self.errors)}):")
            for err in self.errors:
                print(f"      - {err}")
        else:
            print(f"\n   ✅ All steps completed successfully!")
        
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Auto sync workflow for LET deals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full sync (fetch + Excel)
  python auto_sync.py
  
  # Include GitHub sync
  python auto_sync.py --github
  
  # Preview without executing
  python auto_sync.py --dry-run
  
  # No backup
  python auto_sync.py --no-backup
        """
    )
    
    parser.add_argument("--github", "-g", action="store_true", help="Sync to GitHub")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Preview only")
    parser.add_argument("--no-backup", action="store_true", help="Skip Excel backup")
    parser.add_argument("--force-spectral", action="store_true", help="Use spectral extractor only (no fallback)")
    parser.add_argument("--force-bs4", action="store_true", help="Force legacy BS4/RSS fetcher")
    parser.add_argument("--config", "-c", type=Path, help="Config file")
    parser.add_argument("--excel-file", type=Path, help="Excel output path")
    
    args = parser.parse_args()
    
    # Load config if provided
    config = {}
    if args.config:
        config = json.loads(args.config.read_text())
    
    if args.excel_file:
        config["excel_file"] = str(args.excel_file)

    # Run workflow
    workflow = AutoSyncWorkflow(config)
    success = workflow.run(
        dry_run=args.dry_run,
        github=args.github,
        force_spectral=args.force_spectral,
        force_bs4=args.force_bs4,
        no_backup=args.no_backup,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
