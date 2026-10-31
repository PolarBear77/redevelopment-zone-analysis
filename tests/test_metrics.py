import unittest
from datetime import date

from redev import metrics


class ProfitabilityTest(unittest.TestCase):
    def test_proportional_rate(self):
        # 종후 1,000억, 사업비 600억, 종전 380억 -> (1000-600)/380
        self.assertAlmostEqual(metrics.proportional_rate(1000, 600, 380), 1.0526, places=4)

    def test_rights_value_and_contribution(self):
        rights = metrics.rights_value(appraisal=3.0, rate=1.05)
        self.assertAlmostEqual(rights, 3.15)
        self.assertAlmostEqual(metrics.contribution(member_price=9.0, rights=rights), 5.85)

    def test_safety_margin(self):
        # README 계산 예시: 매매가 7억 + 분담금 5.85억, 신축 시세 15억
        total = metrics.total_investment(purchase_price=7.0, contribution=5.85)
        self.assertAlmostEqual(total, 12.85)
        self.assertAlmostEqual(metrics.safety_margin(new_build_price=15.0, total=total), 2.15)

    def test_new_units_per_existing(self):
        self.assertAlmostEqual(metrics.ratio(1919, 1208), 1.5886, places=4)

    def test_ratio_with_zero_denominator_is_none(self):
        self.assertIsNone(metrics.ratio(0, 0))


class DesignationTest(unittest.TestCase):
    def test_aging_rate_by_count_and_floor_area(self):
        buildings = [
            {"approval_date": date(1985, 3, 1), "floor_area": 100.0},
            {"approval_date": date(1994, 6, 1), "floor_area": 300.0},
            {"approval_date": date(2010, 1, 1), "floor_area": 100.0},
            {"approval_date": None, "floor_area": 50.0},
        ]
        # 2026-11-01 기준 30년 이상: 1985, 1994 건물. 사용승인일 없는 건물은 제외
        result = metrics.aging_rate(buildings, as_of=date(2026, 11, 1), years=30)
        self.assertAlmostEqual(result["by_count"], 2 / 3)
        self.assertAlmostEqual(result["by_floor_area"], 400 / 500)
        self.assertEqual(result["unknown"], 1)

    def test_aging_boundary_is_inclusive(self):
        buildings = [{"approval_date": date(1996, 11, 1), "floor_area": 10.0}]
        result = metrics.aging_rate(buildings, as_of=date(2026, 11, 1), years=30)
        self.assertEqual(result["by_count"], 1.0)

    def test_undersized_parcel_rate(self):
        self.assertAlmostEqual(metrics.undersized_parcel_rate([45.0, 89.9, 90.0, 200.0]), 0.5)

    def test_building_density_per_hectare(self):
        # 120동, 2만㎡(2ha) -> 60동/ha
        self.assertAlmostEqual(metrics.building_density(120, 20000), 60.0)


class StageTest(unittest.TestCase):
    def test_stage_durations_skip_missing_dates(self):
        row = {
            "ZONE_DESIGNATION_INIT_YMD": "2020-01-01",
            "PROMOTION_COMMITTEE_YMD": "",
            "ASSOCIATION_ESTABLISHMENT_YMD": "2022-01-01",
            "BIZ_IMPLEMENTATION_INIT_YMD": "2023-07-02",
        }
        durations = metrics.stage_durations(row)
        self.assertEqual(durations, [("구역지정", "조합설립", 731), ("조합설립", "사업시행인가", 547)])


if __name__ == "__main__":
    unittest.main()
