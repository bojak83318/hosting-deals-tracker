#!/usr/bin/env python3
"""
LLM Router for LowEndTalk Hosting Deals Automation

Routes natural language commands to appropriate workflow actions.
Uses local LLM (via Ollama/lmstudio) or API (Claude/OpenAI) for intent parsing.

Usage:
    python llm_router.py "Find all VPS deals under $20 from LowEndTalk"
    python llm_router.py "Update my Excel with today's deals"
    python llm_router.py "Sync deals to GitHub and create PR"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Try to import LLM client
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class WorkflowIntent:
    """Parsed intent from natural language."""
    action: str  # discover, extract, sync, update
    target: str  # lowendtalk, github, excel
    filters: dict[str, Any]  # price_max, provider, etc.
    destination: str | None  # excel, github, both
    priority: str  # high, normal, low


class LLMRouter:
    """Routes natural language to workflow commands."""
    
    # System prompt for intent parsing
    SYSTEM_PROMPT = """You are an intelligent workflow router for a hosting deals automation system.

Your job is to parse natural language requests and output structured JSON commands.

Available actions:
- "discover": Run spectral discovery on a website to find API endpoints
- "extract": Scrape/extract deals data from a source
- "sync": Sync data between sources (e.g., GitHub, Excel)
- "update": Update existing data store
- "analyze": Analyze deals for patterns/best value
- "report": Generate a report of deals

Available targets:
- "lowendtalk" or "let": LowEndTalk.com forum
- "github": GitHub repository for storage
- "excel": Excel spreadsheet @Hosting-Deals-Tracker.xlsx

Available destinations:
- "excel": Update Excel file
- "github": Push to GitHub
- "both": Update both Excel and GitHub
- "console": Just print to console

Parse the user's request and return ONLY a JSON object in this format:
{
    "action": "extract|discover|sync|update|analyze|report",
    "target": "lowendtalk|github|excel",
    "filters": {
        "price_max": number|null,
        "price_min": number|null,
        "provider": string|null,
        "category": "vps|dedi|shared|null",
        "region": string|null,
        "timeframe": "today|week|month|all"
    },
    "destination": "excel|github|both|console",
    "priority": "high|normal|low",
    "rationale": "Brief explanation of your parsing"
}

Rules:
1. If user mentions "under $X" or "less than $X", set price_max
2. If user mentions "VPS", "dedicated", "shared", set category
3. If user mentions provider names, set provider filter
4. Default timeframe is "today" for sync/update, "week" for extract
5. If multiple destinations mentioned, use "both"
"""

    def __init__(self, provider: str = "claude", api_key: str | None = None):
        self.provider = provider
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.client = None
        
        if provider == "claude" and ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        elif provider == "openai" and OPENAI_AVAILABLE and self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
    
    def parse_intent(self, user_input: str) -> WorkflowIntent:
        """Parse natural language into structured intent."""
        
        # Try LLM parsing if available
        if self.client:
            return self._parse_with_llm(user_input)
        else:
            # Fallback to rule-based parsing
            return self._parse_rule_based(user_input)
    
    def _parse_with_llm(self, user_input: str) -> WorkflowIntent:
        """Use LLM to parse intent."""
        
        if self.provider == "claude":
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_input}]
            )
            content = response.content[0].text
        else:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ]
            )
            content = response.choices[0].message.content
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = json.loads(content)
        
        return WorkflowIntent(
            action=parsed.get("action", "extract"),
            target=parsed.get("target", "lowendtalk"),
            filters=parsed.get("filters", {}),
            destination=parsed.get("destination", "console"),
            priority=parsed.get("priority", "normal")
        )
    
    def _parse_rule_based(self, user_input: str) -> WorkflowIntent:
        """Rule-based parsing fallback (no LLM needed)."""
        
        text = user_input.lower()
        
        # Determine action
        if any(w in text for w in ["discover", "find api", "reverse engineer"]):
            action = "discover"
        elif any(w in text for w in ["sync", "push", "commit"]):
            action = "sync"
        elif any(w in text for w in ["update", "refresh"]):
            action = "update"
        elif any(w in text for w in ["analyze", "compare", "best"]):
            action = "analyze"
        elif any(w in text for w in ["report", "summary", "list"]):
            action = "report"
        else:
            action = "extract"
        
        # Determine target
        if any(w in text for w in ["lowendtalk", "let", "forum"]):
            target = "lowendtalk"
        elif any(w in text for w in ["github", "repo", "git"]):
            target = "github"
        elif any(w in text for w in ["excel", "spreadsheet", "xlsx"]):
            target = "excel"
        else:
            target = "lowendtalk"
        
        # Determine destination
        if "excel" in text and "github" in text:
            destination = "both"
        elif "excel" in text or "spreadsheet" in text:
            destination = "excel"
        elif "github" in text or "git" in text:
            destination = "github"
        else:
            destination = "console"
        
        # Parse filters
        filters: dict[str, Any] = {
            "price_max": None,
            "price_min": None,
            "provider": None,
            "category": None,
            "region": None,
            "timeframe": "today"
        }
        
        # Price filter
        price_match = re.search(r'(?:under|less than|below|\$)(\d+)', text)
        if price_match:
            filters["price_max"] = int(price_match.group(1))
        
        price_range = re.search(r'(\d+)\s*-\s*(\d+)', text)
        if price_range:
            filters["price_min"] = int(price_range.group(1))
            filters["price_max"] = int(price_range.group(2))
        
        # Category filter
        if "vps" in text:
            filters["category"] = "vps"
        elif "dedicated" in text or "dedi" in text:
            filters["category"] = "dedicated"
        elif "shared" in text or "hosting" in text:
            filters["category"] = "shared"
        
        # Provider filter
        providers = ["racknerd", "buyvm", "virmach", "greencloud", "hetzner", "contabo"]
        for provider in providers:
            if provider in text:
                filters["provider"] = provider
                break
        
        # Timeframe
        if "today" in text:
            filters["timeframe"] = "today"
        elif "week" in text or "this week" in text:
            filters["timeframe"] = "week"
        elif "month" in text:
            filters["timeframe"] = "month"
        
        return WorkflowIntent(
            action=action,
            target=target,
            filters=filters,
            destination=destination,
            priority="normal"
        )
    
    def route(self, intent: WorkflowIntent) -> dict[str, Any]:
        """Convert intent to executable workflow configuration."""
        
        workflow = {
            "name": f"{intent.action}_{intent.target}",
            "steps": [],
            "config": {}
        }
        
        # Build workflow based on intent
        if intent.action == "discover":
            workflow["steps"] = [
                {"tool": "spectral_nodriver", "action": "discover", "target": "https://lowendtalk.com"}
            ]
        
        elif intent.action == "extract":
            workflow["steps"] = [
                {"tool": "let_scraper", "action": "scrape", "filters": intent.filters},
                {"tool": "processor", "action": "parse_deals", "filters": intent.filters}
            ]
            
            # Add output steps based on destination
            if intent.destination in ["excel", "both"]:
                workflow["steps"].append({"tool": "excel_sync", "action": "update"})
            if intent.destination in ["github", "both"]:
                workflow["steps"].append({"tool": "github_sync", "action": "commit"})
        
        elif intent.action == "sync":
            workflow["steps"] = [
                {"tool": "let_scraper", "action": "scrape", "filters": {"timeframe": intent.filters.get("timeframe", "today")}},
                {"tool": "excel_sync", "action": "update"},
                {"tool": "github_sync", "action": "commit"}
            ]
        
        elif intent.action == "update":
            if intent.target == "excel":
                workflow["steps"].append({"tool": "excel_sync", "action": "update"})
            elif intent.target == "github":
                workflow["steps"].append({"tool": "github_sync", "action": "commit"})
        
        workflow["config"] = {
            "destination": intent.destination,
            "filters": intent.filters,
            "priority": intent.priority
        }
        
        return workflow


def main():
    parser = argparse.ArgumentParser(description="LLM Router for LET automation")
    parser.add_argument("command", help="Natural language command")
    parser.add_argument("--provider", default="claude", choices=["claude", "openai", "rule"])
    parser.add_argument("--api-key", help="API key for LLM provider")
    parser.add_argument("--dry-run", action="store_true", help="Show parsed intent without executing")
    parser.add_argument("--output", "-o", help="Output workflow JSON to file")
    
    args = parser.parse_args()
    
    # Initialize router
    router = LLMRouter(provider=args.provider, api_key=args.api_key)
    
    # Parse intent
    print(f"🎯 Parsing: \"{args.command}\"")
    intent = router.parse_intent(args.command)
    
    print(f"\n📋 Parsed Intent:")
    print(f"   Action: {intent.action}")
    print(f"   Target: {intent.target}")
    print(f"   Destination: {intent.destination}")
    print(f"   Filters: {json.dumps(intent.filters, indent=2)}")
    
    # Route to workflow
    workflow = router.route(intent)
    
    print(f"\n⚙️  Generated Workflow: {workflow['name']}")
    print(f"   Steps:")
    for i, step in enumerate(workflow["steps"], 1):
        print(f"     {i}. {step['tool']}: {step['action']}")
    
    if args.output:
        Path(args.output).write_text(json.dumps(workflow, indent=2))
        print(f"\n💾 Workflow saved to: {args.output}")
    
    if args.dry_run:
        print("\n🏁 Dry run - not executing")
        return
    
    # Execute workflow
    print("\n🚀 Executing workflow...")
    # Import and run executor
    sys.path.insert(0, str(Path(__file__).parent.parent / "workflows"))
    from workflow_executor import execute_workflow
    execute_workflow(workflow)


if __name__ == "__main__":
    main()
