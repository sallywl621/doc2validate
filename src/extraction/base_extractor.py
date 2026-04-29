from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseExtractor(ABC):
    extractor_name: str = "base"

    def __init__(self, extractor_name: str):
        self.extractor_name = extractor_name

    @abstractmethod
    def get_context_strategy(self) -> str: ...

    @abstractmethod
    def get_section_priority(self) -> List[str]: ...

    @abstractmethod
    def get_keywords(self) -> List[str]: ...

    @abstractmethod
    def get_output_schema(self) -> Dict[str, Any]: ...

    @abstractmethod
    def extract(self, article_id: str, article_result: Dict[str, Any] | None = None) -> Dict[str, Any]: ...

    def prepare_result(self, parsed_result: Dict[str, Any], article_id: str) -> Dict[str, Any]:
        return {"article_id": article_id, "extractor": self.extractor_name, "status": "success", "result": parsed_result}

    def handle_error(self, error: Exception, article_id: str) -> Dict[str, Any]:
        return {
            "article_id": article_id,
            "extractor": self.extractor_name,
            "status": "error",
            "result": None,
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            },
        }
