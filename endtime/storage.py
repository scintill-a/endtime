"""Persistence and storage management for Endtime."""
import json
import uuid
import functools
from typing import List, Set, Dict, Any, TYPE_CHECKING
from endtime.config import TASKS_DIR, TASKS_FILE, CONFIG_FILE

if TYPE_CHECKING:
    from textual.app import App


class StorageManager:
    """Manages disk I/O and debounced async saving for tasks and configuration."""

    def __init__(self, app: "App"):
        self.app = app
        self._dirty_tasks: bool = False
        self._dirty_config: bool = False
        self._save_timer = None

    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load tasks from disk synchronously and ensure unique IDs."""
        tasks_data = []
        if TASKS_FILE.exists():
            try:
                with open(TASKS_FILE, "r") as f:
                    tasks_data = json.load(f)
                    for t in tasks_data:
                        if "id" not in t:
                            t["id"] = str(uuid.uuid4())
            except Exception:
                pass
        return tasks_data

    def save_tasks_sync(self, tasks_data: List[Dict[str, Any]]) -> None:
        """Save tasks directly to disk synchronously."""
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(TASKS_FILE, "w") as f:
                json.dump(tasks_data, f, indent=2)
        except Exception:
            pass

    def load_collapsed_tags(self) -> Set[str]:
        """Load set of collapsed category tag names from config file."""
        collapsed_tags = set()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    collapsed_tags = set(data.get("collapsed_tags", []))
            except Exception:
                pass
        return collapsed_tags

    def load_tag_order(self) -> List[str]:
        """Load list of ordered category tag names from config file."""
        tag_order = []
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    tag_order = list(data.get("tag_order", []))
            except Exception:
                pass
        return tag_order

    def save_collapsed_tags_sync(self, collapsed_tags: Set[str], tag_order: List[str] = None) -> None:
        """Save collapsed category tags and tag order directly to config file synchronously."""
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            config_data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
            config_data["collapsed_tags"] = list(collapsed_tags)
            if tag_order is not None:
                config_data["tag_order"] = list(tag_order)
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

    def schedule_save(self, tasks: bool = False, config: bool = False) -> None:
        """Schedule a debounced save to background thread."""
        if tasks:
            self._dirty_tasks = True
        if config:
            self._dirty_config = True
        if self._save_timer is not None:
            try:
                self._save_timer.stop()
            except Exception:
                pass
        self._save_timer = self.app.set_timer(0.3, self._flush_save)

    def _flush_save(self, immediate: bool = False) -> None:
        """Flush dirty states to disk either immediately or via background thread workers."""
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
                self.save_tasks_sync(getattr(self.app, "tasks_data", []))
            else:
                data_copy = list(getattr(self.app, "tasks_data", []))
                self.app.run_worker(functools.partial(self._async_save_tasks, data_copy), thread=True)
                
        if save_c:
            tags_copy = list(getattr(self.app, "collapsed_tags", set()))
            order_copy = list(getattr(self.app, "tag_order", []))
            if immediate:
                self.save_collapsed_tags_sync(tags_copy, order_copy)
            else:
                self.app.run_worker(functools.partial(self._async_save_config, tags_copy, order_copy), thread=True)

    def _async_save_tasks(self, data_copy: List[Dict[str, Any]]) -> None:
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(TASKS_FILE, "w") as f:
                json.dump(data_copy, f, indent=2)
        except Exception:
            pass

    def _async_save_config(self, tags_copy: List[str], order_copy: List[str] = None) -> None:
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            config_data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
            config_data["collapsed_tags"] = tags_copy
            if order_copy is not None:
                config_data["tag_order"] = order_copy
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

