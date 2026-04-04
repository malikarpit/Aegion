#!/usr/bin/env python3
"""
Aegion Documentation Drift Detector CLI.

Identifies divergence between implementation and documentation.
Run this during CI/CD or locally before committing.

Usage:
    python3 scripts/detect_drift.py [path_to_scan]

Exit Code:
    0: No drift detected (or only warnings)
    1: Critical drift detected (errors)
"""

import sys
import os
import argparse

import importlib.util

# Dynamic import to avoid app package initialization dependencies
def import_drift_detector():
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "app/services/praxis/drift_detector.py")
    spec = importlib.util.spec_from_file_location("drift_detector", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["drift_detector"] = module
    spec.loader.exec_module(module)
    return module.DriftDetector, module.DriftIssue

DriftDetector, DriftIssue = import_drift_detector()


def main():
    parser = argparse.ArgumentParser(description="Scan codebase for documentation drift.")
    parser.add_argument("--path", default="app", help="Path to scan (relative to project root)")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    args = parser.parse_args()

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    detector = DriftDetector(root_dir)
    
    print(f"🔍 Scanning '{args.path}' for documentation drift...")
    issues = detector.scan_directory(args.path)

    if not issues:
        print("✅ No drift detected. Code and documentation are consistent.")
        sys.exit(0)

    # Group by file
    issues_by_file = {}
    error_count = 0
    warning_count = 0

    for issue in issues:
        if issue.file_path not in issues_by_file:
            issues_by_file[issue.file_path] = []
        issues_by_file[issue.file_path].append(issue)
        
        if issue.severity == "error":
            error_count += 1
        elif issue.severity == "warning":
            warning_count += 1

    # Print Report
    print("\n📋 Drift Report:")
    for file_path, file_issues in sorted(issues_by_file.items()):
        print(f"\n📄 {file_path}:")
        for issue in file_issues:
            icon = "🔴" if issue.severity == "error" else "🟡"
            print(f"  {icon} Line {issue.line}: {issue.message}")

    print(f"\nSummary: {error_count} Errors, {warning_count} Warnings")
    
    if error_count > 0:
        print("❌ Critical drift detected.")
        sys.exit(1)
        
    if args.strict and warning_count > 0:
        print("❌ Strict mode: Failed on warnings.")
        sys.exit(1)

    print("⚠️  Warnings detected, but passing (non-strict mode).")
    sys.exit(0)


if __name__ == "__main__":
    main()
