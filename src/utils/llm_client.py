from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests

from .config import LLM_CONFIG


class LLMClient:
    """OpenAI-compatible client for vLLM serving."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or LLM_CONFIG
        self.model_name = cfg["model_name"]
        self.api_base_url = cfg["api_base_url"].rstrip("/")
        self.api_key = cfg.get("api_key", "EMPTY")
        self.temperature = cfg.get("temperature", 0.3)
        self.max_tokens = cfg.get("max_tokens", 4000)
        self.timeout = cfg.get("timeout", 60)
        self.max_retries = cfg.get("max_retries", 3)
        self.session = requests.Session()

    def generate(self, system_prompt: str, user_prompt: str) -> "LLMResponse":
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    f"{self.api_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return LLMResponse(data["choices"][0]["message"]["content"])
                last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
            except Exception as exc:  # noqa: BLE001
                last_error = repr(exc)
        return LLMResponse(json.dumps({"error": "llm_call_failed", "message": last_error}, ensure_ascii=False))

    def parse_json_response(self, response: Any) -> Dict[str, Any]:
        content = getattr(response, "content", str(response)).strip()
        try:
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if fenced:
                return json.loads(fenced.group(1))
            obj = re.search(r"\{.*\}", content, re.DOTALL)
            if obj:
                return json.loads(obj.group())
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return {"error": "json_parse_failed", "message": str(exc), "raw": content}


class LLMResponse:
    def __init__(self, content: str):
        self.content = content


_llm_client_singleton: Optional[LLMClient] = None


def get_llm_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    global _llm_client_singleton
    if _llm_client_singleton is None:
        _llm_client_singleton = LLMClient(config)
    return _llm_client_singleton
