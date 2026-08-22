import tempfile
import unittest
from pathlib import Path

from load_tests.summarize import build_conclusions


class LoadReportTest(unittest.TestCase):
    def test_conclusions_do_not_treat_zero_failures_as_supported_capacity(self):
        summaries = [
            {
                "prefix": "04-mixed",
                "stage": {"users": 1000},
                "requests": 10000,
                "failures": 0,
                "average": 7000,
                "p95": 8800,
            },
            {
                "prefix": "05-peak",
                "stage": {"users": 3000},
                "requests": 13000,
                "failures": 0,
                "average": 19000,
                "p95": 23000,
            },
        ]
        resources = {
            "02-auth": {
                "backend": {"cpu": 1505.97, "memory_mib": 2329.6}
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            (results_dir / "05-peak.log").write_text(
                "Not all users finished their tasks & terminated in 10.0 seconds.",
                encoding="utf-8",
            )
            conclusions = "\n".join(
                build_conclusions(summaries, resources, results_dir)
            )

        self.assertIn("23000 次请求，Locust 记录到 0 次失败", conclusions)
        self.assertIn("复杂读写场景 P95 为 8.8 秒", conclusions)
        self.assertIn("系统已经过载", conclusions)
        self.assertIn("GiB 内存", conclusions)


if __name__ == "__main__":
    unittest.main()
