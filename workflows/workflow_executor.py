#!/usr/bin/env python3
"""
Workflow Executor for LET Automation

Orchestrates the complete pipeline:
LLM Router -> Spectral Bridge -> LowEndTalk -> GitHub -> Excel

Usage:
    python workflow_executor.py --workflow workflows/discover_and_sync.yaml
    python workflow_executor.py --command "Find VPS deals under $10 and sync to GitHub"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent to path for imports
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))


class WorkflowExecutor:
    """Executes automation workflows."""
    
    def __init__(self):
        self.results: list[dict] = []
        self.errors: list[str] = []
    
    def execute_workflow(self, workflow: dict[str, Any]) -> bool:
        """Execute a workflow configuration."""
        
        print("=" * 70)
        print(f"🚀 Executing Workflow: {workflow.get('name', 'unnamed')}")
        print("=" * 70)
        print(f"   Started: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"   Steps: {len(workflow.get('steps', []))}")
        print()
        
        steps = workflow.get("steps", [])
        config = workflow.get("config", {})
        
        for i, step in enumerate(steps, 1):
            tool = step.get("tool")
            action = step.get("action")
            
            print(f"\n📍 Step {i}/{len(steps)}: {tool}.{action}")
            print("-" * 40)
            
            success = self._execute_step(step, config)
            
            if success:
                print(f"   ✅ Success")
            else:
                print(f"   ❌ Failed")
                if step.get("required", True):
                    print("   Workflow halted (required step failed)")
                    return False
            
            time.sleep(0.5)  # Brief pause between steps
        
        print("\n" + "=" * 70)
        print("✅ Workflow Complete")
        print("=" * 70)
        return True
    
    def _execute_step(self, step: dict, config: dict) -> bool:
        """Execute a single workflow step."""
        
        tool = step.get("tool")
        action = step.get("action")
        
        try:
            if tool == "spectral_nodriver":
                return self._run_spectral_nodriver(action, step)
            
            elif tool == "let_spectral":
                return self._run_let_spectral(action, step)
            
            elif tool == "let_scraper":
                return self._run_let_scraper(action, step, config)
            
            elif tool == "processor":
                return self._run_processor(action, step, config)
            
            elif tool == "github_sync":
                return self._run_github_sync(action, step)
            
            elif tool == "excel_sync":
                return self._run_excel_sync(action, step)
            
            elif tool == "llm_router":
                return self._run_llm_router(action, step)
            
            else:
                print(f"   Unknown tool: {tool}")
                return False
        
        except Exception as e:
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _run_spectral_nodriver(self, action: str, step: dict) -> bool:
        """Run spectral-nodriver tool."""
        
        script = Path.home() / "workspace" / "spectral-nodriver" / "spectral_nodriver.py"
        
        if not script.exists():
            print(f"   spectral-nodriver not found at {script}")
            return False
        
        target = step.get("target", "https://lowendtalk.com")
        
        cmd = [sys.executable, str(script), action, target]
        
        if step.get("interactive"):
            cmd.append("--interactive")
        
        result = subprocess.run(cmd)
        return result.returncode == 0
    
    def _run_let_spectral(self, action: str, step: dict) -> bool:
        """Run LET spectral bridge."""
        
        script = WORKSPACE / "spectral-bridge" / "let_spectral.py"
        
        if not script.exists():
            print(f"   let_spectral not found at {script}")
            return False
        
        cmd = [sys.executable, str(script), action]
        
        if step.get("interactive"):
            cmd.append("--interactive")
        
        result = subprocess.run(cmd)
        return result.returncode == 0
    
    def _run_let_scraper(self, action: str, step: dict, config: dict) -> bool:
        """Run the LET scraper (existing tool)."""
        
        # Check if existing scraper exists
        scraper = Path.home() / "workspace" / "let-scraper" / "scraper-nodriver.py"
        
        if scraper.exists():
            print(f"   Using existing scraper: {scraper}")
            # Run the scraper
            result = subprocess.run([sys.executable, str(scraper)])
            return result.returncode == 0
        else:
            print("   No existing scraper found, skipping")
            return True  # Not a hard failure
    
    def _run_processor(self, action: str, step: dict, config: dict) -> bool:
        """Process/scrape deals data."""
        
        filters = step.get("filters", {})
        print(f"   Processing with filters: {filters}")
        
        # In a real implementation, this would parse scraped data
        # For now, simulate processing
        deals = self._simulate_deal_extraction(filters)
        
        # Save deals for downstream steps
        output_file = Path.home() / ".let-automation" / "processed_deals.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(deals, indent=2))
        
        print(f"   Processed {len(deals)} deals")
        print(f"   Saved to: {output_file}")
        
        return True
    
    def _run_github_sync(self, action: str, step: dict) -> bool:
        """Sync to GitHub."""
        
        script = WORKSPACE / "github-sync" / "github_uploader.py"
        
        if not script.exists():
            print(f"   github_uploader not found at {script}")
            return False
        
        # Get deals file from previous step
        deals_file = Path.home() / ".let-automation" / "processed_deals.json"
        
        if not deals_file.exists():
            print("   No deals file to upload")
            return False
        
        cmd = [
            sys.executable, str(script),
            "--deals", str(deals_file)
        ]
        
        if action == "pr":
            cmd.append("--pr")
        
        result = subprocess.run(cmd)
        return result.returncode == 0
    
    def _run_excel_sync(self, action: str, step: dict) -> bool:
        """Sync to Excel."""
        
        script = WORKSPACE / "excel-sync" / "excel_manager.py"
        
        if not script.exists():
            print(f"   excel_manager not found at {script}")
            return False
        
        # Get deals file from previous step
        deals_file = Path.home() / ".let-automation" / "processed_deals.json"
        
        cmd = [sys.executable, str(script)]
        
        if deals_file.exists():
            cmd.extend(["--add", str(deals_file)])
        elif action == "stats":
            cmd.append("--stats")
        else:
            cmd.append("--list")
        
        result = subprocess.run(cmd)
        return result.returncode == 0
    
    def _run_llm_router(self, action: str, step: dict) -> bool:
        """Run LLM routing."""
        
        script = WORKSPACE / "router" / "llm_router.py"
        
        if not script.exists():
            print(f"   llm_router not found at {script}")
            return False
        
        command = step.get("command", "extract deals")
        
        cmd = [
            sys.executable, str(script),
            command,
            "--dry-run"
        ]
        
        result = subprocess.run(cmd)
        return result.returncode == 0
    
    def _simulate_deal_extraction(self, filters: dict) -> list[dict]:
        """Simulate deal extraction for demo purposes."""
        
        # In real implementation, this would parse actual scraped data
        sample_deals = [
            {
                "provider": "RackNerd",
                "plan_name": "Intel VPS 1GB",
                "price_usd": 10.99,
                "billing_cycle": "Yearly",
                "type": "VPS",
                "specs": "1GB RAM, 1 Core, 20GB SSD",
                "location": "US (Multiple)",
                "url": "https://lowendtalk.com/discussion/12345",
                "date_added": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "provider": "BuyVM",
                "plan_name": "KVM Slice 512MB",
                "price_usd": 2.00,
                "billing_cycle": "Monthly",
                "type": "VPS",
                "specs": "512MB RAM, 1 Core, 10GB SSD",
                "location": "Las Vegas",
                "url": "https://lowendtalk.com/discussion/12346",
                "date_added": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "provider": "Hetzner",
                "plan_name": "CX11",
                "price_usd": 3.79,
                "billing_cycle": "Monthly",
                "type": "VPS",
                "specs": "2GB RAM, 1 Core, 20GB NVMe",
                "location": "Germany",
                "url": "https://lowendtalk.com/discussion/12347",
                "date_added": datetime.now().strftime("%Y-%m-%d")
            }
        ]
        
        # Apply filters
        filtered = sample_deals
        
        if filters.get("price_max"):
            filtered = [d for d in filtered if d["price_usd"] <= filters["price_max"]]
        
        if filters.get("category"):
            filtered = [d for d in filtered if d["type"].lower() == filters["category"].lower()]
        
        if filters.get("provider"):
            filtered = [d for d in filtered if filters["provider"].lower() in d["provider"].lower()]
        
        return filtered


def execute_workflow(workflow: dict[str, Any]) -> bool:
    """Convenience function to execute a workflow."""
    executor = WorkflowExecutor()
    return executor.execute_workflow(workflow)


def load_workflow(path: Path) -> dict:
    """Load workflow from YAML or JSON file."""
    
    content = path.read_text()
    
    if path.suffix in [".yaml", ".yml"]:
        import yaml
        return yaml.safe_load(content)
    else:
        return json.loads(content)


def main():
    parser = argparse.ArgumentParser(description="Execute LET automation workflows")
    parser.add_argument("--workflow", "-w", type=Path, help="Workflow file (YAML/JSON)")
    parser.add_argument("--command", "-c", help="Natural language command")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute, just show plan")
    
    args = parser.parse_args()
    
    if args.workflow:
        workflow = load_workflow(args.workflow)
    elif args.command:
        # Generate workflow from command
        router = WORKSPACE / "router" / "llm_router.py"
        if router.exists():
            result = subprocess.run(
                [sys.executable, str(router), args.command, "--dry-run"],
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return
        else:
            print(f"LLM Router not found at {router}")
            return
    else:
        # Run default workflow
        workflow = {
            "name": "default_sync",
            "steps": [
                {"tool": "let_scraper", "action": "scrape"},
                {"tool": "processor", "action": "parse_deals"},
                {"tool": "excel_sync", "action": "update"},
                {"tool": "github_sync", "action": "commit"}
            ],
            "config": {"destination": "both"}
        }
    
    if args.dry_run:
        print("\n📋 Workflow Plan:")
        print(json.dumps(workflow, indent=2))
        return
    
    # Execute
    executor = WorkflowExecutor()
    success = executor.execute_workflow(workflow)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
