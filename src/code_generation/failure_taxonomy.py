from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


GEN_NO_DATASET_STRUCTURE = "GEN_NO_DATASET_STRUCTURE"
GEN_INVALID_DATASET_STRUCTURE = "GEN_INVALID_DATASET_STRUCTURE"
GEN_NO_FILES = "GEN_NO_FILES"
GEN_NO_SUPPORTED_FORMAT = "GEN_NO_SUPPORTED_FORMAT"
GEN_NO_DOWNLOADABLE_ARTIFACT = "GEN_NO_DOWNLOADABLE_ARTIFACT"
GEN_AMBIGUOUS_FILE_MAPPING = "GEN_AMBIGUOUS_FILE_MAPPING"
GEN_SCHEMA_TOO_WEAK = "GEN_SCHEMA_TOO_WEAK"
GEN_ACCESS_RESTRICTED = "GEN_ACCESS_RESTRICTED"


@dataclass
class GenerationFailure:
    """
    Generation-time failure record.

    These failures mean the system could not confidently generate a
    validation scaffold. They are distinct from execution-time errors.
    """

    category: str
    detail: str
    recoverable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
