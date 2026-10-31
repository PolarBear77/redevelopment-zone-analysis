import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Optional, Tuple

from redev import metrics

SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
DATA_GO_KR_BASE = "https://apis.data.go.kr"

# 서울 열린데이터광장 서비스명
SEOUL_REDEV_STATUS = "TbSeoulRedevStatus"  # 정비사업 단계·세대수 (OA-22856)
SEOUL_PLAN_STATUS = "vnBsnsNmtn"  # 정비계획 용적률·공급세대 (OA-23112)
SEOUL_ZONE_NOTICE = "upisRebuild"  # 정비구역 고시 이력 (OA-20281)

# 공공데이터포털 엔드포인트
BUILDING_TITLE = "/1613000/BldRgstHubService/getBrTitleInfo"  # 건축물대장 표제부
VILLA_TRADE = "/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"  # 연립다세대 매매 실거래
APT_TRADE = "/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"  # 아파트 매매 실거래


class SourceError(Exception):
    pass


class KeyRequiredError(SourceError):
    pass


class InvalidKeyError(SourceError):
    pass


SEOUL_INVALID_KEY = "INFO-100"


def _get(url: str, timeout: int = 20) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_seoul(payload: dict, service: str) -> Tuple[List[dict], int]:
    body = payload.get(service)
    if body is None:
        result = payload.get("RESULT", {})
        raise SourceError(f"{result.get('CODE')}: {result.get('MESSAGE')}")
    return body["row"], body["list_total_count"]


def parse_seoul_body(text: str, service: str) -> Tuple[List[dict], int]:
    """서울 API는 /json/ 경로로 요청해도 인증키·요청범위 오류를 XML로 돌려준다."""
    if text.lstrip().startswith("<"):
        root = ET.fromstring(text)
        code, message = root.findtext("CODE"), (root.findtext("MESSAGE") or "").strip()
        error = InvalidKeyError if code == SEOUL_INVALID_KEY else SourceError
        raise error(f"{code}: {message}")
    return parse_seoul(json.loads(text), service)


def fetch_seoul(service: str, start: int = 1, end: int = 5, key: Optional[str] = None) -> Tuple[List[dict], int]:
    """키가 없으면 샘플 키를 쓴다. 샘플 키는 한 번에 5건까지만 준다."""
    key = key or os.environ.get("SEOUL_API_KEY") or "sample"
    return parse_seoul_body(_get(f"{SEOUL_BASE}/{key}/json/{service}/{start}/{end}/"), service)


def parse_data_go_kr(text: str) -> Tuple[List[dict], int]:
    root = ET.fromstring(text)
    err = root.find(".//cmmMsgHeader/errMsg")
    if err is not None:
        raise (InvalidKeyError if "SERVICE_KEY" in (err.text or "") else SourceError)(err.text)
    code = root.findtext(".//header/resultCode")
    if code not in ("00", "000"):
        raise SourceError(f"{code}: {root.findtext('.//header/resultMsg')}")
    items = [{child.tag: (child.text or "").strip() for child in item} for item in root.iter("item")]
    return items, int(root.findtext(".//totalCount") or 0)


def fetch_data_go_kr(path: str, params: dict, key: Optional[str] = None) -> Tuple[List[dict], int]:
    key = key or os.environ.get("DATA_GO_KR_KEY")
    if not key:
        raise KeyRequiredError("DATA_GO_KR_KEY 환경변수가 없습니다")
    # 포털의 Encoding 키를 넣어도 두 번 인코딩되지 않도록 먼저 풀어 둔다
    query = urllib.parse.urlencode({**params, "serviceKey": urllib.parse.unquote(key)})
    return parse_data_go_kr(_get(f"{DATA_GO_KR_BASE}{path}?{query}"))


def _int(value: str) -> int:
    return int(float(value)) if value else 0


def zone_summary(row: dict) -> dict:
    """정비사업 현황 한 행을 평가 지표로 바꾼다. 기존 세대수는 토지등소유자 수의 근사치다."""
    existing = _int(row["EXISTING_HOUSEHOLDS"])
    new = _int(row["TOT_BUILT_HOUSEHOLDS"])
    sale = _int(row["SALE_BUILT_HOUSEHOLDS"])
    return {
        "zone": row["ZONE_NM"].strip(),
        "district": row["DISTRICT"],
        "type": row["BIZ_TYPE"],
        "stage": row["BIZ_STAGE"],
        "existing_households": existing,
        "new_households": new,
        "new_per_existing": metrics.ratio(new, existing) if new else None,
        "sale_share": metrics.ratio(sale, new),
        "stage_durations": metrics.stage_durations(row),
    }


def building_records(items: List[dict]) -> List[dict]:
    records = []
    for item in items:
        raw = item.get("useAprDay", "")
        approval = date(int(raw[:4]), int(raw[4:6]) or 1, int(raw[6:8]) or 1) if len(raw) == 8 else None
        records.append({"approval_date": approval, "floor_area": float(item.get("totArea") or 0)})
    return records
