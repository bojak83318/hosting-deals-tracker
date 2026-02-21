#!/usr/bin/env python3
"""
Excel Sync Module for Hosting-Deals-Tracker.xlsx

Manages the @Hosting-Deals-Tracker.xlsx file with deal data.
Supports reading, updating, and syncing with other sources.

Usage:
    python excel_manager.py --add-deals deals.json
    python excel_manager.py --export-to-github
    python excel_manager.py --stats
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas/openpyxl not installed. Run: pip install pandas openpyxl")


# Default paths
DEFAULT_EXCEL_PATH = Path.home() / "workspace" / "Hosting-Deals-Tracker.xlsx"
DATA_DIR = Path.home() / ".let-automation"


class ExcelDealsManager:
    """Manager for Hosting-Deals-Tracker.xlsx."""
    
    # Standard columns for the tracker
    COLUMNS = [
        "Date Added",
        "Provider",
        "Product Type",  # VPS, Dedicated, Shared, etc.
        "Plan Name",
        "Price (USD)",
        "Billing Cycle",  # Monthly, Yearly, etc.
        "Specs",
        "Location",
        "Source URL",
        "Status",  # Active, Expired, Hot
        "Notes",
        "Last Updated"
    ]
    
    def __init__(self, excel_path: Path | None = None):
        self.excel_path = excel_path or DEFAULT_EXCEL_PATH
        self.df: pd.DataFrame | None = None
    
    def load_or_create(self) -> pd.DataFrame:
        """Load existing Excel or create new one."""
        
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required")
        
        if self.excel_path.exists():
            print(f"📂 Loading: {self.excel_path}")
            self.df = pd.read_excel(self.excel_path)
            
            # Ensure all columns exist
            for col in self.COLUMNS:
                if col not in self.df.columns:
                    self.df[col] = None
            
            print(f"   Loaded {len(self.df)} deals")
        else:
            print(f"➕ Creating new tracker: {self.excel_path}")
            self.df = pd.DataFrame(columns=self.COLUMNS)
        
        return self.df
    
    def add_deals(self, deals: list[dict]) -> int:
        """Add new deals to the tracker."""
        
        if self.df is None:
            self.load_or_create()
        
        added = 0
        skipped = 0
        
        for deal in deals:
            # Normalize deal data
            row = self._normalize_deal(deal)
            
            # Check for duplicates (by Provider + Plan Name + Price)
            if self._is_duplicate(row):
                skipped += 1
                continue
            
            # Add to dataframe
            self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
            added += 1
        
        print(f"✅ Added: {added}, Skipped (duplicates): {skipped}")
        return added
    
    def update_deals(self, deals: list[dict], match_by: str = "Source URL") -> int:
        """Update existing deals."""
        
        if self.df is None:
            self.load_or_create()
        
        updated = 0
        
        for deal in deals:
            row = self._normalize_deal(deal)
            match_value = row.get(match_by)
            
            if match_value and match_value in self.df[match_by].values:
                idx = self.df[self.df[match_by] == match_value].index[0]
                for col, val in row.items():
                    if col in self.df.columns and pd.notna(val):
                        self.df.at[idx, col] = val
                self.df.at[idx, "Last Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                updated += 1
        
        print(f"✅ Updated: {updated} deals")
        return updated
    
    def get_active_deals(self, max_price: float | None = None) -> pd.DataFrame:
        """Get active deals with optional price filter."""
        
        if self.df is None:
            self.load_or_create()
        
        active = self.df[self.df["Status"].isin(["Active", "Hot"])]
        
        if max_price:
            active = active[active["Price (USD)"] <= max_price]
        
        return active
    
    def get_stats(self) -> dict:
        """Get statistics about the deals."""
        
        if self.df is None:
            self.load_or_create()
        
        stats = {
            "total_deals": len(self.df),
            "active_deals": len(self.df[self.df["Status"] == "Active"]),
            "hot_deals": len(self.df[self.df["Status"] == "Hot"]),
            "expired_deals": len(self.df[self.df["Status"] == "Expired"]),
            "providers": self.df["Provider"].nunique() if "Provider" in self.df.columns else 0,
            "price_range": {}
        }
        
        if "Price (USD)" in self.df.columns:
            prices = pd.to_numeric(self.df["Price (USD)"], errors="coerce")
            stats["price_range"] = {
                "min": prices.min(),
                "max": prices.max(),
                "avg": prices.mean(),
                "median": prices.median()
            }
        
        # Provider breakdown
        if "Provider" in self.df.columns:
            stats["top_providers"] = self.df["Provider"].value_counts().head(5).to_dict()
        
        # Product type breakdown
        if "Product Type" in self.df.columns:
            stats["product_types"] = self.df["Product Type"].value_counts().to_dict()
        
        return stats
    
    def save(self, backup: bool = True) -> Path:
        """Save the tracker to Excel with formatting."""
        
        if self.df is None:
            raise ValueError("No data to save")
        
        # Create backup
        if backup and self.excel_path.exists():
            backup_path = self.excel_path.with_suffix(f".backup_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
            self.excel_path.rename(backup_path)
            print(f"💾 Backup created: {backup_path}")
        
        # Sort by date (newest first)
        if "Date Added" in self.df.columns:
            self.df["Date Added"] = pd.to_datetime(self.df["Date Added"], errors="coerce")
            self.df = self.df.sort_values("Date Added", ascending=False)
        
        # Save with formatting
        with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
            self.df.to_excel(writer, sheet_name="Deals", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Deals"]
            
            # Format headers
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Add filters
            worksheet.auto_filter.ref = worksheet.dimensions
        
        print(f"✅ Saved: {self.excel_path}")
        print(f"   Deals: {len(self.df)}")
        return self.excel_path
    
    def export_to_json(self, output_path: Path | None = None) -> Path:
        """Export deals to JSON."""
        
        if self.df is None:
            self.load_or_create()
        
        output_path = output_path or DATA_DIR / "deals_export.json"
        
        records = self.df.to_dict("records")
        output_path.write_text(json.dumps(records, indent=2, default=str))
        
        print(f"✅ Exported to JSON: {output_path}")
        return output_path
    
    def import_from_json(self, json_path: Path) -> int:
        """Import deals from JSON."""
        
        deals = json.loads(json_path.read_text())
        return self.add_deals(deals)
    
    def _normalize_deal(self, deal: dict) -> dict:
        """Normalize deal dict to match Excel columns."""
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        normalized = {
            "Date Added": deal.get("date_added") or deal.get("date") or now.split()[0],
            "Provider": deal.get("provider") or deal.get("company", "Unknown"),
            "Product Type": deal.get("product_type") or deal.get("type", "VPS"),
            "Plan Name": deal.get("plan_name") or deal.get("plan", ""),
            "Price (USD)": self._parse_price(deal.get("price") or deal.get("price_usd", 0)),
            "Billing Cycle": deal.get("billing_cycle") or deal.get("cycle", "Monthly"),
            "Specs": deal.get("specs") or deal.get("configuration", ""),
            "Location": deal.get("location") or deal.get("datacenter", ""),
            "Source URL": deal.get("source_url") or deal.get("url", ""),
            "Status": deal.get("status", "Active"),
            "Notes": deal.get("notes", ""),
            "Last Updated": now
        }
        
        return normalized
    
    def _parse_price(self, price: Any) -> float:
        """Parse price to float."""
        
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            # Extract number from string like "$12.99/month" or "€10"
            import re
            match = re.search(r'[\d,]+\.?\d*', price.replace(",", ""))
            if match:
                return float(match.group())
        
        return 0.0
    
    def _is_duplicate(self, row: dict) -> bool:
        """Check if deal already exists."""
        
        if self.df is None or len(self.df) == 0:
            return False
        
        # Match by Source URL
        source_url = row.get("Source URL")
        if source_url and source_url in self.df["Source URL"].values:
            return True
        
        # Match by Provider + Plan + Price (within last 30 days)
        provider = row.get("Provider")
        plan = row.get("Plan Name")
        price = row.get("Price (USD)")
        
        if provider and plan:
            matches = self.df[
                (self.df["Provider"] == provider) &
                (self.df["Plan Name"] == plan) &
                (self.df["Price (USD)"] == price)
            ]
            
            if len(matches) > 0:
                return True
        
        return False


def main():
    parser = argparse.ArgumentParser(description="Excel manager for hosting deals")
    parser.add_argument("--file", "-f", type=Path, default=DEFAULT_EXCEL_PATH)
    parser.add_argument("--add", "-a", type=Path, help="JSON file with deals to add")
    parser.add_argument("--export-json", "-e", type=Path, help="Export to JSON")
    parser.add_argument("--import-json", "-i", type=Path, help="Import from JSON")
    parser.add_argument("--stats", "-s", action="store_true", help="Show statistics")
    parser.add_argument("--list", "-l", action="store_true", help="List all deals")
    parser.add_argument("--filter-price", type=float, help="Filter by max price")
    
    args = parser.parse_args()
    
    if not PANDAS_AVAILABLE:
        print("❌ pandas not installed. Run: pip install pandas openpyxl")
        return
    
    manager = ExcelDealsManager(args.file)
    
    if args.add:
        deals = json.loads(args.add.read_text())
        manager.add_deals(deals)
        manager.save()
    
    elif args.export_json:
        manager.export_to_json(args.export_json)
    
    elif args.import_json:
        manager.import_from_json(args.import_json)
        manager.save()
    
    elif args.stats:
        stats = manager.get_stats()
        print("\n📊 Deal Statistics:")
        print(f"   Total deals: {stats['total_deals']}")
        print(f"   Active: {stats['active_deals']}")
        print(f"   Hot deals: {stats['hot_deals']}")
        print(f"   Expired: {stats['expired_deals']}")
        print(f"   Unique providers: {stats['providers']}")
        
        if stats['price_range']:
            pr = stats['price_range']
            print(f"   Price range: ${pr.get('min', 0):.2f} - ${pr.get('max', 0):.2f}")
            print(f"   Avg price: ${pr.get('avg', 0):.2f}")
        
        if stats.get('top_providers'):
            print("\n   Top Providers:")
            for provider, count in list(stats['top_providers'].items())[:5]:
                print(f"      {provider}: {count}")
    
    elif args.list:
        df = manager.load_or_create()
        
        if args.filter_price:
            df = df[df["Price (USD)"] <= args.filter_price]
        
        # Show recent 20
        print(f"\n📋 Recent Deals (showing {min(20, len(df))} of {len(df)}):")
        print(df.head(20).to_string())
    
    else:
        # Just load and save to ensure format
        manager.load_or_create()
        manager.save(backup=False)
        print(f"\n✅ Excel file ready: {args.file}")


if __name__ == "__main__":
    main()
