import json
import unittest
from datetime import date

from coach import store, sync, userdata
from coach.config import DATA_DIR, USERDATA_FILE


class Store(unittest.TestCase):
    def test_roundtrip_and_no_temp_files(self):
        p = DATA_DIR / "probe.json"
        store.write_json(p, {"ä": [1, 2]})
        store.write_json(p, {"ä": [3]})
        self.assertEqual(json.loads(store.read_text(p)), {"ä": [3]})
        self.assertEqual(list(p.parent.glob("*.tmp")), [])


class SyncHistory(unittest.TestCase):
    def test_window_replaced_older_kept(self):
        store.write_json(DATA_DIR / "hrv.json", [{"calendarDate": "2026-08-01", "v": 1},
                                                 {"calendarDate": "2026-10-01", "v": "alt"},
                                                 {"calendarDate": "2026-10-02", "v": "in Garmin gelöscht"}])
        merged = sync._with_history("hrv", [{"calendarDate": "2026-10-01", "v": "neu"}], date(2026, 9, 12))
        self.assertEqual([(x["calendarDate"], x["v"]) for x in merged], [("2026-08-01", 1), ("2026-10-01", "neu")])

    def test_activities_newest_first(self):
        store.write_json(DATA_DIR / "activities.json", [{"activityId": 2, "startTimeLocal": "2026-10-01 10:00:00"},
                                                        {"activityId": 1, "startTimeLocal": "2026-06-01 10:00:00"}])
        merged = sync._with_history("activities", [{"activityId": 3, "startTimeLocal": "2026-11-01 10:00:00"}],
                                    date(2026, 7, 14))
        self.assertEqual([x["activityId"] for x in merged], [3, 1])

    def test_empty_answer_keeps_data(self):
        store.write_json(DATA_DIR / "sleep_summaries.json", [{"calendarDate": "2026-10-01"}])
        with self.assertRaises(sync.EmptyResult):
            sync._with_history("sleep_summaries", [], date(2026, 9, 12))

    def test_first_sync_without_file(self):
        (DATA_DIR / "daily_summaries.json").unlink(missing_ok=True)
        new = [{"calendarDate": None}, {"calendarDate": "2026-11-10"}]
        self.assertEqual(sync._with_history("daily_summaries", new, date(2026, 9, 12)), new)


class Userdata(unittest.TestCase):
    def setUp(self):
        for p in USERDATA_FILE.parent.glob("userdata.json*"):
            p.unlink()

    def test_set_and_delete(self):
        userdata.set_entry("on_watch", "a", True)
        userdata.set_entry("on_watch", "b", True)
        userdata.set_entry("on_watch", "a", None)
        self.assertEqual(userdata.values(userdata.load(), "on_watch"), {"b": True})

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            userdata.set_entry("quatsch", "a", 1)

    def test_broken_file_does_not_wipe_entries(self):
        userdata.set_entry("notes", "1", {"feel": 4})
        userdata.set_entry("notes", "2", {"feel": 5})
        USERDATA_FILE.write_text('{"notes": {"1": ', encoding="utf-8")  # halb geschrieben
        self.assertIn("1", userdata.load()["notes"])  # aus der Sicherung
        userdata.set_entry("on_watch", "x", True)
        d = userdata.load()
        self.assertIn("1", d["notes"])
        self.assertIn("x", d["on_watch"])
        self.assertTrue(USERDATA_FILE.with_name("userdata.json.defekt").exists())


if __name__ == "__main__":
    unittest.main()
