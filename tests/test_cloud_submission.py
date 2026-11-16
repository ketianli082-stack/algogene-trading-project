import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock


class CloudSubmissionTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("runner", root / "scripts/algogene_cloud_backtest.py")
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    @staticmethod
    def response(payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload)
        return response

    def execute(self, responses):
        with patch.dict(self.runner.os.environ, {"ALGOGENE_USER_ID": "dummy-user",
                                               "ALGOGENE_API_KEY": "dummy-credential"}, clear=True), \
             patch.object(self.runner.urllib.request, "urlopen", side_effect=responses) as request, \
             patch.object(self.runner.time, "sleep"), \
             patch.object(self.runner.time, "monotonic", return_value=1000), \
             patch.object(Path, "write_text"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            code = self.runner.main()
        return code, request, output.getvalue()

    def test_explicit_limit_is_retried_but_submission_rejection_stops(self):
        code, request, output = self.execute([
            self.response({"status": True, "res": []}),
            self.response({"res": {"contractSize": 1}}),
            self.response({"status": False, "res": "Exceed maximum access count!"}),
            self.response({"status": False, "res": "Unsupported dataset"}),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 4)
        self.assertIn("Unsupported dataset", output)
        self.assertNotIn("dummy-credential", output)

    def test_ambiguous_submission_timeout_is_not_retried(self):
        code, request, output = self.execute([
            self.response({"status": True, "res": []}),
            self.response({"res": {"contractSize": 1}}),
            TimeoutError("may have submitted"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(request.call_count, 3)
        self.assertIn("TimeoutError", output)
        self.assertNotIn("dummy-credential", output)
