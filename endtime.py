import json
import uuid
import re
from pathlib import Path
from datetime import date, timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Label, ListView, ListItem
from textual.containers import Horizontal

TASKS_DIR = Path.home() / ".config" / "endtime"
TASKS_FILE = TASKS_DIR / "tasks.json"

def parse_task(text):
    match = re.match(r'^\[([A-Z0-9_\-\s]+)\]\s*(.*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper(), match.group(2)
    return "GENERAL", text

class CategoryItem(ListItem):
    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.disabled = True
        
    def compose(self) -> ComposeResult:
        yield Label(f" --- {self.text} ---", classes="category-label")

class TodoItem(ListItem):
    def __init__(self, task_id: str, original_text: str, display_text: str, completed: bool = False, streak: int = 0, focused: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.task_id = task_id
        self.original_text = original_text
        self.display_text = display_text
        self.completed = completed
        self.streak = streak
        self.focused = focused
        self.is_highlighted = False

    def compose(self) -> ComposeResult:
        prefix = "[#ff4444]>[/] " if self.is_highlighted else "  "
        status = r"[#ff4444]\[X][/]" if self.completed else r"[#ffffff]\[ ][/]"
        streak_text = f" [#ff4444]·[/] {self.streak}" if self.streak > 0 else ""
        
        content_text = self.display_text
        if self.focused and not self.completed:
            content_text = f"[#ff4444][b]{content_text}[/b][/]"

        with Horizontal():
            yield Label(f"{prefix}{status} ", id="task-status", markup=True)
            yield Label(content_text + streak_text, id="task-content", markup=True)

    def set_highlighted(self, is_high: bool):
        self.is_highlighted = is_high
        self.watch_is_highlighted(is_high)

    def watch_is_highlighted(self, value: bool) -> None:
        prefix = "[#ff4444]>[/] " if value else "  "
        status = r"[#ff4444]\[X][/]" if self.completed else r"[#ffffff]\[ ][/]"
        try:
            self.query_one("#task-status", Label).update(f"{prefix}{status} ")
        except Exception:
            pass

class EndtimeApp(App):
    CSS_PATH = "endtime.tcss"
    
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("J", "move_down", "Move Down", show=False),
        Binding("K", "move_up", "Move Up", show=False),
        Binding("space", "toggle", "Toggle", show=False),
        Binding("f", "toggle_focus", "Focus", show=False),
        Binding("enter", "toggle", "Toggle", show=False),
        Binding("d", "delete_task", "Delete", show=False),
        Binding("e", "edit_task", "Edit", show=False),
        Binding("i", "insert_mode", "Insert", show=False),
        Binding("C", "sweep_cleared", "Sweep", show=False),
        Binding("H", "toggle_help", "Help", show=False),
        Binding("y", "confirm_yes", "Yes", show=False),
        Binding("n", "confirm_no", "No", show=False),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.tasks_data = []
        self.mode = "NORMAL"
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
        self.load_tasks()
        self.action_normal_mode() # Start in normal mode

    def update_header(self):
        header = self.query_one("#header", Label)
        total = len(self.tasks_data)
        completed_count = sum(1 for t in self.tasks_data if t.get("completed", False))
        
        mode_color = "#ff4444" if self.mode == "NORMAL" else "#ffffff"
        mode_display = self.mode
        if self.mode == "INSERT" and self.editing_id:
            mode_display = "EDIT"
            
        help_tag = r"\[H] hide" if self.show_help else r"\[H] help"
        line1 = f" [{mode_color}]{mode_display}[/] | {completed_count}/{total} | {help_tag}"
        
        if self.show_help:
            cmd_text = r"\[j/k]nav \[J/K]move \[spc]check \[f]focus \[i]add \[e]edit \[d]del \[C]clear"
            if self.mode == "INSERT":
                cmd_text = r"\[enter]submit \[esc]cancel"
            elif self.mode.startswith("CONFIRM"):
                cmd_text = r"\[y/enter]confirm \[n/esc]cancel"
            line2 = f"\n {cmd_text}"
        else:
            line2 = ""
        
        header.update(f"{line1}{line2}")

    def update_prompt(self, text: str):
        self.query_one("#prompt-label", Label).update(text)

    def load_tasks(self):
        if TASKS_FILE.exists():
            try:
                with open(TASKS_FILE, "r") as f:
                    self.tasks_data = json.load(f)
                    for t in self.tasks_data:
                        if "id" not in t:
                            t["id"] = str(uuid.uuid4())
            except Exception as e:
                pass
        self.refresh_list()

    def save_tasks(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TASKS_FILE, "w") as f:
            json.dump(self.tasks_data, f, indent=2)

    def process_habits(self):
        today_str = date.today().isoformat()
        changed = False
        for t in self.tasks_data:
            tag, _ = parse_task(t["text"])
            if tag == "DAILY":
                completed_dates = t.get("completed_dates", [])
                
                if today_str not in completed_dates and t.get("completed", False):
                    t["completed"] = False
                    changed = True

                streak = 0
                check_date = date.today()
                if today_str not in completed_dates:
                    check_date -= timedelta(days=1)
                
                while check_date.isoformat() in completed_dates:
                    streak += 1
                    check_date -= timedelta(days=1)
                
                t["streak"] = streak

        if changed:
            self.save_tasks()

    def refresh_list(self, keep_index=True):
        self.process_habits()
        task_list = self.query_one("#task-list", ListView)
        
        old_index = task_list.index

        task_list.clear()
        self.previous_highlighted = None
        
        pending = [t for t in self.tasks_data if not t.get("completed", False)]
        completed = [t for t in self.tasks_data if t.get("completed", False)]
        
        groups = {}
        for t in pending:
            tag, display_text = parse_task(t["text"])
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
            task_list.append(CategoryItem(tag))
            for t, display_text in groups[tag]:
                streak = t.get("streak", 0) if tag == "DAILY" else 0
                focused = t.get("focused", False)
                item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused)
                task_list.append(item)

        if completed:
            task_list.append(CategoryItem("CLEARED"))
            for t in completed:
                tag, display_text = parse_task(t["text"])
                streak = t.get("streak", 0) if tag == "DAILY" else 0
                focused = t.get("focused", False)
                item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused)
                item.add_class("-completed")
                task_list.append(item)
            
        if keep_index and old_index is not None and len(task_list.children) > 0:
            new_idx = min(old_index, len(task_list.children) - 1)
            
            if not isinstance(task_list.children[new_idx], TodoItem):
                found = False
                for i in range(new_idx, -1, -1):
                    if isinstance(task_list.children[i], TodoItem):
                        new_idx = i
                        found = True
                        break
                if not found:
                    for i in range(0, len(task_list.children)):
                        if isinstance(task_list.children[i], TodoItem):
                            new_idx = i
                            break
            task_list.index = new_idx
        elif len(task_list) > 0:
            for i, child in enumerate(task_list.children):
                if isinstance(child, TodoItem):
                    task_list.index = i
                    break

        self.update_header()

    def get_task_by_id(self, task_id):
        for t in self.tasks_data:
            if t["id"] == task_id:
                return t
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_toggle()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.previous_highlighted and isinstance(self.previous_highlighted, TodoItem):
            self.previous_highlighted.set_highlighted(False)
        if event.item and isinstance(event.item, TodoItem):
            event.item.set_highlighted(True)
        self.previous_highlighted = event.item

    def action_insert_mode(self):
        if self.mode != "NORMAL": return
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

    def _swap_tasks_in_group(self, task_id, direction):
        idx = -1
        for i, t in enumerate(self.tasks_data):
            if t["id"] == task_id:
                idx = i
                break
        
        if idx == -1: return False

        task = self.tasks_data[idx]
        task_tag, _ = parse_task(task["text"])
        is_completed = task.get("completed", False)

        target_idx = -1
        step = 1 if direction == 1 else -1
        curr = idx + step
        
        while 0 <= curr < len(self.tasks_data):
            other = self.tasks_data[curr]
            other_tag, _ = parse_task(other["text"])
            if other.get("completed", False) == is_completed and other_tag == task_tag:
                target_idx = curr
                break
            curr += step

        if target_idx != -1:
            self.tasks_data[idx], self.tasks_data[target_idx] = self.tasks_data[target_idx], self.tasks_data[idx]
            self.save_tasks()
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
                if isinstance(item, TodoItem):
                    task_data = self.get_task_by_id(item.task_id)
                    if task_data:
                        task_data["completed"] = not task_data["completed"]
                        tag, _ = parse_task(task_data["text"])
                        if tag == "DAILY":
                            today_str = date.today().isoformat()
                            completed_dates = task_data.get("completed_dates", [])
                            if task_data["completed"] and today_str not in completed_dates:
                                completed_dates.append(today_str)
                            elif not task_data["completed"] and today_str in completed_dates:
                                completed_dates.remove(today_str)
                            task_data["completed_dates"] = completed_dates
                            
                        self.save_tasks()
                        self.refresh_list(keep_index=True)
        elif self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP"):
            self.action_confirm_yes()

    def action_toggle_focus(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    task_data = self.get_task_by_id(item.task_id)
                    if task_data:
                        task_data["focused"] = not task_data.get("focused", False)
                        self.save_tasks()
                        self.refresh_list(keep_index=True)

    def action_delete_task(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    self.mode = "CONFIRM_DELETE"
                    self.pending_delete_id = item.task_id
                    self.update_prompt("[#ff4444]DELETE TASK? (y/n)[/]")
                    self.update_header()

    def action_sweep_cleared(self):
        if self.mode == "NORMAL":
            completed = [t for t in self.tasks_data if t.get("completed", False)]
            if not completed:
                return
            self.mode = "CONFIRM_SWEEP"
            self.update_prompt("[#ff4444]SWEEP ALL CLEARED TASKS? (y/n)[/]")
            self.update_header()

    def action_confirm_yes(self):
        if self.mode == "CONFIRM_DELETE" and self.pending_delete_id:
            self.tasks_data = [t for t in self.tasks_data if t["id"] != self.pending_delete_id]
            self.save_tasks()
            self.refresh_list(keep_index=True)
            self.action_normal_mode()
        elif self.mode == "CONFIRM_SWEEP":
            self.tasks_data = [t for t in self.tasks_data if not t.get("completed", False) or parse_task(t["text"])[0] == "DAILY"]
            self.save_tasks()
            self.refresh_list(keep_index=True)
            self.action_normal_mode()

    def action_confirm_no(self):
        if self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP"):
            self.action_normal_mode()

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
            self.save_tasks()
            self.refresh_list(keep_index=True)
        self.action_normal_mode()

if __name__ == "__main__":
    app = EndtimeApp()
    app.run()
