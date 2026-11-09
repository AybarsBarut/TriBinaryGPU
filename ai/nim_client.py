"""NVIDIA NIM client with retries, caching, and rate-limiting (docs/methodology.md section 10)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .config import NIMConfig, get_nvidia_api_key

logger = logging.getLogger("radixlab.ai")


class NIMClient:
    """Client for NVIDIA AI Foundation NIM endpoints."""

    def __init__(self, config: Optional[NIMConfig] = None):
        self.config = config or NIMConfig.load()
        self.api_key = get_nvidia_api_key()
        self.cache_dir = self.config.cache_dir or (Path(__file__).resolve().parent.parent / ".cache" / "nim")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_time = 0.0
        self._min_request_interval = 0.5  # Rate limit: 2 req/sec

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.config.enabled)

    def _cache_key(self, model: str, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        payload = {"model": model, "messages": messages, "kwargs": kwargs}
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        use_cache: bool = True,
    ) -> str:
        """Call NVIDIA NIM chat completions API."""
        if not self.is_available:
            raise RuntimeError("NVIDIA NIM is not configured or NVIDIA_API_KEY is missing.")

        target_model = model or self.config.default_model
        c_key = self._cache_key(target_model, messages, temp=temperature, max_tokens=max_tokens)
        c_file = self.cache_dir / f"{c_key}.json"

        if use_cache and c_file.exists():
            try:
                cached = json.loads(c_file.read_text(encoding="utf-8"))
                return cached["content"]
            except Exception:
                pass

        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_err = None
        for attempt in range(self.config.max_retries):
            # Rate limiting
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)

            try:
                self._last_request_time = time.time()
                with httpx.Client(timeout=self.config.timeout_sec) as client:
                    resp = client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    if use_cache:
                        c_file.write_text(json.dumps({"content": content, "raw": data}, indent=2), encoding="utf-8")
                    return content

                if resp.status_code in (429, 500, 502, 503, 504):
                    backoff = self.config.retry_delay_sec * (2 ** attempt)
                    time.sleep(backoff)
                    last_err = f"HTTP {resp.status_code}: {resp.text}"
                    continue

                resp.raise_for_status()

            except Exception as e:
                last_err = str(e)
                time.sleep(self.config.retry_delay_sec * (2 ** attempt))

        raise RuntimeError(f"NVIDIA NIM query failed after {self.config.max_retries} retries: {last_err}")
