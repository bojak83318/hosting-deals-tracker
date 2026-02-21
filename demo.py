#!/usr/bin/env python3
"""
Demo of the Deterministic Workflow

Shows how the new workflow replaces Power Query with automation.
"""

import json
from datetime import datetime, timedelta

# Mock deals data (simulating what would be fetched)
MOCK_DEALS = [
    {
        "thread_id": "12345",
        "title": "RackNerd - 2GB KVM VPS - $18.99/year - Multiple Locations",
        "author": "racknerd_staff",
        "post_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "url": "https://lowendtalk.com/discussion/12345",
        "provider": "RackNerd",
        "category": "VPS",
        "cpu": 2,
        "ram_gb": 2,
        "storage_gb": 40,
        "storage_type": "SSD",
        "bandwidth": 3000,
        "ipv4_count": 1,
        "ipv6": True,
        "price_yearly": 18.99,
        "location": "USA",
    },
    {
        "thread_id": "12346",
        "title": "BuyVM - 1GB KVM Slice - $2/month - Las Vegas",
        "author": "buyvm_fan",
        "post_date": (datetime.now() - timedelta(days=5)).isoformat(),
        "url": "https://lowendtalk.com/discussion/12346",
        "provider": "BuyVM",
        "category": "VPS",
        "cpu": 1,
        "ram_gb": 1,
        "storage_gb": 20,
        "storage_type": "SSD",
        "bandwidth": 1000,
        "ipv4_count": 1,
        "ipv6": True,
        "price_monthly": 2.00,
        "location": "Las Vegas",
    },
    {
        "thread_id": "12347",  # Duplicate of 12345
        "title": "RackNerd - 2GB KVM VPS - $18.99/year - Multiple Locations",
        "author": "racknerd_staff",
        "post_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "url": "https://lowendtalk.com/discussion/12345",
        "provider": "RackNerd",
        "category": "VPS",
        "cpu": 2,
        "ram_gb": 2,
        "storage_gb": 40,
        "storage_type": "SSD",
        "bandwidth": 3000,
        "ipv4_count": 1,
        "ipv6": True,
        "price_yearly": 18.99,
        "location": "USA",
    },
    {
        "thread_id": "12348",
        "title": "Hetzner - Dedicated Server Auction - €30/month",
        "author": "server_hunter",
        "post_date": (datetime.now() - timedelta(days=45)).isoformat(),
        "url": "https://lowendtalk.com/discussion/12348",
        "provider": "Hetzner",
        "category": "Dedicated",
        "cpu": 4,
        "ram_gb": 32,
        "storage_gb": 2000,
        "storage_type": "HDD",
        "bandwidth": 20000,
        "ipv4_count": 1,
        "ipv6": True,
        "price_monthly": 33.00,  # ~€30
        "location": "Germany",
    },
]


def calculate_status(post_date_str: str) -> str:
    """Calculate status based on age."""
    try:
        post_date = datetime.fromisoformat(post_date_str)
        age_days = (datetime.now() - post_date).days
        
        if age_days < 7:
            return "NEW"  # Green
        elif age_days < 30:
            return "ACTIVE"  # Blue
        else:
            return "EXPIRED"  # Gray
    except:
        return "UNKNOWN"


def deduplicate(deals: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic deduplication."""
    seen = {}
    unique = []
    duplicates = []
    
    for deal in deals:
        # Create dedup key: normalized title (catches reposts with different thread_id)
        title = deal.get("title", "")[:60].lower().strip()
        # Also check provider + specs combination
        provider = deal.get("provider", "")
        specs_key = f"{deal.get('cpu')}cpu_{deal.get('ram_gb')}gb_{deal.get('storage_gb')}gb"
        
        # Primary key: title, Secondary: provider+specs
        key = title
        alt_key = f"{provider}:{specs_key}"
        
        if key in seen or alt_key in seen:
            deal["_is_duplicate"] = True
            deal["_duplicate_of"] = seen.get(key) or seen.get(alt_key)
            duplicates.append(deal)
        else:
            seen[key] = deal.get("url", "")
            seen[alt_key] = deal.get("url", "")
            deal["_is_duplicate"] = False
            unique.append(deal)
    
    return unique, duplicates


def main():
    print("=" * 70)
    print("🤖 DETERMINISTIC WORKFLOW DEMO")
    print("   Showing how automation replaces Power Query")
    print("=" * 70)
    
    # Step 1: Show raw fetched data
    print("\n📍 STEP 1: Fetch Deals")
    print("-" * 50)
    print(f"Fetched {len(MOCK_DEALS)} discussions from LowEndTalk")
    for deal in MOCK_DEALS:
        print(f"  • [{deal['thread_id']}] {deal['title'][:50]}...")
    
    # Step 2: Show extracted specs
    print("\n📍 STEP 2: Extract Structured Specs")
    print("-" * 50)
    print("From text content, extracted:")
    for deal in MOCK_DEALS[:2]:  # Show first 2
        print(f"\n  {deal['provider']}:")
        print(f"    • Category: {deal['category']}")
        print(f"    • Specs: {deal['cpu']}vCPU, {deal['ram_gb']}GB RAM, {deal['storage_gb']}GB {deal['storage_type']}")
        print(f"    • Network: {deal['bandwidth']}GB bandwidth, {deal['ipv4_count']} IPv4")
        print(f"    • Location: {deal['location']}")
        print(f"    • Price: ${deal.get('price_monthly') or deal.get('price_yearly')}")
    
    # Step 3: Deduplicate
    print("\n📍 STEP 3: Deterministic Deduplication")
    print("-" * 50)
    unique, duplicates = deduplicate(MOCK_DEALS.copy())
    
    print(f"Input: {len(MOCK_DEALS)} deals")
    print(f"Unique: {len(unique)}")
    print(f"Duplicates removed: {len(duplicates)}")
    
    if duplicates:
        print("\n  Duplicates found:")
        for dup in duplicates:
            print(f"    🔴 [{dup['thread_id']}] {dup['title'][:40]}...")
            print(f"       → Same as: {dup['_duplicate_of']}")
    
    # Step 4: Calculate status
    print("\n📍 STEP 4: Calculate Status")
    print("-" * 50)
    print("Color coding based on age:")
    for deal in unique:
        status = calculate_status(deal["post_date"])
        emoji = {"NEW": "🟢", "ACTIVE": "🔵", "EXPIRED": "⚪"}.get(status, "⚪")
        print(f"  {emoji} [{status:8}] {deal['provider']:12} - {deal['title'][:30]}...")
    
    # Step 5: Show Excel output structure
    print("\n📍 STEP 5: Generate Excel (5 sheets)")
    print("-" * 50)
    print("  1. Deals Tracker")
    print(f"     • {len(MOCK_DEALS)} rows (all deals)")
    print(f"     • Color-coded: 🟢NEW={sum(1 for d in unique if calculate_status(d['post_date'])=='NEW')} "
          f"🔵ACTIVE={sum(1 for d in unique if calculate_status(d['post_date'])=='ACTIVE')} "
          f"⚪EXPIRED={sum(1 for d in unique if calculate_status(d['post_date'])=='EXPIRED')}")
    print(f"     • 🔴 Duplicates highlighted: {len(duplicates)}")
    print("     • Auto-filters enabled")
    print("")
    print("  2. Deduplicated View")
    print(f"     • {len(unique)} rows (unique only)")
    print("")
    print("  3. Offer Details")
    print("     • Technical specs table")
    print("     • vCPU, RAM, Storage, Bandwidth, IPs")
    print("")
    print("  4. Dashboard")
    print("     • Deal counts by status/category")
    print("     • Price statistics")
    print("     • Top providers")
    print(f"     • Last updated: {datetime.now():%Y-%m-%d %H:%M}")
    print("")
    print("  5. Raw Data")
    print("     • Complete JSON export")
    
    # Summary comparison
    print("\n" + "=" * 70)
    print("📊 COMPARISON: Old vs New")
    print("=" * 70)
    
    print("\n❌ OLD: Power Query Workflow")
    print("   1. Open Excel → Data → Get Data → From Web")
    print("   2. Enter URL: https://lowendtalk.com/discussions/p1")
    print("   3. Wait... Click... Select table...")
    print("   4. Formula in Column F: =IF(COUNTIF(...), 'DUPLICATE', 'UNIQUE')")
    print("   5. Manually copy-paste to Offer Details sheet")
    print("   6. Manually update Dashboard numbers")
    print("   ⏱️  Time: 10-15 minutes")
    print("   🐛 Can break, manual errors, inconsistent")
    
    print("\n✅ NEW: Deterministic Automation")
    print("   $ let-automation sync")
    print("   ⏱️  Time: 30 seconds")
    print("   ✅ No manual steps, always consistent, reliable")
    
    print("\n" + "=" * 70)
    print("✨ Demo complete! Run 'let-automation sync' to try it.")
    print("=" * 70)


if __name__ == "__main__":
    main()
