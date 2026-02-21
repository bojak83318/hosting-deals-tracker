#!/usr/bin/env python3
"""
GitHub Sync Module for LowEndTalk Deals

Syncs hosting deals to a GitHub repository as structured data (JSON/YAML).
Supports creating commits, PRs, and maintaining historical data.

Usage:
    python github_uploader.py --deals deals.json --repo owner/name
    python github_uploader.py --auto-sync  # Use config file
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


class GitHubDealsSync:
    """Sync deals to GitHub repository."""
    
    DEFAULT_REPO = "hosting-deals-data"
    DEFAULT_BRANCH = "main"
    DATA_PATH = "data/deals"
    
    def __init__(self, token: str | None = None, repo: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPO", self.DEFAULT_REPO)
        
        if not self.token:
            raise ValueError("GitHub token required. Set GITHUB_TOKEN env var.")
        
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Parse repo
        if "/" in self.repo:
            self.owner, self.repo_name = self.repo.split("/", 1)
        else:
            self.owner = os.getenv("GITHUB_USER", "unknown")
            self.repo_name = self.repo
    
    def ensure_repo_exists(self, private: bool = False, description: str = "") -> bool:
        """Create repo if it doesn't exist."""
        
        # Check if repo exists
        resp = requests.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}",
            headers=self.headers
        )
        
        if resp.status_code == 200:
            print(f"✅ Repo exists: {self.owner}/{self.repo_name}")
            return True
        
        # Create repo
        print(f"📁 Creating repo: {self.owner}/{self.repo_name}")
        resp = requests.post(
            f"{self.api_base}/user/repos",
            headers=self.headers,
            json={
                "name": self.repo_name,
                "private": private,
                "description": description or "Hosting deals data from LowEndTalk",
                "auto_init": True
            }
        )
        
        if resp.status_code == 201:
            print(f"✅ Repo created")
            return True
        else:
            print(f"❌ Failed to create repo: {resp.status_code}")
            print(resp.text)
            return False
    
    def upload_deals(self, deals: list[dict], date: str | None = None, 
                     message: str | None = None) -> bool:
        """Upload deals as JSON file to repo."""
        
        date = date or datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.DATA_PATH}/deals_{date}.json"
        
        content = json.dumps(deals, indent=2, ensure_ascii=False)
        
        return self._create_or_update_file(
            path=filename,
            content=content,
            message=message or f"Update deals for {date}"
        )
    
    def upload_deals_yaml(self, deals: list[dict], date: str | None = None,
                          message: str | None = None) -> bool:
        """Upload deals as YAML file."""
        
        try:
            import yaml
        except ImportError:
            print("❌ PyYAML required: pip install pyyaml")
            return False
        
        date = date or datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.DATA_PATH}/deals_{date}.yaml"
        
        content = yaml.dump(deals, allow_unicode=True, sort_keys=False)
        
        return self._create_or_update_file(
            path=filename,
            content=content,
            message=message or f"Update deals for {date}"
        )
    
    def upload_summary(self, summary: dict) -> bool:
        """Upload summary statistics."""
        
        filename = "data/summary.json"
        summary["last_updated"] = datetime.now().isoformat()
        content = json.dumps(summary, indent=2)
        
        return self._create_or_update_file(
            path=filename,
            content=content,
            message="Update summary statistics"
        )
    
    def create_deals_pr(self, deals: list[dict], branch_name: str | None = None) -> str | None:
        """Create a PR with new deals."""
        
        branch_name = branch_name or f"deals-{datetime.now():%Y%m%d-%H%M%S}"
        base_branch = self._get_default_branch()
        
        # Create branch
        if not self._create_branch(branch_name, base_branch):
            return None
        
        # Upload deals to branch
        date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.DATA_PATH}/deals_{date}.json"
        content = json.dumps(deals, indent=2, ensure_ascii=False)
        
        if not self._create_or_update_file(
            path=filename,
            content=content,
            message=f"Add deals for {date}",
            branch=branch_name
        ):
            return None
        
        # Create PR
        resp = requests.post(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/pulls",
            headers=self.headers,
            json={
                "title": f"Hosting Deals Update - {date}",
                "head": branch_name,
                "base": base_branch,
                "body": f"Automated update of hosting deals from LowEndTalk\\n\\nDeals added: {len(deals)}"
            }
        )
        
        if resp.status_code == 201:
            pr_url = resp.json()["html_url"]
            print(f"✅ PR created: {pr_url}")
            return pr_url
        else:
            print(f"❌ Failed to create PR: {resp.status_code}")
            return None
    
    def sync_from_excel(self, excel_path: Path) -> bool:
        """Sync deals from Excel file to GitHub."""
        
        try:
            import pandas as pd
        except ImportError:
            print("❌ pandas required: pip install pandas openpyxl")
            return False
        
        print(f"📊 Reading Excel: {excel_path}")
        df = pd.read_excel(excel_path)
        
        # Convert to list of dicts
        deals = df.to_dict("records")
        
        print(f"   Found {len(deals)} deals")
        
        # Upload to GitHub
        return self.upload_deals(deals) and self.upload_deals_yaml(deals)
    
    def _create_or_update_file(self, path: str, content: str, 
                               message: str, branch: str | None = None) -> bool:
        """Create or update a file in the repo."""
        
        # Check if file exists
        resp = requests.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/contents/{path}",
            headers=self.headers,
            params={"ref": branch or self.DEFAULT_BRANCH}
        )
        
        data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode()
        }
        
        if branch:
            data["branch"] = branch
        
        if resp.status_code == 200:
            # File exists, update it
            data["sha"] = resp.json()["sha"]
            print(f"📝 Updating: {path}")
        else:
            print(f"➕ Creating: {path}")
        
        resp = requests.put(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/contents/{path}",
            headers=self.headers,
            json=data
        )
        
        if resp.status_code in [200, 201]:
            print(f"✅ Success: {path}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code}")
            print(resp.text)
            return False
    
    def _get_default_branch(self) -> str:
        """Get default branch name."""
        resp = requests.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}",
            headers=self.headers
        )
        if resp.status_code == 200:
            return resp.json().get("default_branch", "main")
        return "main"
    
    def _create_branch(self, branch_name: str, base_branch: str) -> bool:
        """Create a new branch."""
        
        # Get base branch SHA
        resp = requests.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/git/refs/heads/{base_branch}",
            headers=self.headers
        )
        
        if resp.status_code != 200:
            print(f"❌ Failed to get base branch: {resp.status_code}")
            return False
        
        base_sha = resp.json()["object"]["sha"]
        
        # Create branch
        resp = requests.post(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/git/refs",
            headers=self.headers,
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
        )
        
        if resp.status_code == 201:
            print(f"🌿 Created branch: {branch_name}")
            return True
        else:
            print(f"❌ Failed to create branch: {resp.status_code}")
            return False
    
    def list_deals_files(self) -> list[dict]:
        """List all deals files in the repo."""
        
        resp = requests.get(
            f"{self.api_base}/repos/{self.owner}/{self.repo_name}/contents/{self.DATA_PATH}",
            headers=self.headers
        )
        
        if resp.status_code == 200:
            return [item for item in resp.json() if item["name"].startswith("deals_")]
        elif resp.status_code == 404:
            return []
        else:
            print(f"❌ Failed to list files: {resp.status_code}")
            return []


def main():
    parser = argparse.ArgumentParser(description="GitHub sync for LET deals")
    parser.add_argument("--repo", "-r", help="GitHub repo (owner/name)")
    parser.add_argument("--token", "-t", help="GitHub token")
    parser.add_argument("--deals", "-d", type=Path, help="Deals JSON file")
    parser.add_argument("--excel", "-e", type=Path, help="Excel file to sync")
    parser.add_argument("--pr", action="store_true", help="Create PR instead of direct commit")
    parser.add_argument("--setup", action="store_true", help="Create repo if not exists")
    
    args = parser.parse_args()
    
    sync = GitHubDealsSync(token=args.token, repo=args.repo)
    
    if args.setup:
        sync.ensure_repo_exists()
    
    if args.excel:
        sync.sync_from_excel(args.excel)
    
    elif args.deals:
        deals = json.loads(args.deals.read_text())
        
        if args.pr:
            sync.create_deals_pr(deals)
        else:
            sync.upload_deals(deals)
            sync.upload_deals_yaml(deals)


if __name__ == "__main__":
    main()
