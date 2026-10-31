import importlib.util
import unittest
import urllib.error
from pathlib import Path

from redev import sources

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_feasibility.py"
spec = importlib.util.spec_from_file_location("verify_feasibility", SCRIPT)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)  # 모듈을 불러와도 점검은 실행되지 않아야 한다


class ClassifyTest(unittest.TestCase):
    def test_status_for_each_error(self):
        cases = [
            (sources.KeyRequiredError("DATA_GO_KR_KEY 환경변수가 없습니다"), "KEY_REQUIRED"),
            (sources.InvalidKeyError("INFO-100: 인증키가 유효하지 않습니다"), "KEY_INVALID"),
            (sources.SourceError("ERROR-335: 샘플데이터는 5건까지"), "FAIL"),
            (urllib.error.HTTPError("u", 403, "Forbidden", None, None), "KEY_INVALID"),
            (urllib.error.HTTPError("u", 500, "Server Error", None, None), "FAIL"),
            (ValueError("boom"), "FAIL"),
        ]
        for error, expected in cases:
            with self.subTest(error=error):
                self.assertEqual(verify.classify(error)[0], expected)

    def test_import_does_not_run_checks(self):
        self.assertEqual(verify.results, [])


class RateCheckTest(unittest.TestCase):
    def test_matching_rates_pass(self):
        self.assertEqual(verify.rate_status(1.07442, 1.0744)[0], "OK")

    def test_mismatched_rates_fail(self):
        self.assertEqual(verify.rate_status(0.93, 1.0744)[0], "FAIL")

    def test_missing_stated_rate_fails(self):
        self.assertEqual(verify.rate_status(1.07, None)[0], "FAIL")


if __name__ == "__main__":
    unittest.main()
