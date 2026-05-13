from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests

from src.utils.config import LLM_CONFIG


class LLMClient:
    """
    OpenAI-compatible vLLM client.

    Expected endpoint:
        <api_base_url>/chat/completions

    Example:
        http://host:port/v1/chat/completions
    """

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

        print("[LLMClient] initialized")
        print(f"[LLMClient] model: {self.model_name}")
        print(f"[LLMClient] endpoint: {self.api_base_url}")

    def generate(self, system_prompt: str, user_prompt: str) -> Any:
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
                    content = data["choices"][0]["message"]["content"]
                    return _LLMResponse(content)

                last_error = f"HTTP {resp.status_code}: {resp.text}"

            except Exception as exc:  # noqa: BLE001
                last_error = f"{exc.__class__.__name__}: {exc}"

            print(f"[LLMClient] attempt {attempt}/{self.max_retries} failed: {last_error}")

        return _LLMResponse(
            json.dumps(
                {
                    "error": "llm_call_failed",
                    "message": last_error,
                },
                ensure_ascii=False,
            )
        )

    def parse_json_response(self, response: Any) -> Dict[str, Any]:
        content = getattr(response, "content", "")
        content = content.strip()

        if not content:
            return {
                "error": "empty_response",
                "raw": content,
            }

        content = self._strip_markdown_fence(content)

        try:
            return json.loads(content)
        except Exception:
            pass

        candidate = self._extract_first_json_object(content)

        if candidate is None:
            return {
                "error": "json_parse_failed",
                "message": "No JSON object found in response",
                "raw": content,
            }

        try:
            return json.loads(candidate)
        except Exception as exc:  # noqa: BLE001
            return {
                "error": "json_parse_failed",
                "message": str(exc),
                "raw": candidate,
            }

    def _strip_markdown_fence(self, text: str) -> str:
        text = text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)

        return text.strip()

    def _extract_first_json_object(self, text: str) -> Optional[str]:
        """
        Extract the first balanced JSON object from a string.

        This is safer than regex r'{.*}', because it respects string quotes
        and nested braces.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for idx in range(start, len(text)):
            ch = text[idx]

            if escape:
                escape = False
                continue

            if ch == "\\":
                escape = True
                continue

            if ch == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1

                if depth == 0:
                    return text[start : idx + 1]

        return None


class _LLMResponse:
    def __init__(self, content: str):
        self.content = content


_llm_client_singleton: Optional[LLMClient] = None


def get_llm_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    global _llm_client_singleton

    if _llm_client_singleton is None:
        _llm_client_singleton = LLMClient(config)

    return _llm_client_singleton
