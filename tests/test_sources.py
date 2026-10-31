import json
import unittest
from pathlib import Path

from redev import sources

FIXTURES = Path(__file__).parent / "fixtures"


def load_rows(name, service):
    return json.loads((FIXTURES / name).read_text())[service]["row"]


class SeoulParseTest(unittest.TestCase):
    def test_parse_seoul_response_returns_rows_and_total(self):
        payload = json.loads((FIXTURES / "seoul_redev_status.json").read_text())
        rows, total = sources.parse_seoul(payload, "TbSeoulRedevStatus")
        self.assertEqual(len(rows), 5)
        self.assertEqual(total, 496)

    def test_parse_seoul_error_raises(self):
        payload = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
        with self.assertRaises(sources.SourceError):
            sources.parse_seoul(payload, "TbSeoulRedevStatus")

    def test_zone_summary_from_real_row(self):
        row = next(r for r in load_rows("seoul_redev_status.json", "TbSeoulRedevStatus") if r["ZONE_NM"] == "쌍문2구역 ")
        summary = sources.zone_summary(row)
        self.assertEqual(summary["zone"], "쌍문2구역")
        self.assertEqual(summary["existing_households"], 1208)
        self.assertEqual(summary["new_households"], 1919)
        self.assertAlmostEqual(summary["new_per_existing"], 1919 / 1208)
        self.assertAlmostEqual(summary["sale_share"], 1594 / 1919)

    def test_zone_summary_without_housing_plan(self):
        row = next(r for r in load_rows("seoul_redev_status.json", "TbSeoulRedevStatus") if r["ZONE_NM"].startswith("효제"))
        summary = sources.zone_summary(row)
        self.assertIsNone(summary["new_per_existing"])
        self.assertIsNone(summary["sale_share"])


class DataGoKrParseTest(unittest.TestCase):
    def test_missing_key_error_is_reported(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?><OpenAPI_ServiceResponse><cmmMsgHeader>'
            "<errMsg>SERVICE_KEY_IS_NULL</errMsg><returnAuthMsg>서비스 접근거부</returnAuthMsg>"
            "<returnReasonCode>20</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
        )
        with self.assertRaisesRegex(sources.SourceError, "SERVICE_KEY_IS_NULL"):
            sources.parse_data_go_kr(xml)

    def test_items_are_returned_as_dicts(self):
        xml = (
            "<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
            "<body><items><item><useAprDay>19890512</useAprDay><totArea>120.5</totArea></item>"
            "<item><useAprDay></useAprDay><totArea>80</totArea></item></items>"
            "<totalCount>2</totalCount></body></response>"
        )
        items, total = sources.parse_data_go_kr(xml)
        self.assertEqual(total, 2)
        self.assertEqual(items[0], {"useAprDay": "19890512", "totArea": "120.5"})


if __name__ == "__main__":
    unittest.main()
