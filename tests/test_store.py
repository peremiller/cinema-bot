"""Data-preservation regressions for Cinema Finder's per-chat preferences."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import store


class StorePreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "locations.json"
        patcher_dir = patch.object(config, "DATA_DIR", self.temp.name)
        patcher_path = patch.object(config, "STORE_PATH", str(self.path))
        patcher_dir.start()
        patcher_path.start()
        self.addCleanup(patcher_dir.stop)
        self.addCleanup(patcher_path.stop)

    def test_initial_save_subscription_and_location_update_preserve_daily(self):
        self.assertIsNone(store.get_location(123))
        self.assertFalse(store.subscribe(123, "09:00"))
        store.set_location(123, {"city": "Manila", "lat": 14.6, "lon": 121.0})
        self.assertTrue(store.subscribe(123, "09:00"))
        store.set_location(123, {"city": "Cebu", "lat": 10.3, "lon": 123.9})
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["123"]["daily"], "09:00")
        self.assertEqual(saved["123"]["city"], "Cebu")
        store.unsubscribe(123)
        self.assertNotIn("daily", store.get_location(123))

    def test_corrupt_json_cannot_be_overwritten(self):
        original = b'{ "123": { "city": "unfinished"'
        self.path.write_bytes(original)
        self.assertIsNone(store.get_location(123))  # Existing read fallback remains unchanged.
        with self.assertRaises(store.StoreCorruptedError):
            store.set_location(123, {"city": "Cebu"})
        self.assertEqual(self.path.read_bytes(), original)

    def test_json_array_cannot_be_overwritten_by_subscription(self):
        self.path.write_text('[]', encoding="utf-8")
        with self.assertRaises(store.StoreCorruptedError):
            store.subscribe(123, "09:00")
        self.assertEqual(self.path.read_text(encoding="utf-8"), '[]')

    def test_unreadable_utf8_cannot_be_overwritten_by_unsubscribe(self):
        self.path.write_bytes(b"\\xff\\xfe")
        with self.assertRaises(store.StoreCorruptedError):
            store.unsubscribe(123)
        self.assertEqual(self.path.read_bytes(), b"\\xff\\xfe")


if __name__ == "__main__":
    unittest.main()
