"""Compute the SHA-256 of docs/hypotheses.md with normalised line endings.

Usage: python tools/prereg_hash.py [--write]
The lock file docs/prereg-v1.lock holds the expected hash (see docs/hypotheses.md section 0.8).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HYP = ROOT / "docs" / "hypotheses.md"
LOCK = ROOT / "docs" / "prereg-v1.lock"


def hypotheses_hash() -> str:
    text = HYP.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(text).hexdigest()


if __name__ == "__main__":
    h = hypotheses_hash()
    if "--write" in sys.argv:
        LOCK.write_text(h + "\n", encoding="utf-8")
    print(h)
