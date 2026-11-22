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

    def test_invalid_daily_time_never_replaces_saved_schedule(self):
        store.set_location(123, {"city": "Manila"})
        self.assertTrue(store.subscribe(123, "09:00"))
        original = self.path.read_bytes()
        for invalid in ("9:00", "24:00", "13:60", "12:00\\n", "", None, 930):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    store.subscribe(123, invalid)
                self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual([(cid, when) for cid, when, _ in store.all_subscriptions()],
                         [(123, "09:00")])

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
        self.path.write_bytes(bytes((0xff, 0xfe)))
        with self.assertRaises(store.StoreCorruptedError):
            store.unsubscribe(123)
        self.assertEqual(self.path.read_bytes(), bytes((0xff, 0xfe)))


    def test_malformed_records_do_not_stop_other_subscribers_or_modify_disk(self):
        records = {
            "-1001": {"city": "Manila", "daily": "09:00"},
            "broken": {"city": "Not a numeric chat", "daily": "10:30"},
            "1002": None,
            "1003": ["unexpected", "list"],
            "1004": {"city": "Cebu", "daily": 930},
            "1005": {"city": "Invalid", "daily": "25:99"},
            "1006": {"city": "Davao", "daily": "23:59"},
        }
        original = json.dumps(records, ensure_ascii=False).encode("utf-8")
        self.path.write_bytes(original)
        found = store.all_subscriptions()
        self.assertEqual([(cid, when) for cid, when, _ in found],
                         [(-1001, "09:00"), (1006, "23:59")])
        self.assertEqual(self.path.read_bytes(), original)

    def test_failed_atomic_replace_preserves_saved_preferences(self):
        store.set_location(123, {"city": "Manila"})
        original = self.path.read_bytes()
        with patch.object(store.os, "replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaises(OSError):
                store.set_location(123, {"city": "Cebu"})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()),
                         ["locations.json"])

    def test_unserializable_record_does_not_clobber_saved_preferences(self):
        store.set_location(123, {"city": "Manila"})
        original = self.path.read_bytes()
        with self.assertRaises(TypeError):
            store.set_location(123, {"city": object()})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()),
                         ["locations.json"])

    def test_unreadable_file_does_not_crash_subscription_listing_or_get_rewritten(self):
        original = b'{ "bad": '
        self.path.write_bytes(original)
        self.assertEqual(store.all_subscriptions(), [])
        self.assertEqual(self.path.read_bytes(), original)

    def test_malformed_chat_record_never_replaces_existing_data(self):
        records = {
            "123": ["unexpected", "list"],
            "456": {"city": "Cebu", "daily": "09:00"},
            "789": "unexpected string",
            "999": 0,
        }
        original = json.dumps(records, ensure_ascii=False).encode("utf-8")
        self.path.write_bytes(original)
        for chat_id in (123, 789, 999):
            self.assertIsNone(store.get_location(chat_id))
            self.assertFalse(store.subscribe(chat_id, "10:30"))
            store.unsubscribe(chat_id)
            with self.assertRaises(store.StoreCorruptedError):
                store.set_location(chat_id, {"city": "Manila"})
            self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(store.get_location(456)["daily"], "09:00")
        # A different, valid chat must still be able to save without dropping
        # malformed historic records belonging to other chat IDs.
        store.set_location(321, {"city": "Davao"})
        result = json.loads(self.path.read_text(encoding="utf-8"))
        for chat_id in ("123", "456", "789", "999"):
            self.assertEqual(result[chat_id], records[chat_id])
        self.assertEqual(result["321"]["city"], "Davao")

if __name__ == "__main__":
    unittest.main()
