"""Main TUI application controller for Endtime."""
import os
import uuid
import shutil
import subprocess
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Label, ListView
from textual.containers import Horizontal

from endtime.models import parse_task
from endtime.storage import StorageManager
from endtime.habits import process_habits
from endtime.schedule import ScheduleManager, format_schedule_badge
from endtime.widgets import (
    CategoryItem,
    TodoItem,
    SessionPickerModal,
    SessionOverlayModal,
    ScheduleModal,
    ReminderModal,
    HelpModal,
)
from endtime.session import SessionManager, SessionType, SessionState


def format_progress_gauge(completed: int, total: int, width: int = 8) -> str:
    """Format a compact visual ASCII progress gauge."""
    if total == 0:
        return "[#333333][────────][/] 0%"
    ratio = max(0.0, min(1.0, completed / total))
    filled = int(round(ratio * width))
    empty = width - filled
    pct = int(round(ratio * 100))
    bar_fill = "█" * filled
    bar_empty = "░" * empty
    gauge_color = "#ffffff" if ratio == 1.0 else ("#ff4444" if ratio > 0 else "#333333")
    return f"[{gauge_color}][{bar_fill}[#333333]{bar_empty}[/]][/] {pct}%"


def copy_to_clipboard_system(app: App, text: str) -> None:
    """Copy text using Textual's OSC 52 and desktop clipboard tools (wl-copy, xclip, xsel)."""
    try:
        app.copy_to_clipboard(text)
    except Exception:
        pass

    if shutil.which("wl-copy") and os.environ.get("WAYLAND_DISPLAY"):
        try:
            res = subprocess.run(["wl-copy"], input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                return
        except Exception:
            pass

    if shutil.which("xclip"):
        try:
            res = subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                return
        except Exception:
            pass

    if shutil.which("xsel"):
        try:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass


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
        Binding("at", "schedule_task", "Schedule", show=False),
        Binding("@", "schedule_task", "Schedule", show=False),
        Binding("slash", "search_mode", "Search", show=False),
        Binding("/", "search_mode", "Search", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
        Binding("?", "toggle_help", "Help", show=False),
        Binding("enter", "toggle", "Toggle", show=False),
        Binding("d", "delete_task", "Delete", show=False),
        Binding("e", "edit_task", "Edit", show=False),
        Binding("i", "insert_mode", "Insert", show=False),
        Binding("c", "toggle_collapse", "Collapse", show=False),
        Binding("C", "sweep_cleared", "Sweep", show=False),
        Binding("H", "toggle_help", "Help", show=False),
        Binding("y", "yank", "Yank / Copy", show=False),
        Binding("n", "confirm_no", "No", show=False),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("r", "reset_task", "Reset", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.storage = StorageManager(self)
        self.session = SessionManager(self)
        self.scheduler = ScheduleManager(self)
        self.tasks_data: List[Dict[str, Any]] = []
        self.collapsed_tags = set()
        self.tag_order = []
        self.mode = "NORMAL"
        self.search_query = ""
        self.session_target_id = None
        self.schedule_target_id = None
        self.editing_id = None
        self.pending_delete_id = None
        self.pending_reset_id = None
        self.previous_highlighted = None
        self._toast_timer = None

    def on_key(self, event):
        if self.mode == "NORMAL":
            if event.character == "g":
                if getattr(self, "_pending_g", False):
                    self.action_go_top()
                    self._pending_g = False
                else:
                    self._pending_g = True
            else:
                self._pending_g = False
                if event.character == "G":
                    self.action_go_bottom()

    def action_go_top(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.children:
                task_list.index = 0

    def action_go_bottom(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.children:
                task_list.index = len(task_list.children) - 1

    def compose(self) -> ComposeResult:
        yield Label("", id="header", markup=True)
        yield ListView(id="task-list")
        with Horizontal(id="bottom-bar"):
            yield Label("[#ff4444]>[/] ", id="prompt-prefix", markup=True)
            yield Label("AWAITING TASK...", id="prompt-label", markup=True)
            yield Input(id="task-input")

    def on_mount(self) -> None:
        self.load_collapsed_tags()
        self.load_tag_order()
        self.tasks_data = self.storage.load_tasks()
        if process_habits(self.tasks_data):
            self.schedule_save(tasks=True)
        self.scheduler.start_ticker()
        self.action_normal_mode()

    def on_unmount(self) -> None:
        self.scheduler.stop_ticker()
        self.storage._flush_save(immediate=True)

    def update_header(self):
        try:
            header = self.query_one("#header", Label)
        except Exception:
            return

        total = len(self.tasks_data)
        completed_count = sum(1 for t in self.tasks_data if t.get("completed", False))

        mode_color = "#ff4444" if self.mode == "NORMAL" else "#ffffff"
        mode_display = self.mode
        if self.mode == "INSERT" and self.editing_id:
            mode_display = "EDIT"

        gauge = format_progress_gauge(completed_count, total)
        session_badge = self.session.get_header_badge() if hasattr(self, "session") else ""
        clock_str = datetime.now().strftime("%H:%M")

        header_text = (
            f" [#ff4444][b]ENDTIME[/b][/] [#333333]│[/] "
            f"[{mode_color}][b]{mode_display}[/b][/] [#333333]│[/] "
            f"{gauge} [#888888]({completed_count}/{total})[/] [#333333]│[/] "
            f"{session_badge}"
            f"[#666666]{clock_str}[/] [#333333]│[/] "
            r"[#555555]\[?] help[/]"
        )
        header.update(header_text)

    def update_prompt(self, text: str):
        try:
            lbl = self.query_one("#prompt-label", Label)
            lbl.display = True
            lbl.update(text)
            self.query_one("#task-input", Input).display = False
        except Exception:
            pass

    def show_toast(self, message: str, duration: float = 2.5) -> None:
        """Display a transient HUD notification banner in the prompt bar."""
        if self._toast_timer is not None:
            try:
                self._toast_timer.stop()
            except Exception:
                pass
            self._toast_timer = None

        self.update_prompt(message)
        self._toast_timer = self.set_timer(duration, self._clear_toast)

    def _clear_toast(self) -> None:
        self._toast_timer = None
        if self.mode == "NORMAL":
            self.update_prompt("AWAITING TASK...")

    def load_tasks(self):
        self.tasks_data = self.storage.load_tasks()
        if process_habits(self.tasks_data):
            self.schedule_save(tasks=True)
        self.refresh_list()

    def save_tasks(self):
        self.storage.save_tasks_sync(self.tasks_data)

    def load_collapsed_tags(self):
        self.collapsed_tags = self.storage.load_collapsed_tags()

    def load_tag_order(self):
        self.tag_order = self.storage.load_tag_order()

    def save_collapsed_tags(self):
        self.storage.save_collapsed_tags_sync(self.collapsed_tags, self.tag_order)

    def schedule_save(self, tasks: bool = False, config: bool = False):
        self.storage.schedule_save(tasks=tasks, config=config)

    def _get_task_list(self) -> Optional[ListView]:
        try:
            return self.query_one("#task-list", ListView)
        except Exception:
            pass
        for screen in reversed(getattr(self, "_screen_stack", [])):
            try:
                return screen.query_one("#task-list", ListView)
            except Exception:
                continue
        return None

    def refresh_list(self, keep_index=True):
        task_list = self._get_task_list()
        if task_list is None:
            return
        old_index = task_list.index

        self.previous_highlighted = None

        pending = [t for t in self.tasks_data if not t.get("completed", False)]
        completed = [t for t in self.tasks_data if t.get("completed", False)]
        completed.sort(
            key=lambda t: (parse_task(t["text"], t)[0] == "DAILY", t.get("completed_at", "")),
            reverse=True,
        )

        # Filter by search query if in search mode
        if self.search_query:
            pending = [t for t in pending if self.search_query in t.get("text", "").lower()]
            completed = [t for t in completed if self.search_query in t.get("text", "").lower()]

        groups = {}
        for t in pending:
            tag, display_text = parse_task(t["text"], t)
            if tag not in groups:
                groups[tag] = []
            groups[tag].append((t, display_text))

        present_tags = set(groups.keys())
        if not self.tag_order:
            default_tags = sorted(groups.keys())
            if "GENERAL" in default_tags:
                default_tags.remove("GENERAL")
                default_tags.insert(0, "GENERAL")
            if "DAILY" in default_tags:
                default_tags.remove("DAILY")
                default_tags.insert(0, "DAILY")
            self.tag_order = default_tags

        ordered = [t for t in self.tag_order if t in present_tags]
        for t in sorted(groups.keys()):
            if t not in ordered:
                ordered.append(t)
                if t not in self.tag_order:
                    self.tag_order.append(t)
        sorted_tags = ordered

        items_to_add = []

        for tag in sorted_tags:
            is_col = (tag in self.collapsed_tags)
            group_pending = groups[tag]
            count = len(group_pending)
            completed_in_tag = sum(
                1 for t in self.tasks_data
                if t.get("completed", False) and parse_task(t["text"], t)[0] == tag
            )
            total_in_tag = count + completed_in_tag
            items_to_add.append(CategoryItem(tag, collapsed=is_col, count=total_in_tag, completed_count=completed_in_tag))

            if not is_col:
                for t, display_text in group_pending:
                    streak = t.get("streak", 0) if tag == "DAILY" else 0
                    focused = t.get("focused", False)
                    session_badge = (
                        self.session.get_badge_text()
                        if getattr(self, "session", None) and self.session.active_task_id == t["id"]
                        else self.session.get_saved_badge_text(t) if getattr(self, "session", None) else ""
                    )
                    sched_badge = self.scheduler.get_schedule_badge(t) if getattr(self, "scheduler", None) else ""
                    time_spent = t.get("time_spent_seconds", 0)
                    items_to_add.append(
                        TodoItem(
                            t["id"],
                            t["text"],
                            display_text,
                            t["completed"],
                            streak,
                            focused,
                            session_badge=session_badge,
                            schedule_badge=sched_badge,
                            time_spent_seconds=time_spent,
                        )
                    )

        if completed:
            is_col = ("CLEARED" in self.collapsed_tags)
            count = len(completed)
            items_to_add.append(CategoryItem("CLEARED", collapsed=is_col, count=count, completed_count=count))
            if not is_col:
                for t in completed:
                    tag, display_text = parse_task(t["text"], t)
                    streak = t.get("streak", 0) if tag == "DAILY" else 0
                    focused = t.get("focused", False)
                    session_badge = (
                        self.session.get_badge_text()
                        if getattr(self, "session", None) and self.session.active_task_id == t["id"]
                        else self.session.get_saved_badge_text(t) if getattr(self, "session", None) else ""
                    )
                    sched_badge = self.scheduler.get_schedule_badge(t) if getattr(self, "scheduler", None) else ""
                    time_spent = t.get("time_spent_seconds", 0)
                    item = TodoItem(
                        t["id"],
                        t["text"],
                        display_text,
                        t["completed"],
                        streak,
                        focused,
                        session_badge=session_badge,
                        schedule_badge=sched_badge,
                        time_spent_seconds=time_spent,
                    )
                    item.add_class("-completed")
                    items_to_add.append(item)

        task_list.clear()
        if items_to_add:
            task_list.extend(items_to_add)

        if keep_index and old_index is not None and len(items_to_add) > 0:
            new_idx = min(old_index, len(items_to_add) - 1)
            task_list.index = new_idx
        elif len(items_to_add) > 0:
            task_list.index = 0

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
        input_box.placeholder = "[TAG] Task text @schedule"
        input_box.display = True
        input_box.value = ""
        input_box.focus()

    def action_search_mode(self):
        if self.mode != "NORMAL":
            return
        self.mode = "SEARCH"
        self.search_query = ""
        self.update_header()

        self.query_one("#prompt-label", Label).display = False
        input_box = self.query_one("#task-input", Input)
        input_box.placeholder = "search tasks..."
        input_box.display = True
        input_box.value = ""
        input_box.focus()

    def action_normal_mode(self):
        self.mode = "NORMAL"
        self.search_query = ""
        self.editing_id = None
        self.pending_delete_id = None
        self.session_target_id = None
        self.schedule_target_id = None
        self.update_header()

        try:
            self.query_one("#task-input", Input).display = False
            lbl = self.query_one("#prompt-label", Label)
            lbl.display = True
            lbl.update("AWAITING TASK...")
        except Exception:
            pass

        self.refresh_list(keep_index=True)
        try:
            self.query_one("#task-list", ListView).focus()
        except Exception:
            pass

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

    def _swap_tags(self, tag: str, direction: int) -> bool:
        if tag == "CLEARED":
            return False
        task_list = self._get_task_list()
        if task_list is None:
            return False

        active_tags = [child.tag for child in task_list.children if isinstance(child, CategoryItem) and child.tag != "CLEARED"]
        if tag not in active_tags:
            return False

        idx = active_tags.index(tag)
        target_idx = idx + (1 if direction == 1 else -1)
        if 0 <= target_idx < len(active_tags):
            other_tag = active_tags[target_idx]
            if tag in self.tag_order and other_tag in self.tag_order:
                pos1, pos2 = self.tag_order.index(tag), self.tag_order.index(other_tag)
                self.tag_order[pos1], self.tag_order[pos2] = self.tag_order[pos2], self.tag_order[pos1]
            self.schedule_save(config=True)
            return True
        return False

    def action_move_up(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, CategoryItem):
                    if self._swap_tags(item.tag, -1):
                        self.refresh_list(keep_index=False)
                        for i, child in enumerate(task_list.children):
                            if isinstance(child, CategoryItem) and child.tag == item.tag:
                                task_list.index = i
                                break
                elif isinstance(item, TodoItem):
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
                if isinstance(item, CategoryItem):
                    if self._swap_tags(item.tag, 1):
                        self.refresh_list(keep_index=False)
                        for i, child in enumerate(task_list.children):
                            if isinstance(child, CategoryItem) and child.tag == item.tag:
                                task_list.index = i
                                break
                elif isinstance(item, TodoItem):
                    if self._swap_tasks_in_group(item.task_id, 1):
                        self.refresh_list(keep_index=False)
                        for i, child in enumerate(task_list.children):
                            if getattr(child, "task_id", None) == item.task_id:
                                task_list.index = i
                                break

    def action_toggle_help(self):
        if self.mode == "NORMAL":
            self.push_screen(HelpModal())

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
        elif self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP", "CONFIRM_RESET"):
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

    def action_reset_task(self):
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                if isinstance(item, TodoItem):
                    self.mode = "CONFIRM_RESET"
                    self.pending_reset_id = item.task_id
                    self.update_prompt("[#ff4444]RESET TIMER? (y/n)[/]")
                    self.update_header()

    def action_sweep_cleared(self):
        if self.mode == "NORMAL":
            completed = [t for t in self.tasks_data if t.get("completed", False)]
            if not completed:
                return
            self.mode = "CONFIRM_SWEEP"
            self.update_prompt(f"[#ff4444]SWEEP ALL {len(completed)} CLEARED TASKS? (y/n)[/]")
            self.update_header()

    def action_confirm_yes(self):
        if self.mode == "CONFIRM_DELETE" and self.pending_delete_id:
            self.tasks_data = [t for t in self.tasks_data if t["id"] != self.pending_delete_id]
            self.save_tasks()
            self.refresh_list(keep_index=True)
            self.show_toast("[#ff4444]✓ TASK DELETED[/]")
            self.action_normal_mode()
        elif self.mode == "CONFIRM_SWEEP":
            count = sum(1 for t in self.tasks_data if t.get("completed", False) and parse_task(t["text"], t)[0] != "DAILY")
            self.tasks_data = [
                t for t in self.tasks_data
                if not t.get("completed", False) or parse_task(t["text"], t)[0] == "DAILY"
            ]
            self.save_tasks()
            self.refresh_list(keep_index=True)
            self.show_toast(f"[#ffffff]✓ SWEPT {count} COMPLETED TASKS[/]")
            self.action_normal_mode()
        elif self.mode == "CONFIRM_RESET" and self.pending_reset_id:
            for t in self.tasks_data:
                if t["id"] == self.pending_reset_id:
                    t["time_spent_seconds"] = 0
                    break
            self.save_tasks()
            self.refresh_list(keep_index=True)
            self.show_toast("[#ffffff]✓ TIMER RESET TO 0s[/]")
            self.action_normal_mode()

    def action_yank(self):
        if self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP", "CONFIRM_RESET"):
            self.action_confirm_yes()
            return
        if self.mode == "NORMAL":
            task_list = self.query_one("#task-list", ListView)
            if task_list.index is not None and task_list.children:
                item = task_list.children[task_list.index]
                text_to_copy = ""
                msg = ""
                if isinstance(item, TodoItem):
                    task_data = self.get_task_by_id(item.task_id)
                    if task_data:
                        text_to_copy = task_data["text"]
                        msg = "[#ffffff]✓ COPIED TASK TO CLIPBOARD[/]"
                elif isinstance(item, CategoryItem):
                    tag_name = item.tag
                    if tag_name == "CLEARED":
                        matching = [t["text"] for t in self.tasks_data if t.get("completed", False)]
                    else:
                        matching = [
                            t["text"] for t in self.tasks_data
                            if not t.get("completed", False) and parse_task(t["text"], t)[0] == tag_name
                        ]
                    if matching:
                        text_to_copy = "\n".join(matching)
                        count_label = f"{len(matching)} TASK{'S' if len(matching)>1 else ''}"
                        msg = f"[#ffffff]✓ COPIED {count_label} ({tag_name}) TO CLIPBOARD[/]"
                    else:
                        msg = f"[#888888]NO TASKS IN {tag_name} TO COPY[/]"

                if text_to_copy:
                    copy_to_clipboard_system(self, text_to_copy)
                if msg:
                    self.show_toast(msg)

    def action_confirm_no(self):
        if self.mode in ("CONFIRM_DELETE", "CONFIRM_SWEEP", "CONFIRM_RESET"):
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

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.mode == "SEARCH":
            self.search_query = event.value.strip().lower()
            self.refresh_list(keep_index=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.mode == "SEARCH":
            self.action_normal_mode()
            return

        text = event.value.strip()
        if text:
            if self.editing_id:
                task_data = self.get_task_by_id(self.editing_id)
                if task_data:
                    clean_text = self.scheduler.extract_and_apply_schedule(task_data, text)
                    task_data["text"] = clean_text
            else:
                new_task = {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "completed": False,
                }
                clean_text = self.scheduler.extract_and_apply_schedule(new_task, text)
                new_task["text"] = clean_text
                self.tasks_data.insert(0, new_task)
            self.schedule_save(tasks=True)
            self.refresh_list(keep_index=True)
        self.action_normal_mode()

    def action_schedule_task(self):
        if self.mode != "NORMAL":
            return
        task_list = self.query_one("#task-list", ListView)
        if task_list.index is not None and task_list.children:
            item = task_list.children[task_list.index]
            if isinstance(item, TodoItem):
                self.schedule_target_id = item.task_id
                task_dict = self.get_task_by_id(item.task_id)
                has_schedule = bool(task_dict and task_dict.get("schedule"))
                _, task_display = parse_task(item.original_text, task_dict)
                self.push_screen(
                    ScheduleModal(task_display, is_scheduled=has_schedule),
                    callback=self._on_schedule_result,
                )

    def _on_schedule_result(self, result) -> None:
        if not self.schedule_target_id:
            return

        if result == "CLEAR":
            self.scheduler.clear_schedule(self.schedule_target_id)
            self.show_toast("[#ff4444]✓ SCHEDULE CLEARED[/]")
        elif isinstance(result, datetime):
            self.scheduler.set_schedule(self.schedule_target_id, result)
            badge = format_schedule_badge(result)
            self.show_toast(f"[#ffffff]✓ SCHEDULED: {badge}[/]")

        self.schedule_target_id = None

    def action_work_session(self):
        if self.mode != "NORMAL":
            return
        task_list = self.query_one("#task-list", ListView)
        if task_list.index is not None and task_list.children:
            item = task_list.children[task_list.index]
            if isinstance(item, TodoItem):
                if getattr(item, "completed", False):
                    return
                if self.session.state != SessionState.IDLE and self.session.active_task_id == item.task_id:
                    self.push_screen(SessionOverlayModal(item.display_text, self.session.get_overlay_title()))
                else:
                    self.session_target_id = item.task_id
                    task_dict = self.get_task_by_id(item.task_id)
                    saved = task_dict.get("saved_session") if task_dict else None
                    _, task_display = parse_task(item.original_text, task_dict)
                    self.push_screen(SessionPickerModal(task_display, saved_session=saved), callback=self._on_picker_result)

    def _on_picker_result(self, result: Optional[str]) -> None:
        if not result or not self.session_target_id:
            self.session_target_id = None
            return

        task_dict = self.get_task_by_id(self.session_target_id)
        if not task_dict:
            self.session_target_id = None
            return

        _, task_display = parse_task(task_dict["text"], task_dict)

        if result == "continue":
            self.session.start_session(self.session_target_id, SessionType.POMODORO, resume=True)
            self.push_screen(SessionOverlayModal(task_display, self.session.get_overlay_title()))
        elif result == "discard":
            self.session.clear_saved_session(self.session_target_id)
            self.refresh_list(keep_index=True)
            self.show_toast("[#ff4444]✓ SAVED SESSION DISCARDED[/]")
        elif result == "pomodoro":
            self.session.start_session(self.session_target_id, SessionType.POMODORO, duration=25 * 60)
            self.push_screen(SessionOverlayModal(task_display, "P O M O D O R O"))
        elif result == "short_break":
            self.session.start_session(self.session_target_id, SessionType.BREAK, duration=5 * 60)
            self.push_screen(SessionOverlayModal(task_display, "S H O R T   B R E A K"))
        elif result == "long_break":
            self.session.start_session(self.session_target_id, SessionType.LONG_BREAK, duration=15 * 60)
            self.push_screen(SessionOverlayModal(task_display, "L O N G   B R E A K"))
        elif result == "stopwatch":
            self.session.start_session(self.session_target_id, SessionType.STOPWATCH, duration=0)
            self.push_screen(SessionOverlayModal(task_display, "S T O P W A T C H"))

        self.session_target_id = None


def main():
    """Run the Endtime TUI application."""
    app = EndtimeApp()
    app.run()


if __name__ == "__main__":
    main()
