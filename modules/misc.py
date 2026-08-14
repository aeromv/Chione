import threading
import random

from utils.options import save_settings
from utils.hotkeys import get_controls
from utils.sendinput import press_key, release_key


def anti_afk(self, stop_event, module, timer, randomize):
    """
    Periodically presses W then S to prevent AFK kick.

    Uses stop_event.wait(wait_time) instead of time.sleep(wait_time) so the
    thread exits promptly when the stop event is set.
    """
    while not stop_event.is_set():
        wait_time = timer + random.randint(-randomize, randomize)
        wait_time = max(wait_time, 1)

        # Wait for the configured interval (or until stopped)
        if stop_event.wait(wait_time):
            break  # stop_event was set during the wait

        press_key(get_controls(self, "Controls_2", "W"))
        release_key(get_controls(self, "Controls_2", "W"))
        press_key(get_controls(self, "Controls_4", "S"))
        release_key(get_controls(self, "Controls_4", "S"))


def thread_antiafk(self, stop_event, module, timer, randomize):
    threading.Thread(
        target=anti_afk,
        args=(self, stop_event, module, timer, randomize),
        daemon=True,
    ).start()


def selfdestruct(self, stop_event, module):
    """Saves settings and closes the application."""
    save_settings(self, self.json_file)
    self.root.destroy()
