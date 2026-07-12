from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.generation.credentials import load_credentials


def write_config(path: Path, api_key: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[mimo]\n"
        f"api_key={api_key}\n"
        "base_url=https://api.xiaomimimo.com/v1\n"
        "model=mimo-v2.5-pro\n\n"
        "[limits]\n"
        "max_requests=70\n"
        "max_cost_usd=2.0\n",
        encoding="utf-8",
    )


class CredentialLoaderTests(unittest.TestCase):
    def test_machine_local_secrets_root_is_used_without_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            machine_config = Path(directory) / "machine.local.ini"
            secrets_root = Path(directory) / "portable-secrets"
            machine_config.write_text(
                "[paths]\n"
                f"secrets_root={secrets_root}\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"MACHINE_CONFIG_PATH": str(machine_config), "MIMO_SECRET_FILE": "", "MIMO_API_KEY": ""},
                clear=False,
            ):
                config = load_credentials(create_template=False)

            self.assertEqual(config.config_path, secrets_root / "retrieval-adaptation-lab" / "mimo.ini")
            self.assertEqual(config.status, "missing_credentials")

    def test_missing_config_creates_secret_free_template(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "secrets" / "mimo.ini"
            with patch.dict(os.environ, {"MIMO_SECRET_FILE": str(config_path)}, clear=False), patch.dict(os.environ, {"MIMO_API_KEY": ""}, clear=False):
                config = load_credentials()

            self.assertTrue(config.config_created)
            self.assertEqual(config.status, "missing_credentials")
            content = config_path.read_text(encoding="utf-8")
            self.assertIn("api_key=\n", content)
            self.assertNotIn("tp-", content)

    def test_environment_key_has_priority_without_public_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "mimo.ini"
            write_config(config_path)
            with patch.dict(os.environ, {"MIMO_SECRET_FILE": str(config_path), "MIMO_API_KEY": "environment-placeholder"}, clear=False):
                config = load_credentials()

            self.assertEqual(config.status, "ready")
            self.assertEqual(config.credential_source, "environment")
            public = json.dumps(config.to_public())
            self.assertNotIn("api_key", public)
            self.assertNotIn("environment-placeholder", public)

    def test_file_key_is_used_when_environment_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "mimo.ini"
            write_config(config_path, "file-placeholder")
            with patch.dict(os.environ, {"MIMO_SECRET_FILE": str(config_path), "MIMO_API_KEY": ""}, clear=False):
                config = load_credentials()

            self.assertEqual(config.status, "ready")
            self.assertEqual(config.credential_source, "file")

    def test_token_plan_endpoint_policy_is_blocked_without_leaking_key(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "mimo.ini"
            fake_key = "tp-" + ("x" * 20)
            write_config(config_path, fake_key)
            with patch.dict(os.environ, {"MIMO_SECRET_FILE": str(config_path), "MIMO_API_KEY": ""}, clear=False):
                config = load_credentials()

            self.assertEqual(config.status, "policy_blocked")
            self.assertIn("token_plan_base_url_mismatch", config.issues)
            self.assertNotIn(fake_key, json.dumps(config.to_public()))


if __name__ == "__main__":
    unittest.main()
