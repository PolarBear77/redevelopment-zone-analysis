"""README의 분석 순서를 실제 공공데이터로 단계별 점검한다.

    python3 scripts/verify_feasibility.py

환경변수
    SEOUL_API_KEY   서울 열린데이터광장 인증키 (없으면 샘플 키, 5건 제한)
    DATA_GO_KR_KEY  공공데이터포털 인증키 (건축물대장, 실거래가). Encoding, Decoding 어느 쪽이든 된다.
"""
import functools
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redev import metrics, notice, sources  # noqa: E402

# 검증용 표본: 서울시 고시 제2026-204호 (추정비례율 107.44%)
SAMPLE_NOTICE_URL = (
    "https://urban.seoul.go.kr/UpisArchive/DATA/PM/pdf/11000TTC202607280008/"
    "%EA%B3%A0%EC%8B%9C%EB%AC%B8%282026-204%ED%98%B8%29.pdf"
)
# 건축물대장·실거래가 표본: 종로구(11110) 청운동(10100), 2025년 9월
SAMPLE_SIGUNGU, SAMPLE_BJDONG, SAMPLE_MONTH = "11110", "10100", "202509"

# 고시문 비례율은 소수 둘째 자리(%)까지 표기되므로 그 반올림 폭만 허용한다
RATE_TOLERANCE = 0.0001

STEPS = []
results = []


def step(name):
    def register(fn):
        STEPS.append((name, fn))
        return fn

    return register


def classify(error):
    if isinstance(error, sources.KeyRequiredError):
        return "KEY_REQUIRED", str(error)
    if isinstance(error, sources.InvalidKeyError):
        return "KEY_INVALID", str(error)
    if isinstance(error, urllib.error.HTTPError) and error.code in (401, 403):
        return "KEY_INVALID", f"HTTP {error.code}: 인증키가 틀렸거나 해당 API 활용신청이 승인되지 않았습니다"
    if isinstance(error, sources.SourceError):
        return "FAIL", str(error)
    return "FAIL", f"{type(error).__name__}: {error}"


def rate_status(recomputed, stated):
    if stated is None:
        return "FAIL", f"고시문에서 추정비례율을 찾지 못함 (재계산 {recomputed:.2%})"
    if abs(recomputed - stated) > RATE_TOLERANCE:
        return "FAIL", f"고시문 {stated:.2%} ≠ 재계산 {recomputed:.2%}"
    return "OK", f"고시문 {stated:.2%}, 재계산 {recomputed:.2%}"


def run_step(name, fn):
    try:
        status, detail = fn()
    except Exception as e:  # noqa: BLE001
        status, detail = classify(e)
    results.append((name, status, detail))
    print(f"[{status}] {name}\n    {detail}")


@functools.lru_cache(maxsize=None)
def redev_status():
    return sources.fetch_seoul(sources.SEOUL_REDEV_STATUS)


@step("1. 후보 구역 목록 (정비사업 현황 TbSeoulRedevStatus)")
def check_zone_list():
    rows, total = redev_status()
    stages = sorted({r["BIZ_STAGE"] for r in rows})
    return "OK", f"전체 {total}건, 표본 {len(rows)}건, 단계 예: {', '.join(stages)}"


@step("2. 정비계획 수치 (용적률·공급세대 vnBsnsNmtn)")
def check_plan_numbers():
    rows, total = sources.fetch_seoul(sources.SEOUL_PLAN_STATUS)
    r = rows[0]
    return "OK", (
        f"전체 {total}건. 예: {r['BSNS_NAME']} 용적률 {r['FLAR_RT']}%, "
        f"공급 {r['SUPLY_HSHLD']:.0f}세대(분양 {r['PARCEL']:.0f}, 임대 {r['RENTAL']:.0f})"
    )


@step("2b. 정비구역 고시 이력 (upisRebuild)")
def check_zone_notices():
    rows, total = sources.fetch_seoul(sources.SEOUL_ZONE_NOTICE)
    return "OK", f"전체 {total}건, 고시관리코드 예: {rows[0]['DCSN_ANCMNT_MNG_CD']}"


@step("3. 구역 사업성 지표 (기존 세대 대비 신축, 분양 비중, 단계 소요기간)")
def check_zone_metrics():
    rows, _ = redev_status()
    lines = []
    for s in map(sources.zone_summary, rows):
        npe = f"{s['new_per_existing']:.2f}배" if s["new_per_existing"] else "주택 계획 없음"
        share = f"{s['sale_share']:.0%}" if s["sale_share"] is not None else "-"
        durations = ", ".join(f"{a}→{b} {days}일" for a, b, days in s["stage_durations"]) or "단계 하나뿐"
        lines.append(f"{s['zone']}({s['stage']}): 신축/기존 {npe}, 분양 비중 {share}, {durations}")
    return "OK", "\n    ".join(lines)


@step("4. 노후도 (건축물대장 표제부)")
def check_aging():
    items, total = sources.fetch_data_go_kr(
        sources.BUILDING_TITLE,
        {"sigunguCd": SAMPLE_SIGUNGU, "bjdongCd": SAMPLE_BJDONG, "numOfRows": 100, "pageNo": 1},
    )
    aging = metrics.aging_rate(sources.building_records(items), as_of=date.today(), years=30)
    if aging["by_count"] is None:
        return "FAIL", f"표본 {len(items)}/{total}동 중 사용승인일이 있는 건물이 없음"
    return "OK", f"표본 {len(items)}/{total}동, 30년 이상 동수 비율 {aging['by_count']:.0%}"


@step("5. 실거래가 (연립다세대·아파트 매매)")
def check_trades():
    _, vt = sources.fetch_data_go_kr(sources.VILLA_TRADE, {"LAWD_CD": SAMPLE_SIGUNGU, "DEAL_YMD": SAMPLE_MONTH})
    _, at = sources.fetch_data_go_kr(sources.APT_TRADE, {"LAWD_CD": SAMPLE_SIGUNGU, "DEAL_YMD": SAMPLE_MONTH})
    return "OK", f"연립다세대 {vt}건, 아파트 {at}건"


@step("6. 추정비례율 (정비계획 결정 고시문 PDF)")
def check_proportional_rate():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return "NEEDS_PYPDF", "pip install pypdf 후 다시 실행"
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(urllib.request.urlopen(SAMPLE_NOTICE_URL, timeout=30).read())
        f.flush()
        est = notice.parse_estimate(notice.extract_text(f.name))
    rate = metrics.proportional_rate(est["total_revenue"], est["total_cost"], est["pre_asset_total"])
    return rate_status(rate, est["stated_rate"])


def main():
    for name, fn in STEPS:
        run_step(name, fn)
    print("\n요약")
    for name, status, _ in results:
        print(f"  {status:<13} {name}")
    unverified = sum(1 for _, s, _ in results if s not in ("OK", "FAIL"))
    if unverified:
        print(f"\n  ※ {unverified}개 단계는 키나 pypdf가 없어 실제 데이터로 확인하지 못했습니다")
    return 1 if any(s == "FAIL" for _, s, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
