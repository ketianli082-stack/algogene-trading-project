import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".csv", ".txt"}


class RepositorySafetyTest(unittest.TestCase):
    def test_no_obvious_private_key_or_hard_coded_algogene_secret(self):
        findings = []
        assignment = re.compile(
            r"(?i)(?:api[_-]?key|secret)\s*=\s*['\"]([^'\"]{12,})['\"]"
        )
        allowed_values = {"YOUR_API_KEY", "ALGOGENE_API_KEY"}

        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or path.suffix not in TEXT_SUFFIXES
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
            if private_key_marker in text:
                findings.append("%s: private key marker" % path.relative_to(ROOT))
            for match in assignment.finditer(text):
                if match.group(1) not in allowed_values:
                    findings.append(
                        "%s: possible hard-coded secret" % path.relative_to(ROOT)
                    )

        self.assertEqual(findings, [], "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
