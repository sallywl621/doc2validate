from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests


class BaseValidator(ABC):
    validator_name = "base"

    def __init__(self, github_token: str | None = None):
        self.github_token = github_token

    @abstractmethod
    def extract_urls(self, article_result: Dict[str, Any]) -> List[str]: ...

    def check_url_format(self, url: str) -> Dict[str, Any]:
        if not url or not isinstance(url, str):
            return {"is_valid": False, "reason": "empty_or_non_string"}
        url = url.strip()
        if len(url) < 6:
            return {"is_valid": False, "reason": "too_short"}
        if " " in url:
            return {"is_valid": False, "reason": "contains_whitespace"}
        candidate = url if url.startswith("http") else "https://" + url
        try:
            parsed = urlparse(candidate)
        except Exception:
            return {"is_valid": False, "reason": "urlparse_failed"}
        if not parsed.netloc:
            return {"is_valid": False, "reason": "missing_netloc"}
        if "." not in parsed.netloc:
            return {"is_valid": False, "reason": "invalid_domain"}
        return {"is_valid": True, "reason": "ok"}

    def normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith("http"):
            url = "https://" + url
        return url.rstrip("/")

    def resolve_redirect(self, url: str, timeout: int = 10) -> str:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code < 400:
                return resp.url
        except Exception:
            pass
        return url

    def check_accessible(self, url: str, timeout: int = 10) -> bool:
        try:
            r = requests.get(url, allow_redirects=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            r.close()
            return r.status_code < 400
        except Exception:
            return False

    def infer_repo_type(self, url: str) -> str:
        lower = url.lower()
        if "github.com" in lower:
            return "github"
        if "gitlab.com" in lower:
            return "gitlab"
        if "bitbucket.org" in lower:
            return "bitbucket"
        if "zenodo.org" in lower:
            return "zenodo"
        if "figshare" in lower:
            return "figshare"
        if "osf.io" in lower:
            return "osf"
        if "doi.org" in lower:
            return "doi"
        return "web"

    def estimate_repo_size(self, url: str) -> Dict[str, Any]:
        return {"estimated_size_bytes": None, "estimation_method": "not_estimated"}

    def validate_url(self, url: str) -> Dict[str, Any]:
        raw_url = url.strip() if isinstance(url, str) else url
        format_check = self.check_url_format(raw_url)
        if not format_check["is_valid"]:
            return {"raw_url": raw_url, "redirected_url": None, "accessible": False, "repo_type": "invalid", "estimated_size_bytes": None, "estimation_method": None, "url_validity": format_check}
        normalized = self.normalize_url(raw_url)
        redirected = self.resolve_redirect(normalized)
        accessible = self.check_accessible(redirected)
        size = self.estimate_repo_size(redirected)
        return {"raw_url": raw_url, "redirected_url": redirected, "accessible": accessible, "repo_type": self.infer_repo_type(redirected), "estimated_size_bytes": size.get("estimated_size_bytes"), "estimation_method": size.get("estimation_method"), "url_validity": format_check}

    def run(self, article_id: str, article_result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            urls = self.extract_urls(article_result)
            validations = [self.validate_url(url) for url in urls]
            return {"validator": self.validator_name, "article_id": article_id, "status": "success", "validated_count": len(validations), "results": validations}
        except Exception as exc:  # noqa: BLE001
            return {"validator": self.validator_name, "article_id": article_id, "status": "error", "error": {"type": exc.__class__.__name__, "message": str(exc), "traceback": traceback.format_exc()}}
