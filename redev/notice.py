"""서울시 정비계획 결정 고시문에서 추정비례율 산출 근거를 뽑는다.

PDF 텍스트 추출에는 pypdf가 필요하다(`pip install pypdf`). 파싱은 추출된 텍스트만 받는다.
"""
import re
from typing import Optional

_AMOUNT = r"([\d,]+)"

_PATTERNS = {
    "total_revenue": rf"합계\s*{_AMOUNT}",
    "total_cost": rf"총\s*지출\s*{_AMOUNT}",
    "pre_asset_total": rf"종전자산\s*총액\s*{_AMOUNT}",
}


def _amount(pattern: str, text: str) -> Optional[int]:
    match = re.search(pattern, text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_estimate(text: str) -> dict:
    """금액은 고시문 표기 그대로(천원). 비례율은 소수(1.0744 = 107.44%)."""
    result = {key: _amount(pattern, text) for key, pattern in _PATTERNS.items()}
    rate = re.search(r"추정비례율\s*:\s*([\d.]+)\s*%", text)
    result["stated_rate"] = float(rate.group(1)) / 100 if rate else None
    return result


def extract_text(pdf_path: str) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages)
