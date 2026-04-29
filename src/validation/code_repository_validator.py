from __future__ import annotations
from src.validation.base_validator import BaseValidator

class CodeRepositoryValidator(BaseValidator):
    validator_name = "code_repository_validator"
    def extract_urls(self, article_result):
        if article_result.get("status") != "success":
            return []
        return article_result.get("result", {}).get("primary_code_repository", {}).get("code_repository_urls", []) or []
