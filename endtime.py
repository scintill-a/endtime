import json
import uuid
import re
import functools
from pathlib import Path
from datetime import date, datetime, timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Label, ListView, ListItem
from textual.containers import Horizontal

TASKS_DIR = Path.home() / ".config" / "endtime"
TASKS_FILE = TASKS_DIR / "tasks.json"
CONFIG_FILE = TASKS_DIR / "config.json"

TAG_REGEX = re.compile(r'^\[([A-Z0-9_\-\s]+)\]\s*(.*)', re.IGNORECASE)

def parse_task(text, task_data=None):
    if task_data is not None and task_data.get("_cached_text") == text:
        return task_data["_tag"], task_data["_display"]
    match = TAG_REGEX.match(text)
    if match:
        tag, display = match.group(1).strip().upper(), match.group(2)
    else:
        tag, display = "GENERAL", text
    if task_data is not None and isinstance(task_data, dict):
        task_data["_cached_text"] = text
        task_data["_tag"] = tag
        task_data["_display"] = display
    return tag, display

class CategoryItem(ListItem):
    def __init__(self, text: str, collapsed: bool = False, count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.collapsed = collapsed
        self.count = count
        self.disabled = False
        self.is_highlighted = False
        self._label = None
        
    def _format_text(self, is_high: bool) -> str:
        icon = "[+]" if self.collapsed else "[-]"
        prefix = "[#ff4444]>[/] " if is_high else "  "
        count_text = f" ({self.count})" if self.collapsed and self.count > 0 else ""
        return f"{prefix}{icon} --- {self.text} ---{count_text}"

    def compose(self) -> ComposeResult:
        self._label = Label(self._format_text(self.is_highlighted), classes="category-label", markup=True)
        yield self._label

    def set_highlighted(self, is_high: bool):
        if self.is_highlighted != is_high:
            self.is_highlighted = is_high
            if self._label is not None:
                self._label.update(self._format_text(is_high))

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
        self._label = None

    def _format_text(self, is_high: bool) -> str:
        prefix = "[#ff4444]>[/] " if is_high else "  "
        status = r"[#ff4444]\[X][/]" if self.completed else r"[#ffffff]\[ ][/]"
        streak_text = f" [#ff4444]·[/] {self.streak}" if self.streak > 0 else ""
        
        content_text = self.display_text
        if self.focused and not self.completed:
            content_text = f"[#ff4444][b]{content_text}[/b][/]"
        
        return f"{prefix}{status} {content_text}{streak_text}"

    def compose(self) -> ComposeResult:
        self._label = Label(self._format_text(self.is_highlighted), classes="todo-label", markup=True)
        yield self._label

    def set_highlighted(self, is_high: bool):
        if self.is_highlighted != is_high:
            self.is_highlighted = is_high
            if self._label is not None:
                self._label.update(self._format_text(is_high))

    def update_data_and_refresh(self, completed: bool = None, focused: bool = None, streak: int = None, display_text: str = None, original_text: str = None):
        if completed is not None:
            self.completed = completed
            if self.completed and "-completed" not in self.classes:
                self.add_class("-completed")
            elif not self.completed and "-completed" in self.classes:
                self.remove_class("-completed")
        if focused is not None:
            self.focused = focused
        if streak is not None:
            self.streak = streak
        if display_text is not None:
            self.display_text = display_text
        if original_text is not None:
            self.original_text = original_text
        if self._label is not None:
            self._label.update(self._format_text(self.is_highlighted))

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
        self.tasks_data = []
        self.collapsed_tags = set()
        self.mode = "NORMAL"
        self.editing_id = None
        self.pending_delete_id = None
        self.previous_highlighted = None
        self.show_help = False
        self._save_timer = None
        self._dirty_tasks = False
        self._dirty_config = False

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
            cmd_text = r"\[j/k]nav \[J/K]move \[spc]check \[f]focus \[c]collapse \[i]add \[e]edit \[d]del \[C]clear"
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
        self.process_habits()
        self.refresh_list()

    def save_tasks(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TASKS_FILE, "w") as f:
            json.dump(self.tasks_data, f, indent=2)

    def load_collapsed_tags(self):
        self.collapsed_tags = set()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.collapsed_tags = set(data.get("collapsed_tags", []))
            except Exception:
                pass

    def save_collapsed_tags(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            config_data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
            config_data["collapsed_tags"] = list(self.collapsed_tags)
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

    def schedule_save(self, tasks: bool = False, config: bool = False):
        if tasks:
            self._dirty_tasks = True
        if config:
            self._dirty_config = True
        if self._save_timer is not None:
            try:
                self._save_timer.stop()
            except Exception:
                pass
        self._save_timer = self.set_timer(0.3, self._flush_save)

    def _flush_save(self, immediate: bool = False):
        if self._save_timer is not None:
            try:
                self._save_timer.stop()
            except Exception:
                pass
            self._save_timer = None
            
        save_t = self._dirty_tasks
        save_c = self._dirty_config
        self._dirty_tasks = False
        self._dirty_config = False

        if save_t:
            if immediate:
                self.save_tasks()
            else:
                self.run_worker(functools.partial(self._async_save_tasks, list(self.tasks_data)), thread=True)
        if save_c:
            if immediate:
                self.save_collapsed_tags()
            else:
                self.run_worker(functools.partial(self._async_save_config, list(self.collapsed_tags)), thread=True)

    def _async_save_tasks(self, data_copy):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(TASKS_FILE, "w") as f:
                json.dump(data_copy, f, indent=2)
        except Exception:
            pass

    def _async_save_config(self, tags_copy):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            config_data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
            config_data["collapsed_tags"] = tags_copy
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

    def on_unmount(self) -> None:
        self._flush_save(immediate=True)

    def process_habits(self):
        today_str = date.today().isoformat()
        changed = False
        for t in self.tasks_data:
            tag, _ = parse_task(t["text"], t)
            if tag == "DAILY":
                completed_dates = t.get("completed_dates", [])
                
                if today_str not in completed_dates and t.get("completed", False):
                    t["completed"] = False
                    if "completed_at" in t:
                        del t["completed_at"]
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
            self.schedule_save(tasks=True)

    def refresh_list(self, keep_index=True):
        task_list = self.query_one("#task-list", ListView)
        
        old_index = task_list.index

        task_list.clear()
        self.previous_highlighted = None
        
        pending = [t for t in self.tasks_data if not t.get("completed", False)]
        completed = [t for t in self.tasks_data if t.get("completed", False)]
        completed.sort(key=lambda t: (parse_task(t["text"], t)[0] == "DAILY", t.get("completed_at", "")), reverse=True)
        
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
                    item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused)
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
                    item = TodoItem(t["id"], t["text"], display_text, t["completed"], streak, focused)
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

    def get_task_by_id(self, task_id):
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
            self.tasks_data = [t for t in self.tasks_data if not t.get("completed", False) or parse_task(t["text"], t)[0] == "DAILY"]
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
            self.schedule_save(tasks=True)
            self.refresh_list(keep_index=True)
        self.action_normal_mode()

if __name__ == "__main__":
    app = EndtimeApp()
    app.run()
