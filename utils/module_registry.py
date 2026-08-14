# utils/module_registry.py
import threading
from typing import Any

class ModuleRegistry:
    """
    Central registry for module running state.
    
    Owns per-module threading.Event stop tokens so module threads
    can stop promptly via stop_event.wait() instead of time.sleep().
    All mutations protected by a threading.Lock.
    """
    
    def __init__(self):
        self._stop_events: dict[str, threading.Event] = {}
        self._param_cache: dict[str, list[Any]] = {}
        self._lock = threading.Lock()

    def is_running(self, module: str) -> bool:
        """Returns True if the module has an active (non-set) stop event."""
        with self._lock:
            event = self._stop_events.get(module)
            return event is not None and not event.is_set()

    def start(self, module: str, params: list[Any]) -> threading.Event:
        """
        Creates a fresh stop event for the module, caches params, and returns the event.
        Caller is responsible for starting the thread with this event.
        """
        with self._lock:
            stop_event = threading.Event()
            self._stop_events[module] = stop_event
            self._param_cache[module] = list(params)
            return stop_event

    def stop(self, module: str) -> None:
        """
        Sets the module's stop event so the thread exits on its next wait() call.
        No-op if the module is not running.
        """
        with self._lock:
            event = self._stop_events.get(module)
            if event is not None:
                event.set()
            # Remove from registry so is_running returns False immediately
            self._stop_events.pop(module, None)

    def get_stop_event(self, module: str) -> threading.Event | None:
        """Returns the current stop event for the module, or None if not running."""
        with self._lock:
            return self._stop_events.get(module)

    def get_params(self, module: str) -> list[Any]:
        """Returns the cached params for the module (empty list if not found)."""
        with self._lock:
            return list(self._param_cache.get(module, []))

    def active_modules(self) -> list[str]:
        """Returns the list of currently running module names."""
        with self._lock:
            return [
                m for m, e in self._stop_events.items()
                if not e.is_set()
            ]
