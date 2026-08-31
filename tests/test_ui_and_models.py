"""Unit tests for UI formatting, progress gauges, and models."""
import unittest
from endtime.models import parse_task, format_duration, format_accumulated_time
from endtime.habits import process_habits
from endtime.app import format_progress_gauge


class TestModelsAndUI(unittest.TestCase):
    def test_parse_task_with_tags(self):
        tag, display = parse_task("[WORK] Write quarterly review")
        self.assertEqual(tag, "WORK")
        self.assertEqual(display, "Write quarterly review")

        tag2, display2 = parse_task("Plain task without tag")
        self.assertEqual(tag2, "GENERAL")
        self.assertEqual(display2, "Plain task without tag")

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(1500), "25:00")
        self.assertEqual(format_duration(3665), "01:01:05")

    def test_format_accumulated_time(self):
        self.assertEqual(format_accumulated_time(45), "45s")
        self.assertEqual(format_accumulated_time(120), "2m")
        self.assertEqual(format_accumulated_time(3600), "1h")
        self.assertEqual(format_accumulated_time(5400), "1h 30m")

    def test_format_progress_gauge(self):
        gauge_empty = format_progress_gauge(0, 0)
        self.assertIn("0%", gauge_empty)

        gauge_half = format_progress_gauge(5, 10)
        self.assertIn("50%", gauge_half)
        self.assertIn("█", gauge_half)

        gauge_full = format_progress_gauge(10, 10)
        self.assertIn("100%", gauge_full)

    def test_process_habits(self):
        tasks = [
            {
                "id": "h1",
                "text": "[DAILY] Read 20 pages",
                "completed": True,
                "completed_dates": ["2026-08-30"],  # Completed yesterday, but not today
                "streak": 1,
            }
        ]
        changed = process_habits(tasks)
        # Should reset completion state for today and calculate streak
        self.assertTrue(changed)
        self.assertFalse(tasks[0]["completed"])


if __name__ == "__main__":
    unittest.main()
