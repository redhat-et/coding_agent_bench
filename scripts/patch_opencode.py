#!/usr/bin/env python3
"""Patch harbor's opencode.py to comment out the unknown-provider ValueError.

Locates the installed opencode.py in the current virtual environment and
ensures the `else: raise ValueError(...)` block for unknown providers is
commented out. Safe to run multiple times (idempotent).
"""

import site
import sys
import textwrap
from pathlib import Path

RELATIVE_PATH = Path(
    "harbor/agents/installed/opencode.py"
)

UNCOMMENTED = """\
        else:
            raise ValueError(
                f"Unknown provider {provider}. If you believe this provider "
                "should be supported, please contact the maintainers."
            )
"""

COMMENTED = """\
        # else:
        #     raise ValueError(
        #         f"Unknown provider {provider}. If you believe this provider "
        #         "should be supported, please contact the maintainers."
        #     )
"""


def find_opencode() -> Path:
    """Find opencode.py in the active virtual environment's site-packages."""
    for d in site.getsitepackages():
        candidate = Path(d) / RELATIVE_PATH
        if candidate.exists():
            return candidate

    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        candidate = Path(user_site) / RELATIVE_PATH
        if candidate.exists():
            return candidate

    print("ERROR: Could not find opencode.py in site-packages.", file=sys.stderr)
    sys.exit(1)


def main():
    path = find_opencode()
    print(f"Found: {path}")

    content = path.read_text()

    if COMMENTED in content:
        print("Already patched — nothing to do.")
        return

    if UNCOMMENTED not in content:
        print(
            "WARNING: Could not find the expected else/raise block "
            "(commented or uncommented). The file may have changed upstream.",
            file=sys.stderr,
        )
        sys.exit(1)

    patched = content.replace(UNCOMMENTED, COMMENTED)
    path.write_text(patched)
    print("Patched successfully.")


if __name__ == "__main__":
    main()
