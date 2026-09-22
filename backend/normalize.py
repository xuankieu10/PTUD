"""
Mirror module cho normalize.py trong thư mục backend/
Cho phép import cả dạng `import normalize` lẫn `from backend.normalize import normalize_transcript`.
"""

from normalize import (
    normalize_transcript,
    normalize_to_json,
    normalize_course_item,
    calculate_summary,
)

__all__ = [
    "normalize_transcript",
    "normalize_to_json",
    "normalize_course_item",
    "calculate_summary",
]
