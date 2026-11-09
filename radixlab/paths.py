"""Locations of data directories (cell libraries, experiments, results)."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("RADIXLAB_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def cells_dir() -> Path:
    env = os.environ.get("RADIXLAB_CELLS")
    if env:
        return Path(env)
    return repo_root() / "cells"


def results_dir() -> Path:
    return repo_root() / "results"
