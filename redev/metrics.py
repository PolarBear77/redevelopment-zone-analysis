from datetime import date
from typing import Iterable, List, Optional, Tuple

UNDERSIZED_PARCEL_M2 = 90.0

# 서울시 정비사업 현황 API(TbSeoulRedevStatus)의 단계별 날짜 필드, 진행 순서대로
STAGE_FIELDS = [
    ("구역지정", "ZONE_DESIGNATION_INIT_YMD"),
    ("추진위", "PROMOTION_COMMITTEE_YMD"),
    ("조합설립", "ASSOCIATION_ESTABLISHMENT_YMD"),
    ("건축심의", "ARCHITECTURAL_REVIEW_YMD"),
    ("사업시행인가", "BIZ_IMPLEMENTATION_INIT_YMD"),
    ("관리처분인가", "MGMT_DISPOSITION_INIT_YMD"),
    ("이주", "MIGRATION_START_YMD"),
    ("착공", "CONSTRUCTION_START_YMD"),
]


def ratio(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    return numerator / denominator


def proportional_rate(post_asset_total: float, project_cost: float, pre_asset_total: float) -> float:
    """비례율 = (종후자산 총액 - 총사업비) / 종전자산 총액"""
    return (post_asset_total - project_cost) / pre_asset_total


def rights_value(appraisal: float, rate: float) -> float:
    return appraisal * rate


def contribution(member_price: float, rights: float) -> float:
    return member_price - rights


def total_investment(purchase_price: float, contribution: float, extra_costs: float = 0.0) -> float:
    return purchase_price + contribution + extra_costs


def safety_margin(new_build_price: float, total: float) -> float:
    return new_build_price - total


def aging_rate(buildings: Iterable[dict], as_of: date, years: int = 30) -> dict:
    """사용승인일 기준 노후도. 사용승인일이 없는 건물은 분모에서 빼고 개수만 센다."""
    known = [b for b in buildings if b.get("approval_date")]
    unknown = sum(1 for b in buildings if not b.get("approval_date"))
    try:
        cutoff = as_of.replace(year=as_of.year - years)
    except ValueError:  # 2월 29일
        cutoff = as_of.replace(year=as_of.year - years, day=28)
    old = [b for b in known if b["approval_date"] <= cutoff]
    return {
        "by_count": ratio(len(old), len(known)),
        "by_floor_area": ratio(sum(b["floor_area"] for b in old), sum(b["floor_area"] for b in known)),
        "unknown": unknown,
    }


def undersized_parcel_rate(parcel_areas_m2: List[float]) -> Optional[float]:
    return ratio(sum(1 for a in parcel_areas_m2 if a < UNDERSIZED_PARCEL_M2), len(parcel_areas_m2))


def building_density(building_count: int, zone_area_m2: float) -> Optional[float]:
    """호수밀도(동/ha)"""
    return ratio(building_count, zone_area_m2 / 10000)


def stage_durations(row: dict) -> List[Tuple[str, str, int]]:
    """날짜가 있는 단계를 날짜순으로 이어서 (이전 단계, 다음 단계, 경과일)을 돌려준다.

    실제 데이터에 추진위 날짜가 구역지정보다 앞선 구역이 있어서(예: 효창공원앞역세권) 단계 순서가 아니라 날짜순으로 잇는다.
    """
    dated = [(name, date.fromisoformat(row[field][:10])) for name, field in STAGE_FIELDS if row.get(field)]
    dated.sort(key=lambda stage: stage[1])
    return [(a, b, (db - da).days) for (a, da), (b, db) in zip(dated, dated[1:])]
