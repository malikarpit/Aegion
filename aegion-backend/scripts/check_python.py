#!/usr/bin/env python3
"""
Aegion Backend - Python Version Check.

Ensures the correct Python version is being used.
Minimum required: Python 3.12
"""

import sys
import warnings

MINIMUM_VERSION = (3, 12)
RECOMMENDED_VERSION = (3, 12)


def check_python_version():
    """Check Python version and warn if below minimum."""
    current = sys.version_info[:2]
    
    if current < MINIMUM_VERSION:
        print(f"❌ ERROR: Python {MINIMUM_VERSION[0]}.{MINIMUM_VERSION[1]}+ required")
        print(f"   Current version: Python {current[0]}.{current[1]}")
        print()
        print("   To fix this issue:")
        print("   1. Install Python 3.12: brew install python@3.12")
        print("   2. Create a new venv: python3.12 -m venv .venv")
        print("   3. Activate: source .venv/bin/activate")
        print("   4. Install deps: pip install -e .")
        sys.exit(1)
    
    if current < RECOMMENDED_VERSION:
        warnings.warn(
            f"Python {current[0]}.{current[1]} is below recommended version "
            f"{RECOMMENDED_VERSION[0]}.{RECOMMENDED_VERSION[1]}. "
            "Consider upgrading for best performance.",
            DeprecationWarning
        )
    
    return True


def main():
    """Entry point."""
    if check_python_version():
        print(f"✅ Python {sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]} - OK")


if __name__ == "__main__":
    main()
