"""Configuration for NVIDIA NIM integration."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class NIMConfig:
    base_url: str = "https://integrate.api.nvidia.com/v1"
    default_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    fast_model: str = "deepseek-ai/deepseek-v4.1-flash"
    timeout_sec: float = 20.0
    max_retries: int = 2
    retry_delay_sec: float = 1.0
    cache_dir: Optional[Path] = None
    enabled: bool = True

    @classmethod
    def load(cls, path: Optional[Path] = None) -> NIMConfig:
        config = cls()
        config_path = path or (Path(__file__).resolve().parent.parent / "ai_config.json")
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(config, k):
                        setattr(config, k, v)
            except Exception:
                pass
        return config


def get_nvidia_api_key() -> str:
    """Retrieve NVIDIA API key without logging or exposing it."""
    # 1. Environment variable
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if key:
        return key

    # 2. Check local user gemini/mcp config path
    fallback_path = Path.home() / ".gemini" / "mcp" / "nvidia_nim" / "config.json"
    if fallback_path.exists():
        try:
            data = json.loads(fallback_path.read_text(encoding="utf-8"))
            k = data.get("api_key", "").strip()
            if k:
                return k
        except Exception:
            pass

    return ""
