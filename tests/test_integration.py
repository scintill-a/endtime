"""End-to-end integration tests for Endtime TUI app."""
import asyncio
import unittest
from endtime.app import EndtimeApp
from endtime.widgets import SessionPickerModal, ScheduleModal, HelpModal


class TestEndtimeIntegration(unittest.TestCase):
    def test_app_boot_navigation_and_insert(self):
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                task_list = pilot.app.query_one("#task-list")
                self.assertGreater(len(task_list.children), 0)

                # Test navigation
                await pilot.press("j")
                await pilot.press("k")

                # Test insert typing visibility
                await pilot.press("i")
                self.assertEqual(pilot.app.mode, "INSERT")
                input_box = pilot.app.query_one("#task-input")
                self.assertTrue(input_box.display)
                await pilot.press("t", "e", "s", "t")
                self.assertEqual(input_box.value, "test")
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")

                # Test search mode
                await pilot.press("slash")
                self.assertEqual(pilot.app.mode, "SEARCH")
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")

                # Test schedule modal navigation (move to TodoItem first)
                await pilot.press("j")
                await pilot.press("at")
                self.assertTrue(any(isinstance(s, ScheduleModal) for s in pilot.app._screen_stack))
                sched_modal = [s for s in pilot.app._screen_stack if isinstance(s, ScheduleModal)][0]
                self.assertEqual(sched_modal.selected_index, 0)
                await pilot.press("j")
                self.assertEqual(sched_modal.selected_index, 1)
                await pilot.press("k")
                self.assertEqual(sched_modal.selected_index, 0)
                await pilot.press("escape")

                # Test help modal
                await pilot.press("question_mark")
                self.assertTrue(any(isinstance(s, HelpModal) for s in pilot.app._screen_stack))
                await pilot.press("escape")

                await pilot.exit(None)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
