from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.machine_config import load_machine_config


class MachineConfigTests(unittest.TestCase):
    def test_environment_root_override_without_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_config = Path(directory) / "machine.local.ini"
            with patch.dict(
                os.environ,
                {"MACHINE_CONFIG_PATH": str(missing_config), "AI_LAB_ROOT": str(Path(directory) / "assets")},
                clear=False,
            ):
                config = load_machine_config()
        self.assertEqual(config.ai_lab_root, Path(directory) / "assets")
        self.assertEqual(config.cache_root, Path(directory) / "assets" / "cache")
        self.assertFalse(config.config_exists)

    def test_local_ini_values_are_loaded_without_reading_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "machine.local.ini"
            config_path.write_text(
                "[machine]\n"
                "ai_lab_root=E:\\PortableAI\n"
                "[paths]\n"
                "cache_root=E:\\PortableAI\\cache\n"
                "[assets]\n"
                "docling_artifacts=E:\\PortableAI\\models\\docling\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"MACHINE_CONFIG_PATH": str(config_path)}, clear=False):
                config = load_machine_config()
        self.assertEqual(config.ai_lab_root, Path("E:/PortableAI"))
        self.assertEqual(config.cache_root, Path("E:/PortableAI/cache"))
        self.assertEqual(config.docling_artifacts, Path("E:/PortableAI/models/docling"))


if __name__ == "__main__":
    unittest.main()
