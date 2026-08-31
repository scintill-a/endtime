"""Category tag item widget for Endtime list view."""
from textual.app import ComposeResult
from textual.widgets import Label, ListItem


class CategoryItem(ListItem):
    """Represents a collapsible category header in the task list."""

    def __init__(
        self,
        text: str,
        collapsed: bool = False,
        count: int = 0,
        completed_count: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.text = text
        self.collapsed = collapsed
        self.count = count
        self.completed_count = completed_count
        self.disabled = False
        self.is_highlighted = False
        self._label = None

    @property
    def tag(self) -> str:
        return self.text

    def _format_text(self, is_high: bool) -> str:
        icon = "▸" if self.collapsed else "▾"
        prefix = "[#ff4444]>[/] " if is_high else "  "

        tag_color = "#ff4444" if self.text in ("DAILY", "GENERAL") else ("#666666" if self.text == "CLEARED" else "#ffffff")
        tag_display = f"[{tag_color}][b]{icon} [{self.text}][/b][/]"

        if self.text == "CLEARED":
            stats_text = f" [#444444]({self.count} cleared)[/]" if self.count > 0 else ""
        else:
            if self.count > 0:
                stats_text = f" [#888888]{self.completed_count}/{self.count}[/]"
                if self.count > 0 and self.completed_count > 0:
                    pct = int(round((self.completed_count / self.count) * 100))
                    stats_text += f" [#555555][{pct}%][/]"
            else:
                stats_text = ""

        divider_color = "#333333" if not is_high else "#555555"
        return f"{prefix}{tag_display}{stats_text} [{divider_color}]" + "─" * 20 + "[/]"

    def compose(self) -> ComposeResult:
        self._label = Label(self._format_text(self.is_highlighted), classes="category-label", markup=True)
        yield self._label

    def set_highlighted(self, is_high: bool):
        """Update highlighted state and re-render label in place."""
        if self.is_highlighted != is_high:
            self.is_highlighted = is_high
            if self._label is not None:
                self._label.update(self._format_text(is_high))
