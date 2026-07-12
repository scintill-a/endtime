from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static

class HelpModal(ModalScreen[None]):
    """Fullscreen minimal modal overlay to display all keybindings."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }

    #help-card {
        width: 44;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #333333;
        background: #080808;
    }

    .help-title {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .help-row {
        width: 100%;
        layout: horizontal;
    }

    .help-key {
        color: #ffffff;
        text-style: bold;
        width: 12;
        text-align: right;
        margin-right: 2;
    }

    .help-desc {
        color: #aaaaaa;
        width: 1fr;
        text-align: left;
    }

    .help-hint {
        color: #555555;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="help-card"):
            yield Label("HELP & KEYBINDS", classes="help-title")
            
            bindings = [
                ("j/k", "Navigate"),
                ("J/K", "Move Task"),
                ("spc", "Check/Uncheck"),
                ("i", "Add Task"),
                ("e", "Edit Task"),
                ("d", "Delete Task"),
                ("r", "Reset Timer"),
                ("c", "Collapse Tag"),
                ("f", "Focus Session"),
                ("w", "Work Session"),
                ("C", "Clear Completed"),
                ("gg / G", "Top / Bottom"),
            ]
            
            for key, desc in bindings:
                with Static(classes="help-row"):
                    yield Label(f"\\[{key}]", classes="help-key")
                    yield Label(desc, classes="help-desc")
                    
            yield Label("\\[H/esc/q] close", classes="help-hint")

    def on_key(self, event) -> None:
        if event.character in ("H", "h", "q") or event.key == "escape":
            self.dismiss()
            event.prevent_default()
