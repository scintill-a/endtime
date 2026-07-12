"""Main TUI application controller for Endtime."""
import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Label, ListView
from textual.containers import Horizontal

from endtime.models import parse_task
from endtime.storage import StorageManager
from endtime.habits import process_habits
from endtime.widgets import CategoryItem, TodoItem, SessionSelectDialog, SessionControlDialog, ConfirmDialog
from endtime.session import SessionManager, SessionType, SessionState



class EndtimeApp(App):
    """Endtime terminal user interface controller."""
    CSS_PATH = "endtime.tcss"
    
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("J", "move_down", "Move Down", show=False),
        Binding("K", "move_up", "Move Up", show=False),
        Binding("space", "toggle", "Toggle", show=False),
        Binding("f", "toggle_focus", "Focus", show=False),
        Binding("w", "work_session", "Work", show=False),
        Binding("enter", "toggle", "Toggle", show=False),
        Binding("d", "delete_task", "Delete", show=False),
        Binding("e", "edit_task", "Edit", show=False),
        Binding("i", "insert_mode", "Insert", show=False),
        Binding("c", "toggle_collapse", "Collapse", show=False),
        Binding("C", "sweep_cleared", "Sweep", show=False),
        Binding("H", "toggle_help", "Help", show=False),
        Binding("y", "confirm_yes", "Yes", show=False),
        Binding("n", "confirm_no", "No", show=False),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.storage = StorageManager(self)
        self.session = SessionManager(self)
        self.tasks_data = []
        self.collapsed_tags = set()
        self.mode = "NORMAL"
        self.session_target_id = None
        self.editing_id = None
        self.pending_delete_id = None
        self.previous_highlighted = None
        self.show_help = False

    def compose(self) -> ComposeResult:
        yield Label("", id="header", markup=True)
        yield ListView(id="task-list")
        with Horizontal(id="bottom-bar"):
            yield Label("[#ff4444]>[/] ", id="prompt-prefix", markup=True)
            yield Label("AWAITING TASK...", id="prompt-label", markup=True)
            yield Input(id="task-input")

    def on_mount(self) -> None:
        self.load_collapsed_tags()
        self.load_tasks()
        self.action_normal_mode()

    def update_header(self):
        header = self.query_one("#header", Label)
        total = len(self.tasks_data)
        completed_count = sum(1 for t in self.tasks_data if t.get("completed", False))
        
        mode_color = "#ff4444" if self.mode == "NORMAL" else "#ffffff"
        mode_display = self.mode
        if self.mode == "INSERT" and self.editing_id:
            mode_display = "EDIT"
            
        help_tag = r"\[H] hide" if self.show_help else r"\[H] help"
        line1 = f" {self.session.get_header_badge()}[{mode_color}]{mode_display}[/] | {completed_count}/{total} | {help_tag}"
        
        if self.show_help:
            cmd_text = r"\[j/k]nav \[J/K]move \[spc]check \[f]focus \[w]work \[c]collapse \[i]add \[e]edit \[d]del \[C]clear"
            if self.mode == "INSERT":
                cmd_text = r"\[enter]submit \[esc]cancel"
            elif self.mode.startswith("CONFIRM"):
                cmd_text = r"\[y/enter]confirm \[n/esc]cancel"
            line2 = f"\n {cmd_text}"
        else:
            line2 = ""
        
        header.update(f"{line1}{line2}")

    def update_prompt(self, text: str):
        lbl = self.query_one("#prompt-label", Label)
        lbl.display = True
        lbl.update(text)
        self.query_one("#task-input", Input).display = False

    def load_tasks(self):
        self.tasks_data = self.storage.load_tasks()
        if process_habits(self.tasks_data):
            self.schedule_save(tasks=True)
        self.refresh_list()

    def save_tasks(self):
        self.storage.save_tasks_sync(self.tasks_data)

    def load_collapsed_tags(self):
        self.collapsed_tags = self.storage.load_collapsed_tags()

    def save_collapsed_tags(self):
        self.storage.save_collapsed_tags_sync(self.collapsed_tags)

    def schedule_save(self, tasks: bool = False, config: bool = False):
        self.storage.schedule_save(tasks=tasks, config=config)

    def on_unmount(self) -> None:
        self.storage._flush_save(immediate=True)

    def refresh_list(self, keep_index=True):
        task_list = self.query_one("#task-list", ListView)
        old_index = task_list.index

        task_list.clear()
        self.previous_highlighted = None
        
        pending = [t for t in self.tasks_data if not t.get("completed", False)]
        completed = [t for t in self.tasks_data if t.get("completed", False)]
        completed.sort(
            key=lambda t: (parse_task(t["text"], t)[0] == "DAILY", t.get("completed_at", "")),
            reverse=True,
        )
        
        groups = {}
        for t in pending:
            tag, display_text = parse_task(t["text"], t)
            if tag not in groups:
                groups[tag] = []
            groups[tag].append((t, display_text))

        sorted_tags = sorted(groups.keys())
        if "GENERAL" in sorted_tags:
            sorted_tags.remove("GENERAL")
            sorted_tags.insert(0, "GENERAL")
        if "DAILY" in sorted_tags:
            sorted_tags.remove("DAILY")
            sorted_tags.insert(0, "DAILY")
        
        for tag in sorted_tags:
            is_col = (tag in self.collapsed_tags)
            count = len(groups[tag])
            task_list.append(CategoryItem(tag, collapsed=is_col, count=count))
            if not is_col:
                for t, display_text in groups[tag]:
                    streak = t.get("streak", 0) if tag == "DAILY" else 0
                    focused = t.get("focused", False)
                    session_badge = self.session.get_badge_text() if getattr(self, "session", None) and self.session.active_task_id == t["id"] else ""
                    time_spent = t.get("time_spent_seconds", 0)
                    item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused, session_badge=session_badge, time_spent_seconds=time_spent)
                    task_list.append(item)

        if completed:
            is_col = ("CLEARED" in self.collapsed_tags)
            count = len(completed)
            task_list.append(CategoryItem("CLEARED", collapsed=is_col, count=count))
            if not is_col:
                for t in completed:
                    tag, display_text = parse_task(t["text"], t)
                    streak = t.get("streak", 0) if tag == "DAILY" else 0
                    focused = t.get("focused", False)
                    session_badge = self.session.get_badge_text() if getattr(self, "session", None) and self.session.active_task_id == t["id"] else ""
                    time_spent = t.get("time_spent_seconds", 0)
                    item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused, session_badge=session_badge, time_spent_seconds=time_spent)
                    item.add_class("-completed")
                    task_list.append(item)
            
        if keep_index and old_index is not None and len(task_list.children) > 0:
            new_idx = min(old_index, len(task_list.children) - 1)
            task_list.index = new_idx
        elif len(task_list) > 0:
            for i, child in enumerate(task_list.children):
                if isinstance(child, (TodoItem, CategoryItem)):
                    task_list.index = i
                    break

        self.update_header()

    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        for t in self.tasks_data:
            if t["id"] == task_id:
                return t
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_toggle()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.previous_highlighted and hasattr(self.previous_highlighted, "set_highlighted"):
            self.previous_highlighted.set_highlighted(False)
        if event.item and hasattr(event.item, "set_highlighted"):
            event.item.set_highlighted(True)
        self.previous_highlighted = event.item

    def action_insert_mode(self):
        if self.mode != "NORMAL":
            return
        self.mode = "INSERT"
        self.editing_id = None
        self.update_header()
        
        self.query_one("#prompt-label", Label).display = False
        input_box = self.query_one("#task-input", Input)
        input_box.display = True
        input_box.value = ""
        input_box.focus()

    def action_normal_mode(self):
        self.mode = "NORMAL"
        self.editing_id = None
        self.pending_delete_id = None
        self.session_target_id = None
        self.update_header()
        
        self.query_one("#task-input", Input).display = False
        lbl = self.query_one("#prompt-label", Label)
        lbl.display = True
        lbl.update("AWAITING TASK...")
        
        self.query_one("#task-list", ListView).focus()

    def action_cursor_down(self):
        if self.mode == "NORMAL":
            self.query_one("#task-list", ListView).action_cursor_down()

    def action_cursor_up(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            task_list.action_cursor_up()
            if task_list.index == 1:
                task_list.scroll_home()

    def _swap_tasks_in_group(self, task_id: str, direction: int) -> bool:
        idx = -1
        for i, t in enumerate(self.tasks_data):
            if t["id"] == task_id:
                idx = i
                break
        
        if idx == -1:
            return False

        task = self.tasks_data[idx]
        task_tag, _ = parse_task(task["text"], task)
        is_completed = task.get("completed", False)

        target_idx = -1
        step = 1 if direction == 1 else -1
        curr = idx + step
        
        while 0 <= curr < len(self.tasks_data):
            other = self.tasks_data[curr]
            other_tag, _ = parse_task(other["text"], other)
            if other.get("completed", False) == is_completed and other_tag == task_tag:
                target_idx = curr
                break
            curr += step

        if target_idx != -1:
            self.tasks_data[idx], self.tasks_data[target_idx] = self.tasks_data[target_idx], self.tasks_data[idx]
            self.schedule_save(tasks=True)
            return True
        return False

    def action_move_up(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    if self._swap_tasks_in_group(item.task_id, -1):
                        self.refresh_list(keep_index=False)
                        for i, child in enumerate(task_list.children):
                            if getattr(child, "task_id", None) == item.task_id:
                                task_list.index = i
                                break

    def action_move_down(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    if self._swap_tasks_in_group(item.task_id, 1):
                        self.refresh_list(keep_index=False)
                        for i, child in enumerate(task_list.children):
                            if getattr(child, "task_id", None) == item.task_id:
                                task_list.index = i
                                break

    def action_toggle_help(self):
        if self.mode == "NORMAL":
            self.show_help = not self.show_help
            self.update_header()

    def action_toggle(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, CategoryItem):
                    self.action_toggle_collapse()
                    return
                if isinstance(item, TodoItem):
                    task_data = self.get_task_by_id(item.task_id)
                    if task_data:
                        task_data["completed"] = not task_data["completed"]
                        if task_data["completed"]:
                            task_data["completed_at"] = datetime.now().isoformat()
                        else:
                            if "completed_at" in task_data:
                                del task_data["completed_at"]
                        tag, _ = parse_task(task_data["text"], task_data)
                        if tag == "DAILY":
                            today_str = date.today().isoformat()
                            completed_dates = task_data.get("completed_dates", [])
                            if task_data["completed"] and today_str not in completed_dates:
                                completed_dates.append(today_str)
                            elif not task_data["completed"] and today_str in completed_dates:
                                completed_dates.remove(today_str)
                            task_data["completed_dates"] = completed_dates
                            
                        self.schedule_save(tasks=True)
                        self.refresh_list(keep_index=True)
        elif self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP"):
            self.action_confirm_yes()

    def action_toggle_collapse(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                tag_to_toggle = None
                if isinstance(item, CategoryItem):
                    tag_to_toggle = item.text
                elif isinstance(item, TodoItem):
                    if item.completed:
                        tag_to_toggle = "CLEARED"
                    else:
                        tag_to_toggle, _ = parse_task(item.original_text)
                
                if tag_to_toggle:
                    if tag_to_toggle in self.collapsed_tags:
                        self.collapsed_tags.remove(tag_to_toggle)
                    else:
                        self.collapsed_tags.add(tag_to_toggle)
                    self.schedule_save(config=True)
                    self.refresh_list(keep_index=False)
                    for i, child in enumerate(task_list.children):
                        if isinstance(child, CategoryItem) and child.text == tag_to_toggle:
                            task_list.index = i
                            break

    def action_toggle_focus(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    task_data = self.get_task_by_id(item.task_id)
                    if task_data:
                        task_data["focused"] = not task_data.get("focused", False)
                        item.update_data_and_refresh(focused=task_data["focused"])
                        self.schedule_save(tasks=True)

    def action_delete_task(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    delete_id = item.task_id
                    _, task_display = parse_task(item.original_text)
                    
                    def delete_callback(confirmed: bool) -> None:
                        if confirmed:
                            self.tasks_data = [t for t in self.tasks_data if t["id"] != delete_id]
                            self.save_tasks()
                            self.refresh_list(keep_index=True)
                        self.action_normal_mode()
                    
                    self.push_screen(
                        ConfirmDialog("DELETE TASK?", f"Are you sure you want to delete:\n'{task_display}'?"),
                        delete_callback
                    )

    def action_sweep_cleared(self):
        if self.mode == "NORMAL":
            completed = [t for t in self.tasks_data if t.get("completed", False)]
            if not completed:
                return
            
            def sweep_callback(confirmed: bool) -> None:
                if confirmed:
                    self.tasks_data = [
                        t for t in self.tasks_data
                        if not t.get("completed", False) or parse_task(t["text"], t)[0] == "DAILY"
                    ]
                    self.save_tasks()
                    self.refresh_list(keep_index=True)
                self.action_normal_mode()
            
            self.push_screen(
                ConfirmDialog("SWEEP CLEARED TASKS?", "Are you sure you want to sweep all completed tasks?"),
                sweep_callback
            )

    def action_edit_task(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    self.mode = "INSERT"
                    self.editing_id = item.task_id
                    self.update_header()
                    
                    self.query_one("#prompt-label", Label).display = False
                    input_box = self.query_one("#task-input", Input)
                    input_box.display = True
                    input_box.value = item.original_text
                    input_box.focus()
                    input_box.action_end()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            if self.editing_id:
                task_data = self.get_task_by_id(self.editing_id)
                if task_data:
                    task_data["text"] = text
            else:
                self.tasks_data.insert(0, {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "completed": False
                })
            self.schedule_save(tasks=True)
            self.refresh_list(keep_index=True)
        self.action_normal_mode()

    def action_work_session(self):
        if self.mode != "NORMAL":
            return
        task_list = self.query_one("#task-list", ListView)
        if task_list.index is not None and task_list.children:
            item = task_list.children[task_list.index]
            if isinstance(item, TodoItem):
                self.session_target_id = item.task_id
                _, task_display = parse_task(item.original_text)
                
                if self.session.state != SessionState.IDLE and self.session.active_task_id == item.task_id:
                    is_paused = (self.session.state == SessionState.PAUSED)
                    def control_callback(choice: Optional[str]) -> None:
                        if choice == "p":
                            self.session.toggle_pause()
                        elif choice == "s":
                            self.session.stop_and_save()
                        elif choice == "c":
                            self.session.cancel_session()
                        self.action_normal_mode()
                    
                    self.push_screen(
                        SessionControlDialog(task_display, self.session.get_badge_text(), is_paused=is_paused),
                        control_callback
                    )
                else:
                    def select_callback(choice: Optional[str]) -> None:
                        if choice == "1":
                            self.session.start_session(self.session_target_id, SessionType.POMODORO, duration=25 * 60)
                        elif choice == "2":
                            self.session.start_session(self.session_target_id, SessionType.BREAK, duration=5 * 60)
                        elif choice == "3":
                            self.session.start_session(self.session_target_id, SessionType.STOPWATCH, duration=0)
                        self.action_normal_mode()
                    
                    self.push_screen(
                        SessionSelectDialog(task_display),
                        select_callback
                    )



def main():
    """Run the Endtime TUI application."""
    app = EndtimeApp()
    app.run()


if __name__ == "__main__":
    main()
