#!/usr/bin/env python3
"""Statische Prüfung: Deploy-Pfade dürfen Keys/State nicht übertragen."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "deploy" / "contabo.sh",
    ROOT / "deploy" / "server-auto-deploy.sh",
    ROOT / ".github" / "workflows" / "ci.yml",
]
REQUIRED = [
    "attest/keys/",
    "attest/payapi/keys/",
    "attest/payapi/state/",
    "providers/state/",
    "resolver/state/",
    "affiliate/state/",
    "logs/",
]


class DeployExcludeTests(unittest.TestCase):
    def test_all_deploy_paths_exclude_keys_and_state(self):
        for path in FILES:
            text = path.read_text(encoding="utf-8")
            for pattern in REQUIRED:
                self.assertRegex(
                    text, re.escape(pattern),
                    f"{path.name} schließt {pattern} nicht aus",
                )
            self.assertIn("/ready", text, f"{path.name} prüft nicht /ready")


if __name__ == "__main__":
    unittest.main(verbosity=2)
