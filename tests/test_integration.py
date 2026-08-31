"""End-to-end integration and palette compliance tests for Endtime TUI app."""
import os
import re
import tempfile
import asyncio
import unittest
from pathlib import Path

# Ensure package root is on python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from textual.events import Key
from textual.widgets import Input, ListView
from endtime.app import EndtimeApp, format_progress_gauge
from endtime.widgets import SessionPickerModal, SessionOverlayModal, ScheduleModal, HelpModal


import json

class TestEndtimeIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_env = os.environ.get("ENDTIME_DATA_DIR")
        os.environ["ENDTIME_DATA_DIR"] = self.temp_dir.name
        
        # Write initial tasks so on_mount loads them into task_list
        tasks_file = Path(self.temp_dir.name) / "tasks.json"
        initial_tasks = [
            {"id": "t-1", "text": "[WORK] Complete annual report", "completed": False, "focused": True},
            {"id": "t-2", "text": "[DAILY] Read 20 pages", "completed": False, "streak": 3},
            {"id": "t-3", "text": "Buy groceries @18:00", "completed": True},
        ]
        with open(tasks_file, "w") as f:
            json.dump(initial_tasks, f)

    def tearDown(self):
        if self.old_env is not None:
            os.environ["ENDTIME_DATA_DIR"] = self.old_env
        else:
            os.environ.pop("ENDTIME_DATA_DIR", None)
        self.temp_dir.cleanup()

    def test_app_boot_insert_visibility_and_navigation(self):
        """Test full app lifecycle with isolated storage, typing visibility, and navigation."""
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                # 1. Assert tasks rendered in ListView
                task_list = pilot.app.query_one("#task-list", ListView)
                self.assertGreater(len(task_list.children), 0)

                # 2. Test navigation
                await pilot.press("j")
                await pilot.press("k")

                # 3. Test insert mode typing visibility
                await pilot.press("i")
                self.assertEqual(pilot.app.mode, "INSERT")
                inp = pilot.app.query_one("#task-input", Input)
                bar = pilot.app.query_one("#bottom-bar")
                self.assertTrue(inp.display)
                self.assertGreaterEqual(bar.size.height, 1, "Bottom bar must render with positive height")
                self.assertGreaterEqual(inp.size.height, 1, "Input widget must have positive height")

                await pilot.press("h", "e", "l", "l", "o")
                self.assertEqual(inp.value, "hello")
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")

                # 4. Test search mode
                await pilot.press("slash")
                self.assertEqual(pilot.app.mode, "SEARCH")
                inp = pilot.app.query_one("#task-input", Input)
                await pilot.press("a", "n", "n", "u", "a", "l")
                self.assertEqual(pilot.app.search_query, "annual")
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")

                # 5. Test help modal & j/k scrolling
                await pilot.press("question_mark")
                help_screen = next(s for s in pilot.app._screen_stack if isinstance(s, HelpModal))
                self.assertIsNotNone(help_screen)
                help_card = help_screen.query_one("#help-card")
                initial_y = help_card.scroll_y
                await pilot.press("j", "j")
                self.assertGreaterEqual(help_card.scroll_y, initial_y)
                await pilot.press("k")
                await pilot.press("escape")
                self.assertFalse(any(isinstance(s, HelpModal) for s in pilot.app._screen_stack))

                await pilot.exit(None)

        asyncio.run(run())

    def test_edit_mode_flow(self):
        """Test Edit task mode (e) and input pre-population."""
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                task_list = pilot.app.query_one("#task-list", ListView)
                # Find first TodoItem
                target_item = None
                for idx, child in enumerate(task_list.children):
                    if type(child).__name__ == "TodoItem":
                        task_list.index = idx
                        target_item = child
                        break
                self.assertIsNotNone(target_item)
                await pilot.press("e")
                self.assertEqual(pilot.app.mode, "INSERT")
                self.assertIsNotNone(pilot.app.editing_id)
                inp = pilot.app.query_one("#task-input", Input)
                self.assertEqual(inp.value, target_item.original_text)
                await pilot.press("escape")
                self.assertEqual(pilot.app.mode, "NORMAL")
                self.assertIsNone(pilot.app.editing_id)
                await pilot.exit(None)

        asyncio.run(run())

    def test_task_toggle_and_sweep(self):
        """Test focus toggle, task check, and sweep confirmation."""
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                task_list = pilot.app.query_one("#task-list", ListView)
                # Find first TodoItem
                for idx, child in enumerate(task_list.children):
                    if type(child).__name__ == "TodoItem":
                        task_list.index = idx
                        break
                item = task_list.children[task_list.index]
                task_id = item.task_id
                task_data = pilot.app.get_task_by_id(task_id)
                init_focus = task_data.get("focused", False)
                await pilot.press("f")
                self.assertNotEqual(task_data.get("focused", False), init_focus)

                init_comp = task_data.get("completed", False)
                await pilot.press("space")
                self.assertNotEqual(task_data.get("completed", False), init_comp)

                # Sweep completed tasks
                await pilot.press("C")
                self.assertEqual(pilot.app.mode, "CONFIRM_SWEEP")
                await pilot.press("y")
                await pilot.pause()
                self.assertEqual(pilot.app.mode, "NORMAL")
                await pilot.exit(None)

        asyncio.run(run())

    def test_schedule_and_session_modal_flow(self):
        """Test interactive ScheduleModal and SessionModal push and dismiss."""
        async def run():
            app = EndtimeApp()
            async with app.run_test(headless=True) as pilot:
                task_list = pilot.app.query_one("#task-list", ListView)
                for idx, child in enumerate(task_list.children):
                    if type(child).__name__ == "TodoItem":
                        task_list.index = idx
                        break
                await pilot.pause()
                await pilot.press("at")
                await pilot.pause()
                self.assertTrue(any(isinstance(s, ScheduleModal) for s in pilot.app._screen_stack))
                await pilot.press("1")  # Select 15m
                await pilot.pause()
                self.assertFalse(any(isinstance(s, ScheduleModal) for s in pilot.app._screen_stack))

                # Launch Work Session
                await pilot.press("w")
                await pilot.pause()
                self.assertTrue(any(isinstance(s, SessionPickerModal) for s in pilot.app._screen_stack))
                await pilot.press("1")  # Launch Pomodoro
                await pilot.pause()
                self.assertTrue(any(isinstance(s, SessionOverlayModal) for s in pilot.app._screen_stack))
                await pilot.press("p")  # Pause
                await pilot.press("m")  # Minimize
                await pilot.pause()
                self.assertFalse(any(isinstance(s, SessionOverlayModal) for s in pilot.app._screen_stack))

                await pilot.exit(None)

        asyncio.run(run())

    def test_schedule_modal_navigation_and_focus(self):
        """Test ScheduleModal keyboard navigation and custom input isolation."""
        modal = ScheduleModal("Plan trip", is_scheduled=True)
        self.assertEqual(modal.selected_index, 0)

        # Nav down with j
        modal.on_key(Key("j", "j"))
        self.assertEqual(modal.selected_index, 1)

        # Nav down with down key
        modal.on_key(Key("down", ""))
        self.assertEqual(modal.selected_index, 2)

        # Nav up with k
        modal.on_key(Key("k", "k"))
        self.assertEqual(modal.selected_index, 1)

        # Nav up with up key
        modal.on_key(Key("up", ""))
        self.assertEqual(modal.selected_index, 0)

        # Clear schedule sentinel
        dt_clear = modal._resolve_selection("clear")
        self.assertEqual(dt_clear, "CLEAR")

    def test_session_picker_modal_navigation(self):
        """Test SessionPickerModal navigation and continue option."""
        picker_modal = SessionPickerModal("Complete report", saved_session={"type": "POMODORO", "remaining_seconds": 900})
        self.assertEqual(picker_modal.options[0][0], "continue")
        self.assertEqual(picker_modal.selected_index, 0)

        picker_modal.on_key(Key("j", "j"))
        self.assertEqual(picker_modal.selected_index, 1)

        picker_modal.on_key(Key("k", "k"))
        self.assertEqual(picker_modal.selected_index, 0)

    def test_progress_gauge_strict_palette(self):
        """Test progress gauge rendering adhering strictly to red/white/gray palette."""
        gauge_empty = format_progress_gauge(0, 10)
        self.assertIn("0%", gauge_empty)

        gauge_mid = format_progress_gauge(5, 10)
        self.assertIn("50%", gauge_mid)
        self.assertIn("#ffffff", gauge_mid)

        gauge_full = format_progress_gauge(10, 10)
        self.assertIn("100%", gauge_full)
        self.assertIn("#ffffff", gauge_full)

    def test_strict_palette_compliance(self):
        """Assert zero illegal accent colors (cyan, amber, yellow, green, blue, purple) exist in source files."""
        root = Path(__file__).parent.parent / "endtime"
        forbidden = [
            r"#00e5ff",
            r"#00b4d8",
            r"#ffaa00",
            r"#ffff00",
            r"\bcyan\b",
            r"\byellow\b",
            r"\bamber\b",
            r"\bgreen\b",
            r"\bblue\b",
            r"\bpurple\b",
            r"\borange\b",
        ]
        for p in root.rglob("*"):
            if p.suffix in (".py", ".tcss"):
                content = p.read_text(encoding="utf-8")
                for pattern in forbidden:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    self.assertEqual(
                        len(matches),
                        0,
                        f"Found forbidden palette pattern '{pattern}' in {p.name}: {matches}",
                    )


if __name__ == "__main__":
    unittest.main()

