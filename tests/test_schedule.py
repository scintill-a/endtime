"""Unit tests for Endtime schedule parsing, reminders, and ScheduleManager."""
import unittest
from datetime import datetime, timedelta, date, time
from endtime.schedule import parse_schedule_string, format_schedule_badge, ScheduleManager


class DummyApp:
    def __init__(self):
        self.tasks_data = [
            {
                "id": "task-1",
                "text": "[WORK] Submit quarterly budget",
                "completed": False,
                "schedule": None,
            },
            {
                "id": "task-2",
                "text": "[DAILY] Review emails",
                "completed": False,
                "schedule": {
                    "scheduled_at": "2026-08-31T18:00:00",
                    "remind_at": "2026-08-31T18:00:00",
                    "notified": False,
                },
            },
        ]
        self.saved = False
        self.screen_pushed = None

    def get_task_by_id(self, task_id):
        for t in self.tasks_data:
            if t["id"] == task_id:
                return t
        return None

    def schedule_save(self, tasks=False, config=False):
        self.saved = True

    def refresh_list(self, keep_index=True):
        pass

    def push_screen(self, screen):
        self.screen_pushed = screen


class TestSchedule(unittest.TestCase):
    def test_parse_relative_minutes(self):
        now = datetime(2026, 8, 31, 14, 0, 0)
        dt = parse_schedule_string("@in 15m", now=now)
        self.assertEqual(dt, datetime(2026, 8, 31, 14, 15, 0))

        dt2 = parse_schedule_string("+30min", now=now)
        self.assertEqual(dt2, datetime(2026, 8, 31, 14, 30, 0))

        dt3 = parse_schedule_string("1h", now=now)
        self.assertEqual(dt3, datetime(2026, 8, 31, 15, 0, 0))

    def test_parse_time_of_day_future(self):
        now = datetime(2026, 8, 31, 10, 0, 0)
        dt = parse_schedule_string("@14:30", now=now)
        self.assertEqual(dt, datetime(2026, 8, 31, 14, 30, 0))

        dt_pm = parse_schedule_string("2:30pm", now=now)
        self.assertEqual(dt_pm, datetime(2026, 8, 31, 14, 30, 0))

    def test_parse_time_of_day_past_rolls_to_tomorrow(self):
        now = datetime(2026, 8, 31, 18, 0, 0)
        # 09:00 already passed today, so should schedule for tomorrow
        dt = parse_schedule_string("09:00", now=now)
        self.assertEqual(dt, datetime(2026, 9, 1, 9, 0, 0))

    def test_parse_tomorrow(self):
        now = datetime(2026, 8, 31, 14, 0, 0)
        dt = parse_schedule_string("tomorrow 15:00", now=now)
        self.assertEqual(dt, datetime(2026, 9, 1, 15, 0, 0))

        dt_default = parse_schedule_string("tomorrow", now=now)
        self.assertEqual(dt_default, datetime(2026, 9, 1, 9, 0, 0))

    def test_format_schedule_badge(self):
        now = datetime(2026, 8, 31, 14, 0, 0)
        # in 15m
        badge1 = format_schedule_badge(datetime(2026, 8, 31, 14, 15, 0), now=now)
        self.assertIn("in 15m", badge1)

        # overdue by 20m
        badge2 = format_schedule_badge(datetime(2026, 8, 31, 13, 40, 0), now=now)
        self.assertIn("[OVERDUE]", badge2)
        self.assertIn("20m", badge2)

    def test_is_task_overdue(self):
        app = DummyApp()
        sm = ScheduleManager(app)
        now = datetime(2026, 8, 31, 19, 0, 0)

        # task-2 is scheduled for 18:00 (1 hour ago) -> overdue
        task2 = app.get_task_by_id("task-2")
        self.assertTrue(sm.is_task_overdue(task2, now=now))

        # task with future schedule -> not overdue
        future_task = {
            "id": "t-fut",
            "text": "Future task",
            "completed": False,
            "schedule": {"remind_at": "2026-08-31T20:00:00"}
        }
        self.assertFalse(sm.is_task_overdue(future_task, now=now))

        # completed task -> not overdue
        comp_task = {
            "id": "t-comp",
            "text": "Done task",
            "completed": True,
            "schedule": {"remind_at": "2026-08-31T18:00:00"}
        }
        self.assertFalse(sm.is_task_overdue(comp_task, now=now))

    def test_extract_and_apply_schedule(self):
        app = DummyApp()
        sm = ScheduleManager(app)
        task = {"id": "t3", "text": "Draft report"}

        cleaned = sm.extract_and_apply_schedule(task, "[WORK] @in 15m Draft report")
        self.assertEqual(cleaned, "[WORK] Draft report")
        self.assertIsNotNone(task.get("schedule"))
        self.assertFalse(task["schedule"]["notified"])

    def test_snooze_task(self):
        app = DummyApp()
        sm = ScheduleManager(app)
        sm.snooze_task("task-2", minutes=15)

        task2 = app.get_task_by_id("task-2")
        self.assertFalse(task2["schedule"]["notified"])
        remind_dt = datetime.fromisoformat(task2["schedule"]["remind_at"])
        self.assertTrue(remind_dt > datetime.now())

    def test_clear_schedule(self):
        app = DummyApp()
        sm = ScheduleManager(app)
        sm.clear_schedule("task-2")
        task2 = app.get_task_by_id("task-2")
        self.assertIsNone(task2["schedule"])


if __name__ == "__main__":
    unittest.main()
