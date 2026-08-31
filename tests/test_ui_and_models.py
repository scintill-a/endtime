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
        from datetime import date, timedelta
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        tasks = [
            {
                "id": "h1",
                "text": "[DAILY] Read 20 pages",
                "completed": True,
                "completed_dates": [two_days_ago, yesterday_str],
                "time_spent_seconds": 1800,
                "saved_session": {"type": "POMODORO", "remaining_seconds": 600},
                "last_habit_date": yesterday_str,
                "streak": 2,
            }
        ]
        changed = process_habits(tasks)
        # Should reset completion state, timer data, saved session for new day, and preserve 2-day streak
        self.assertTrue(changed)
        self.assertFalse(tasks[0]["completed"])
        self.assertEqual(tasks[0]["time_spent_seconds"], 0)
        self.assertIsNone(tasks[0]["saved_session"])
        self.assertEqual(tasks[0]["streak"], 2)

    def test_process_habits_completed_today_preserved(self):
        from datetime import date
        today_str = date.today().isoformat()
        tasks = [
            {
                "id": "h2",
                "text": "[DAILY] 30m Workout",
                "completed": True,
                "completed_dates": [today_str],
                "time_spent_seconds": 1800,
                "last_habit_date": today_str,
                "streak": 1,
            }
        ]
        changed = process_habits(tasks)
        self.assertFalse(changed)
        self.assertTrue(tasks[0]["completed"])
        self.assertEqual(tasks[0]["time_spent_seconds"], 1800)
        self.assertEqual(tasks[0]["streak"], 1)

    def test_process_habits_missed_streak_reset(self):
        from datetime import date, timedelta
        three_days_ago = (date.today() - timedelta(days=3)).isoformat()
        tasks = [
            {
                "id": "h3",
                "text": "[DAILY] Meditate",
                "completed": True,
                "completed_dates": [three_days_ago],
                "time_spent_seconds": 600,
                "streak": 5,
            }
        ]
        changed = process_habits(tasks)
        self.assertTrue(changed)
        self.assertFalse(tasks[0]["completed"])
        self.assertEqual(tasks[0]["time_spent_seconds"], 0)
        self.assertEqual(tasks[0]["streak"], 0)


if __name__ == "__main__":
    unittest.main()
