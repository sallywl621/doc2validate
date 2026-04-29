from __future__ import annotations
from src.validation.base_validator import BaseValidator

class DatasetURLValidator(BaseValidator):
    validator_name = "dataset_url_validator"
    def extract_urls(self, article_result):
        if article_result.get("status") != "success":
            return []
        return article_result.get("result", {}).get("primary_dataset", {}).get("access_urls", []) or []
