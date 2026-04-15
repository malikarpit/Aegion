"""
AEGION Master Test Runner
=========================
Runs ALL tests across backend, extension, and frontend.
Generates a unified pass/fail report.

Usage:
    python tests/master_runner.py             # Run all
    python tests/master_runner.py --unit      # Unit only
    python tests/master_runner.py --e2e       # E2E only
    python tests/master_runner.py --report    # Generate HTML report afterwards
"""

import subprocess
import sys
import time
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

# ── Colors ────────────────────────────────────────────────────────────────────
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class TestSuiteResult:
    name: str
    passed: bool
    duration_s: float
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    errors: List[str] = field(default_factory=list)
    output: str = ""


# ── Runner ────────────────────────────────────────────────────────────────────

def run_command(name: str, cmd: List[str], cwd: str, timeout: int = 300) -> TestSuiteResult:
    """Run a test command and capture results."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}Running: {name}{RESET}")
    print(f"{YELLOW}  Command: {' '.join(cmd)}{RESET}")
    print(f"{YELLOW}  Dir:     {cwd}{RESET}")
    print()

    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start
        output = result.stdout + result.stderr

        # Print live output
        print(output[-3000:] if len(output) > 3000 else output)

        passed = result.returncode == 0
        return TestSuiteResult(
            name=name,
            passed=passed,
            duration_s=round(duration, 2),
            output=output,
        )

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        msg = f"TIMEOUT after {timeout}s"
        print(f"{RED}{msg}{RESET}")
        return TestSuiteResult(name=name, passed=False, duration_s=round(duration, 2), errors=[msg])

    except FileNotFoundError as e:
        duration = time.monotonic() - start
        msg = f"Command not found: {e}"
        print(f"{RED}{msg}{RESET}")
        return TestSuiteResult(name=name, passed=False, duration_s=round(duration, 2), errors=[msg])


def parse_pytest_results(output: str, result: TestSuiteResult) -> TestSuiteResult:
    """Extract passed/failed counts from pytest output."""
    import re
    # Match: "87 passed, 3 failed, 2 warnings in 12.34s"
    match = re.search(r"(\d+) passed", output)
    if match:
        result.passed_count = int(match.group(1))
    match = re.search(r"(\d+) failed", output)
    if match:
        result.failed_count = int(match.group(1))
    result.total = result.passed_count + result.failed_count
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    run_unit = "--unit" in args or not args
    run_integration = "--integration" in args or not args
    run_e2e = "--e2e" in args or not args
    run_extension = "--extension" in args or not args
    run_frontend = "--frontend" in args or not args
    run_playwright = "--playwright" in args or not args
    generate_report = "--report" in args

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_root = os.path.join(project_root, "aegion-backend")
    extension_root = os.path.join(project_root, "aegion-vscode")
    frontend_root = os.path.join(project_root, "aegion-frontend")

    results: List[TestSuiteResult] = []
    overall_start = time.monotonic()

    print(f"\n{BOLD}{'='*60}")
    print("  AEGION MASTER TEST RUNNER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}{RESET}\n")

    # ── 1. Backend Unit Tests ────────────────────────────────────────────
    if run_unit:
        r = run_command(
            "Backend Unit Tests (87 files)",
            ["python", "-m", "pytest", "tests/unit/", "-x", "--tb=short", "-q",
             "--cov=app", "--cov-report=term-missing:skip-covered"],
            cwd=backend_root,
            timeout=300,
        )
        r = parse_pytest_results(r.output, r)
        results.append(r)

    # ── 2. Backend Integration Tests ────────────────────────────────────
    if run_integration:
        r = run_command(
            "Backend Integration Tests (19 files)",
            ["python", "-m", "pytest", "tests/integration/", "-x", "--tb=short", "-q"],
            cwd=backend_root,
            timeout=180,
        )
        r = parse_pytest_results(r.output, r)
        results.append(r)

    # ── 3. Backend E2E Tests ─────────────────────────────────────────────
    if run_e2e:
        r = run_command(
            "Backend E2E Tests",
            ["python", "-m", "pytest", "tests/e2e/", "-x", "--tb=short", "-v"],
            cwd=backend_root,
            timeout=300,
        )
        r = parse_pytest_results(r.output, r)
        results.append(r)

    # ── 4. Extension TypeScript Tests ────────────────────────────────────
    if run_extension and os.path.isdir(extension_root):
        r = run_command(
            "VS Code Extension Tests (TypeScript)",
            ["npm", "test"],
            cwd=extension_root,
            timeout=120,
        )
        results.append(r)

    # ── 5. Frontend Unit Tests (Vitest) ──────────────────────────────────
    if run_frontend and os.path.isdir(frontend_root):
        r = run_command(
            "Frontend Unit Tests (Vitest)",
            ["npm", "run", "test", "--", "--run"],
            cwd=frontend_root,
            timeout=120,
        )
        results.append(r)

    # ── 6. Frontend Playwright E2E ───────────────────────────────────────
    if run_playwright and os.path.isdir(frontend_root):
        r = run_command(
            "Frontend Playwright E2E Tests",
            ["npx", "playwright", "test", "--reporter=list"],
            cwd=frontend_root,
            timeout=300,
        )
        results.append(r)

    # ── Final Report ────────────────────────────────────────────────────
    total_duration = time.monotonic() - overall_start

    print(f"\n{BOLD}{'='*60}")
    print("  MASTER TEST REPORT")
    print(f"  Duration: {total_duration:.1f}s")
    print(f"{'='*60}{RESET}\n")

    all_passed = True
    for r in results:
        status = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        detail = ""
        if r.total > 0:
            detail = f"  ({r.passed_count}/{r.total} tests)"
        print(f"  [{status}] {r.name}{detail} — {r.duration_s}s")
        if not r.passed:
            all_passed = False
            for err in r.errors:
                print(f"           {RED}→ {err}{RESET}")

    print()
    if all_passed:
        print(f"  {GREEN}{BOLD}✅ ALL SUITES PASSED — Aegion is production-ready!{RESET}")
    else:
        failed = [r.name for r in results if not r.passed]
        print(f"  {RED}{BOLD}❌ FAILED: {', '.join(failed)}{RESET}")
        print(f"  {YELLOW}  → Fix failing tests before proceeding.{RESET}")

    print()

    # ── JSON Report ─────────────────────────────────────────────────────
    if generate_report:
        report = {
            "generated_at": datetime.now().isoformat(),
            "all_passed": all_passed,
            "duration_s": round(total_duration, 2),
            "suites": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration_s": r.duration_s,
                    "total": r.total,
                    "passed_count": r.passed_count,
                    "failed_count": r.failed_count,
                    "errors": r.errors,
                }
                for r in results
            ],
        }
        report_path = os.path.join(project_root, "test-report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Report written to: {report_path}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
