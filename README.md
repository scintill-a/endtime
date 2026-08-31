# endtime (Todo TUI)

A minimalist, keyboard-driven Task Manager and Productivity HUD for the terminal. Built with Python and [Textual](https://textual.textualize.io/).

## Features

- **Persistent Focus Sessions & Continue**: Start Pomodoro (25m), Short Breaks (5m), Long Breaks (15m), or Stopwatches attached to tasks. Pausing or exiting persists a snapshot, allowing you to seamlessly **continue where you left off** with remaining time and cycle counters intact.
- **Scheduled Tasks & Reminders**: Schedule tasks inline using natural syntax (e.g. `[WORK] Submit budget @14:30`, `@tomorrow 09:00`, `@in 15m`) or via the interactive schedule picker modal (`@`). Includes audio bells, floating in-app reminder alerts with 1-key snooze (`10m`, `30m`, `1h`) / start work actions, and desktop notifications.
- **Real-Time Live Search (`/`)**: Filter and jump through tasks dynamically as you type.
- **Daily Habit Tracker**: Prefix tasks with `[DAILY]` to create auto-resetting habits with streak counters (`🔥`).
- **Telemetry HUD Header**: Live mode indicator, visual progress gauge (`[████░░░░] 50%`), active timer pulse (`● [POMODORO 14:20]`), and system clock.
- **Dynamic Tagging System**: Prefix tasks with `[TAG]` (e.g. `[WORK] reply to emails`) for automatic collapsible grouping and category reordering (`Shift+J`/`Shift+K`).
- **Cyberpunk Dark Aesthetic**: Pure pitch-black terminal background with `#ff4444` crimson red highlights, high-contrast cursor bars, and clean ASCII gauges.
- **Command Cheatsheet (`?` / `Shift+H`)**: Categorized keybindings guide.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/scintill-a/endtime.git
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

### System Alias 
To launch Endtime instantly from anywhere in your terminal just by typing `endtime`, add the following bash function to your `~/.bashrc` or `~/.zshrc`:

```bash
endtime() {
    # Replace /path/to/endtime with the actual path to your cloned repository
    (cd /path/to/endtime && ./venv/bin/python3 endtime.py)
}
```
After adding it, restart your terminal or run `source ~/.bashrc` (or `~/.zshrc`), and you can now pull up the HUD instantly by typing `endtime`!

### Controls (Normal Mode)

| Key | Action |
| --- | --- |
| `j` / `k` | Navigate tasks down / up |
| `Shift+J` / `Shift+K` | Move task down/up within its tag or move active tag |
| `gg` / `G` | Jump to top / jump to bottom |
| `Space` / `Enter` | Check / Uncheck task |
| `w` | Open Work Session (Continue saved session, Pomodoro, Break, Stopwatch) |
| `@` | Schedule task / set reminder popup |
| `/` | Search and filter tasks in real-time |
| `f` | Toggle task focus (importance) |
| `i` | Insert new task (`[TAG] text @schedule`) |
| `e` | Edit selected task |
| `d` | Delete selected task |
| `y` | Yank / Copy task or category to clipboard |
| `c` | Toggle collapse / expand active category |
| `Shift+C` | Sweep all completed tasks |
| `r` | Reset task timer |
| `?` / `Shift+H` | Toggle command cheatsheet guide |
| `q` | Quit application |

*Data is automatically saved to `~/.config/endtime/tasks.json` and `~/.config/endtime/config.json`.*

## License

[MIT](LICENSE)
