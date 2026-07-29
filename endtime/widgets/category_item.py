"""Category tag item widget for Endtime list view."""
from textual.app import ComposeResult
from textual.widgets import Label, ListItem


class CategoryItem(ListItem):
    """Represents a collapsible category header in the task list."""

    def __init__(self, text: str, collapsed: bool = False, count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.collapsed = collapsed
        self.count = count
        self.disabled = False
        self.is_highlighted = False
        self._label = None

    @property
    def tag(self) -> str:
        return self.text

    def _format_text(self, is_high: bool) -> str:
        icon = "[+]" if self.collapsed else "[-]"
        prefix = "[#ff4444]>[/]" if is_high else ""
        count_text = f" ({self.count})" if self.collapsed and self.count > 0 else ""
        return f"{prefix}{icon} --- {self.text} ---{count_text}"

    def compose(self) -> ComposeResult:
        self._label = Label(self._format_text(self.is_highlighted), classes="category-label", markup=True)
        yield self._label

    def set_highlighted(self, is_high: bool):
        """Update highlighted state and re-render label in place."""
        if self.is_highlighted != is_high:
            self.is_highlighted = is_high
            if self._label is not None:
                self._label.update(self._format_text(is_high))
