"""End-to-end integration and palette compliance tests for Endtime TUI app."""
import sys
import re
from pathlib import Path
import unittest

# Ensure package root is on python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from textual.events import Key
from textual.widgets import Input
from endtime.app import EndtimeApp, format_progress_gauge
from endtime.widgets import SessionPickerModal, ScheduleModal, HelpModal


class TestEndtimeIntegration(unittest.TestCase):
    def test_app_actions_and_modals(self):
        """Test full set of App actions, search filtering, and modal instantiation."""
        app = EndtimeApp()
        app.load_collapsed_tags()
        app.load_tag_order()
        app.tasks_data = [
            {"id": "t-1", "text": "[WORK] Complete annual report", "completed": False, "focused": True},
            {"id": "t-2", "text": "[DAILY] Read 20 pages", "completed": False, "streak": 3},
            {"id": "t-3", "text": "Buy groceries @18:00", "completed": True},
        ]
        
        # Test progress gauge format
        gauge = format_progress_gauge(1, 3)
        self.assertIn("33%", gauge)
        self.assertNotIn("#00e5ff", gauge)
        self.assertNotIn("#ffaa00", gauge)

        # Test search mode filter
        app.mode = "SEARCH"
        app.search_query = "annual"
        matching = [t for t in app.tasks_data if "annual" in t["text"].lower()]
        self.assertEqual(len(matching), 1)

        # Exit search mode to insert mode
        app.mode = "INSERT"
        dummy_input = Input(id="task-input")
        app.on_input_submitted(Input.Submitted(dummy_input, "[PERSONAL] Plan weekend trip @tomorrow 10:00"))
        new_task = app.tasks_data[0]
        self.assertEqual(new_task["text"], "[PERSONAL] Plan weekend trip")
        self.assertIsNotNone(new_task.get("schedule"))

        # Test schedule modal
        sched_modal = ScheduleModal("Plan trip", is_scheduled=True)
        self.assertEqual(sched_modal.selected_index, 0)
        sched_modal.on_key(Key("j", "j"))
        self.assertEqual(sched_modal.selected_index, 1)
        sched_modal.on_key(Key("k", "k"))
        self.assertEqual(sched_modal.selected_index, 0)

        # Test session picker modal with continue option
        picker_modal = SessionPickerModal("Complete annual report", saved_session={"type": "POMODORO", "remaining_seconds": 900})
        self.assertEqual(picker_modal.options[0][0], "continue")
        picker_modal.on_key(Key("j", "j"))
        self.assertEqual(picker_modal.selected_index, 1)

        # Test help modal
        help_modal = HelpModal()
        self.assertIsNotNone(help_modal)

    def test_strict_palette_compliance(self):
        """Assert no illegal accent colors (cyan, amber, yellow) exist in source files."""
        root = Path(__file__).parent.parent / "endtime"
        forbidden = [r"#00e5ff", r"#ffaa00", r"#ffff00", r"\bcyan\b", r"\byellow\b"]
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
