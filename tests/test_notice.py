import unittest
from pathlib import Path

from redev import metrics, notice

FIXTURE = Path(__file__).parent / "fixtures" / "notice_2026_204_excerpt.txt"


class NoticeParseTest(unittest.TestCase):
    def test_extracts_estimate_from_seoul_notice_2026_204(self):
        est = notice.parse_estimate(FIXTURE.read_text())
        self.assertEqual(est["total_revenue"], 536_917_900)
        self.assertEqual(est["total_cost"], 410_148_106)
        self.assertEqual(est["pre_asset_total"], 117_989_448)
        self.assertAlmostEqual(est["stated_rate"], 1.0744)

    def test_stated_rate_matches_recomputed_rate(self):
        est = notice.parse_estimate(FIXTURE.read_text())
        rate = metrics.proportional_rate(est["total_revenue"], est["total_cost"], est["pre_asset_total"])
        self.assertAlmostEqual(rate, est["stated_rate"], places=4)

    def test_text_without_estimate_returns_none_fields(self):
        est = notice.parse_estimate("정비계획 결정 고시\n용적률 250%")
        self.assertEqual(set(est.values()), {None})


if __name__ == "__main__":
    unittest.main()
