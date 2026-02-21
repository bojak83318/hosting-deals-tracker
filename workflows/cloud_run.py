#!/usr/bin/env python3
"""
Cloud runner for LET automation.

Pipeline:
Run button -> GitHub Actions -> LLM router -> Spectral -> LowEndTalk -> Excel
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE / "router"))
sys.path.insert(0, str(WORKSPACE / "workflows"))

from llm_router import LLMRouter  # noqa: E402
from auto_sync import AutoSyncWorkflow  # noqa: E402


def run_spectral_step(skip: bool) -> dict[str, Any]:
    """Run spectral discovery as a best-effort step."""
    if skip:
        return {"status": "skipped", "reason": "--skip-spectral requested"}

    script = WORKSPACE / "spectral-bridge" / "let_spectral.py"
    if not script.exists():
        return {"status": "skipped", "reason": f"{script} not found"}

    cmd = [sys.executable, str(script), "discover", "--no-interactive"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    return {
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1200:],
        "stderr_tail": result.stderr[-1200:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cloud LET automation pipeline")
    parser.add_argument(
        "--command",
        default="Sync latest LowEndTalk deals to excel and github",
        help="Natural language routing command",
    )
    parser.add_argument(
        "--provider",
        default="rule",
        choices=["rule", "claude", "openai"],
        help="Router provider for intent parsing",
    )
    parser.add_argument("--api-key", help="Optional API key for router provider")
    parser.add_argument(
        "--excel-file",
        type=Path,
        default=WORKSPACE / "output" / "Hosting-Deals-Tracker.xlsx",
        help="Excel output path",
    )
    parser.add_argument("--skip-spectral", action="store_true")
    parser.add_argument(
        "--report-json",
        type=Path,
        default=WORKSPACE / "output" / "cloud_run_report.json",
        help="Path to write execution report",
    )

    args = parser.parse_args()
    args.excel_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.parent.mkdir(parents=True, exist_ok=True)

    print(f"[cloud-run] started={datetime.now(timezone.utc).isoformat()}")
    print(f"[cloud-run] command={args.command}")

    router = LLMRouter(provider=args.provider, api_key=args.api_key)
    intent = router.parse_intent(args.command)
    workflow = router.route(intent)

    print(
        f"[cloud-run] route action={intent.action} target={intent.target} "
        f"destination={intent.destination}"
    )

    spectral_result = run_spectral_step(skip=args.skip_spectral)
    print(f"[cloud-run] spectral={spectral_result['status']}")

    sync_github = intent.destination in {"github", "both"}
    auto_sync = AutoSyncWorkflow(config={"excel_file": str(args.excel_file)})
    success = auto_sync.run(dry_run=False, github=sync_github)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_command": args.command,
        "router_provider": args.provider,
        "intent": {
            "action": intent.action,
            "target": intent.target,
            "filters": intent.filters,
            "destination": intent.destination,
            "priority": intent.priority,
        },
        "workflow": workflow,
        "spectral": spectral_result,
        "auto_sync_success": success,
        "excel_file": str(args.excel_file),
        "results": auto_sync.results,
        "errors": auto_sync.errors,
    }
    args.report_json.write_text(json.dumps(report, indent=2))
    print(f"[cloud-run] report={args.report_json}")
    print(f"[cloud-run] excel={args.excel_file}")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
