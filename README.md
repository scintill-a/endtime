# Endtime (Todo TUI)

A minimalist, keyboard-driven Task Manager for the terminal, designed with a strict "NASA Telemetry / Hacker" aesthetic. Built with Python and [Textual](https://textual.textualize.io/).

## Features
- **Vim-like Keybindings**: Seamlessly navigate your tasks without touching the mouse (`j`/`k` to navigate, `i` to insert, `e` to edit, `d` to delete).
- **Dynamic Tagging System**: Prefix tasks with `[TAG]` (e.g. `[WORK] reply to emails`) and Endtime will automatically group and categorize them for you.
- **Ultra-Minimal Aesthetic**: Strict terminal gray and stark `#ff4444` red highlights. No bloated borders, no unnecessary UI elements.
- **Toggleable Guide**: Press `Shift+H` to seamlessly drop down a command telemetry guide.
- **Smart Text Wrapping**: Handles infinitely long tasks gracefully without destroying your layout.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/endtime.git
   cd endtime
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Usage

Start the HUD:
```bash
python3 endtime.py
```

### System Alias (Optional)
To launch Endtime instantly from anywhere in your terminal just by typing `endtime`, add the following bash function to your `~/.bashrc` or `~/.zshrc`:

```bash
endtime() {
    # Replace /path/to/endtime with the actual path to your cloned repository
    (cd /path/to/endtime && ./venv/bin/python3 endtime.py)
}
```
After adding it, restart your terminal or run `source ~/.bashrc` (or `~/.zshrc`), and you can now pull up the HUD instantly by typing `endtime`!

### Controls (Normal Mode)
- `j` / `k`: Navigate tasks
- `Space`: Check/Uncheck task
- `i`: Insert new task
- `e`: Edit selected task
- `d`: Delete selected task
- `Shift+C`: Sweep all completed tasks
- `Shift+H`: Toggle command guide
- `q`: Quit application

*Data is automatically saved to `~/.config/nasa-todo/tasks.json`.*

## License
MIT
