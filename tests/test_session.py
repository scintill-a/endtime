"""Unit tests for Endtime session manager and snapshot continue feature."""
import unittest
from unittest.mock import MagicMock
from endtime.session import SessionManager, SessionType, SessionState


class DummyApp:
    def __init__(self):
        self.tasks_data = [
            {
                "id": "task-1",
                "text": "[WORK] Complete report",
                "completed": False,
                "time_spent_seconds": 120,
                "saved_session": None,
            },
            {
                "id": "task-2",
                "text": "[DAILY] Morning Workout",
                "completed": False,
                "time_spent_seconds": 0,
                "saved_session": {
                    "type": SessionType.POMODORO,
                    "remaining_seconds": 1200,
                    "total_cycle_seconds": 1500,
                    "elapsed_seconds": 300,
                    "pomodoro_round": 2,
                    "is_break": False,
                },
            }
        ]

    def get_task_by_id(self, task_id):
        for t in self.tasks_data:
            if t["id"] == task_id:
                return t
        return None

    def schedule_save(self, tasks=False, config=False):
        pass

    def update_header(self):
        pass

    def set_interval(self, interval, callback):
        mock_timer = MagicMock()
        return mock_timer


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.app = DummyApp()
        self.sm = SessionManager(self.app)

    def test_start_fresh_pomodoro(self):
        self.sm.start_session("task-1", SessionType.POMODORO, duration=25 * 60)
        self.assertEqual(self.sm.active_task_id, "task-1")
        self.assertEqual(self.sm.session_type, SessionType.POMODORO)
        self.assertEqual(self.sm.duration_seconds, 1500)
        self.assertEqual(self.sm.state, SessionState.RUNNING)
        self.assertEqual(self.sm.pomodoro_round, 1)

    def test_pause_and_resume_persists_snapshot(self):
        self.sm.start_session("task-1", SessionType.POMODORO, duration=25 * 60)
        self.sm.elapsed_seconds = 60
        self.sm.duration_seconds = 1440
        self.sm.toggle_pause()

        self.assertEqual(self.sm.state, SessionState.PAUSED)
        task1 = self.app.get_task_by_id("task-1")
        self.assertIsNotNone(task1["saved_session"])
        self.assertEqual(task1["saved_session"]["remaining_seconds"], 1440)

        # Resume
        self.sm.toggle_pause()
        self.assertEqual(self.sm.state, SessionState.RUNNING)

    def test_stop_and_save_preserves_snapshot(self):
        self.sm.start_session("task-1", SessionType.POMODORO, duration=25 * 60)
        self.sm.elapsed_seconds = 100
        self.sm.duration_seconds = 1400
        self.sm.stop_and_save(preserve_snapshot=True)

        self.assertEqual(self.sm.state, SessionState.IDLE)
        self.assertIsNone(self.sm.active_task_id)
        task1 = self.app.get_task_by_id("task-1")
        self.assertEqual(task1["time_spent_seconds"], 220)  # 120 + 100
        self.assertIsNotNone(task1["saved_session"])
        self.assertEqual(task1["saved_session"]["remaining_seconds"], 1400)

    def test_continue_saved_session(self):
        # task-2 has saved pomodoro with 1200 seconds remaining on round 2
        self.sm.start_session("task-2", SessionType.POMODORO, resume=True)
        self.assertEqual(self.sm.active_task_id, "task-2")
        self.assertEqual(self.sm.duration_seconds, 1200)
        self.assertEqual(self.sm.pomodoro_round, 2)
        self.assertEqual(self.sm.state, SessionState.RUNNING)

    def test_tick_and_save_clears_snapshot(self):
        self.sm.start_session("task-2", SessionType.POMODORO, resume=True)
        self.sm.elapsed_seconds = 50
        self.sm.tick_and_save()

        self.assertEqual(self.sm.state, SessionState.IDLE)
        task2 = self.app.get_task_by_id("task-2")
        self.assertTrue(task2["completed"])
        self.assertIsNone(task2["saved_session"])
        self.assertEqual(task2["time_spent_seconds"], 50)

    def test_clear_saved_session(self):
        self.sm.clear_saved_session("task-2")
        task2 = self.app.get_task_by_id("task-2")
        self.assertIsNone(task2["saved_session"])


if __name__ == "__main__":
    unittest.main()
