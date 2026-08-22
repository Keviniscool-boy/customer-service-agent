import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import Settings


class SettingsTest(unittest.TestCase):
    def test_env_example_can_be_loaded_directly(self):
        env_example = Path(__file__).resolve().parents[1] / ".env.example"

        with patch.dict(os.environ, {}, clear=True):
            loaded = Settings(_env_file=env_example)

        self.assertEqual(loaded.database_backend, "postgres")
        self.assertEqual(loaded.knowledge_provider, "weknora")


if __name__ == "__main__":
    unittest.main()
