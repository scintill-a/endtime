"""Todo task item widget for Endtime list view."""
from textual.app import ComposeResult
from textual.widgets import Label, ListItem
from endtime.models import format_accumulated_time


class TodoItem(ListItem):
    """Represents an individual task item with split status and content labels."""

    def __init__(
        self,
        task_id: str,
        original_text: str,
        display_text: str,
        completed: bool = False,
        streak: int = 0,
        focused: bool = False,
        session_badge: str = "",
        time_spent_seconds: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.task_id = task_id
        self.original_text = original_text
        self.display_text = display_text
        self.completed = completed
        self.streak = streak
        self.focused = focused
        self.session_badge = session_badge
        self.time_spent_seconds = time_spent_seconds
        self.is_highlighted = False
        self._status_label = None
        self._content_label = None

    def _get_status_text(self, is_high: bool) -> str:
        prefix = "[#ff4444]>[/] " if is_high else "  "
        status = r"[#ff4444]\[X][/]" if self.completed else r"[#ffffff]\[ ][/]"
        return f"{prefix}{status} "

    def _get_content_text(self) -> str:
        streak_text = f" [#ff4444]·[/] {self.streak}" if self.streak > 0 else ""
        content_text = self.display_text
        if self.focused and not self.completed:
            content_text = f"[#ff4444][b]{content_text}[/b][/]"
            
        badge_text = f" [#ff4444][b]{self.session_badge}[/b][/]" if self.session_badge else ""
        time_text = (
            f" [#888888]({format_accumulated_time(self.time_spent_seconds)})[/]"
            if not self.session_badge and self.time_spent_seconds > 0
            else ""
        )
        return f"{content_text}{streak_text}{badge_text}{time_text}"

    def compose(self) -> ComposeResult:
        self._status_label = Label(
            self._get_status_text(self.is_highlighted),
            classes="todo-status",
            markup=True,
        )
        self._content_label = Label(
            self._get_content_text(),
            classes="todo-content",
            markup=True,
        )
        yield self._status_label
        yield self._content_label

    def set_highlighted(self, is_high: bool):
        """Update highlighted state and re-render status label in place."""
        if self.is_highlighted != is_high:
            self.is_highlighted = is_high
            if self._status_label is not None:
                self._status_label.update(self._get_status_text(is_high))

    def update_data_and_refresh(
        self,
        completed: bool = None,
        focused: bool = None,
        streak: int = None,
        display_text: str = None,
        original_text: str = None,
        session_badge: str = None,
        time_spent_seconds: int = None,
    ):
        """Update task properties in place and refresh DOM labels without rebuilding."""
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
        if session_badge is not None:
            self.session_badge = session_badge
        if time_spent_seconds is not None:
            self.time_spent_seconds = time_spent_seconds
            
        if self._status_label is not None:
            self._status_label.update(self._get_status_text(self.is_highlighted))
        if self._content_label is not None:
            self._content_label.update(self._get_content_text())
