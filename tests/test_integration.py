"""End-to-end integration tests for Endtime TUI app."""
import asyncio
import unittest
from endtime.app import EndtimeApp
from endtime.widgets import SessionPickerModal, ScheduleModal, HelpModal


class TestEndtimeIntegration(unittest.TestCase):
    def test_app_boot_and_navigation(self):
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                task_list = pilot.app.query_one("#task-list")
                self.assertGreater(len(task_list.children), 0)

                # Test navigation
                await pilot.press("j")
                await pilot.press("k")

                # Test search mode
                await pilot.press("slash")
                self.assertEqual(pilot.app.mode, "SEARCH")
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")

                # Test help modal
                await pilot.press("question_mark")
                self.assertTrue(any(isinstance(s, HelpModal) for s in pilot.app._screen_stack))
                await pilot.press("escape")

                await pilot.exit(None)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
