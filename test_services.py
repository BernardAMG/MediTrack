"""
test_services.py
Unit tests for domain and background services (services.watcher and services.adherence).
"""
import unittest
from datetime import datetime, timedelta
from services.watcher import _parse_single_time, normalize_time, should_alert
from services.adherence import calculate_adherence_stats, format_adherence_summary

class TestWatcherService(unittest.TestCase):
    def test_parse_single_time_formats(self):
        self.assertEqual(_parse_single_time("08:30"), "08:30")
        self.assertEqual(_parse_single_time("8:30"), "08:30")
        self.assertEqual(_parse_single_time("08:30 AM"), "08:30")
        self.assertEqual(_parse_single_time("8:30pm"), "20:30")
        self.assertEqual(_parse_single_time("8 pm"), "20:00")
        self.assertIsNone(_parse_single_time("invalid-time"))
        self.assertIsNone(_parse_single_time(None))

    def test_normalize_time_multi(self):
        # Deduplication and sorting
        result = normalize_time("20:00, 08:00, 20:00")
        self.assertEqual(result, "08:00, 20:00")

        # Semicolon delimiter
        result2 = normalize_time("12:00; 06:00")
        self.assertEqual(result2, "06:00, 12:00")

        # Invalid entry
        self.assertIsNone(normalize_time("not-a-time"))

    def test_should_alert_window(self):
        base_dt = datetime(2026, 11, 7, 8, 5)  # 08:05

        # Exactly at 08:00 -> within 15 min window (5 min difference)
        self.assertTrue(should_alert("08:00", current_dt=base_dt, window_minutes=15))

        # Exactly at 08:05 -> 0 min diff
        self.assertTrue(should_alert("08:05", current_dt=base_dt, window_minutes=15))

        # At 07:45 -> 20 min ago, outside window
        self.assertFalse(should_alert("07:45", current_dt=base_dt, window_minutes=15))

        # In the future (08:30) -> negative difference, should be False
        self.assertFalse(should_alert("08:30", current_dt=base_dt, window_minutes=15))

        # Invalid time input
        self.assertFalse(should_alert(None, current_dt=base_dt))
        self.assertFalse(should_alert("invalid", current_dt=base_dt))

class TestAdherenceService(unittest.TestCase):
    def test_empty_adherence(self):
        pct, taken, total = calculate_adherence_stats([])
        self.assertEqual(pct, 0)
        self.assertEqual(taken, 0)
        self.assertEqual(total, 0)
        self.assertEqual(format_adherence_summary([]), "No doses logged yet.")

    def test_perfect_adherence(self):
        records = [
            ("Amoxicillin", "taken", "2026-11-07 08:00:00", "08:00"),
            ("Amoxicillin", "taken", "2026-11-07 20:00:00", "20:00"),
        ]
        pct, taken, total = calculate_adherence_stats(records)
        self.assertEqual(pct, 100)
        self.assertEqual(taken, 2)
        self.assertEqual(total, 2)
        self.assertEqual(format_adherence_summary(records), "100% adherence (2 of 2 doses taken)")

    def test_partial_adherence(self):
        records = [
            ("Metformin", "taken", "2026-11-06 08:00:00", "08:00"),
            ("Metformin", "skipped", "2026-11-06 20:00:00", "20:00"),
            ("Metformin", "taken", "2026-11-07 08:00:00", "08:00"),
        ]
        pct, taken, total = calculate_adherence_stats(records)
        self.assertEqual(pct, 67)
        self.assertEqual(taken, 2)
        self.assertEqual(total, 3)
        self.assertEqual(format_adherence_summary(records), "67% adherence (2 of 3 doses taken)")

if __name__ == "__main__":
    unittest.main()
