import random
import threading
import time

import win32api
import win32con
import win32gui
import win32process

from utils.others import modules_should_run, is_cursor_visible
from utils.hotkeys import get_controls
from utils.input_state import is_key_physically_down


# Helpers
def find_win_pos():
    """Return (hwnd, lParam) for posting a click to the game window.

    WindowFromPoint finds the real input window of launchers with nested
    windows (Lunar etc.), but it is only trusted when it belongs to the same
    process as the foreground window — otherwise clicks could land on the
    desktop or another app.
    """
    x, y = win32api.GetCursorPos()
    fg = win32gui.GetForegroundWindow()
    hwnd = win32gui.WindowFromPoint((x, y))
    try:
        if not hwnd or (fg and win32process.GetWindowThreadProcessId(hwnd)[1]
                        != win32process.GetWindowThreadProcessId(fg)[1]):
            hwnd = fg
    except Exception:
        hwnd = hwnd or fg
    rel_x, rel_y = win32gui.ScreenToClient(hwnd, (x, y))
    param = win32api.MAKELONG(rel_x & 0xFFFF, rel_y & 0xFFFF)
    return hwnd, param


_MSG = {
    "left":  (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON,
              win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
    "right": (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON,
              win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
}


def send_virtual_up(hwnd, param, button):
    """Send a window-message button-up (used to clean up a down-only click)."""
    if not hwnd:
        return
    try:
        _, msg_up, _, _, _ = _MSG[button]
        win32api.SendMessage(hwnd, msg_up, 0, param or 0)
    except Exception:
        pass


def click_mouse(hwnd, param, button, virtual=False, physically_held=False):
    """Perform one click.

    virtual=False -> hardware-level mouse_event down + up (normal clicking).

    virtual=True  -> window messages straight to the game ("Break Blocks" /
                     "Allow Eating"). While the user is physically holding the
                     button only a DOWN message is sent: the game keeps seeing
                     the button as held, so eating / bow drawing / block
                     breaking are NOT interrupted, yet every DOWN still counts
                     as a new click (block placing, hits). Sending DOWN+UP —
                     the previous behaviour — released "use item" / "attack"
                     in the game on every click, which is why Allow Eating
                     and Break Blocks did not work.
    """
    msg_down, msg_up, state, ev_down, ev_up = _MSG[button]
    if virtual and hwnd:
        win32api.SendMessage(hwnd, msg_down, state, param)
        if not physically_held:
            win32api.SendMessage(hwnd, msg_up, 0, param)
        return True  # a down-only click may need a later virtual UP
    win32api.mouse_event(ev_down, 0, 0)
    time.sleep(random.uniform(0.005, 0.010))
    win32api.mouse_event(ev_up, 0, 0)
    return False


def shake_effect(shake):
    if shake == 0:
        return
    currentPos = win32api.GetCursorPos()
    direction  = random.randint(0, 3)
    pixels     = random.randint(-shake, shake)
    direction_map = {0: (1, -1), 1: (-1, 1), 2: (1, 1), 3: (-1, -1)}
    x_adjust, y_adjust = direction_map[direction]
    win32api.SetCursorPos((
        currentPos[0] + x_adjust * pixels,
        currentPos[1] + y_adjust * pixels,
    ))


def interval_calculator(cps, randomize):
    # Calculates the sleep interval and adds a bit of randomness so it doesn't look like a robot.
    rand_cps = cps + random.randint(-randomize, randomize)
    rand_cps = max(rand_cps, 1)
    interval = 1.0 / rand_cps
    return max(interval, 0.005)


# Left-click loop
def leftclick(self, stop_event, module, clicks_per_second, randomize, shake,
              blockhit, hold, bblock, allow_shifting, button="left"):
    # Main loop for left clicks. Uses perf_counter for better timing accuracy.
    next_click_time = time.perf_counter()
    virtual_down = None  # (hwnd, param) of a down-only virtual click
    try:
        while not stop_event.is_set():
            # Physical state comes from the hook (ignores our own clicks)
            left_button_state = self.mouse_hook.is_button_physically_down("left")

            # The user let go after a down-only virtual click: release it in the game too
            if virtual_down and not left_button_state:
                send_virtual_up(*virtual_down, button)
                virtual_down = None

            if modules_should_run(self):
                crouch_key = get_controls(self, "Controls_1", "SHIFT")
                is_crouching = is_key_physically_down(self, crouch_key)

                if is_crouching and not allow_shifting:
                    should_click = False
                else:
                    should_click = (hold and left_button_state) or (not hold)

                if should_click:
                    now = time.perf_counter()
                    if now >= next_click_time:
                        interval = interval_calculator(clicks_per_second, randomize)
                        if bblock:
                            hwnd, param = find_win_pos()
                        else:
                            hwnd, param = None, None
                        if click_mouse(hwnd, param, button, bblock, left_button_state):
                            virtual_down = (hwnd, param) if left_button_state else None

                        # Blockhit
                        if random.randint(1, 100) <= blockhit:
                            half_wait = interval / 2 - (time.perf_counter() - now)
                            if half_wait > 0:
                                stop_event.wait(half_wait)
                            click_mouse(None, None, "right", False)

                        shake_effect(shake)

                        # Drift compensation
                        next_click_time += interval
                        if time.perf_counter() - next_click_time > interval * 2:
                            next_click_time = time.perf_counter()
                    else:
                        remaining = next_click_time - time.perf_counter()
                        if remaining > 0.0015:
                            stop_event.wait(remaining - 0.0012)
                        while time.perf_counter() < next_click_time:
                            if stop_event.is_set():
                                break
                else:
                    stop_event.wait(0.005)
                    next_click_time = time.perf_counter()
            else:
                stop_event.wait(0.05)
                next_click_time = time.perf_counter()
    finally:
        if virtual_down and not self.mouse_hook.is_button_physically_down("left"):
            send_virtual_up(*virtual_down, button)
        # Never release a button the user is still physically holding
        if not self.mouse_hook.is_button_physically_down("left"):
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)


def thread_lclick(self, stop_event, module, slider, randomize, shake, blockhit,
                  hold, bblock, allow_shifting, button="left"):
    threading.Thread(
        target=leftclick,
        args=(self, stop_event, module, slider, randomize, shake, blockhit, hold, bblock, allow_shifting, button),
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Right-click loop
# ---------------------------------------------------------------------------

def rightclick(self, stop_event, module, clicks_per_second, randomize, shake,
               hold, eat, ignore_shifting, ignore_leftclicking, allow_menus_shifting, button="right"):
    # Main loop for right clicks.
    next_click_time = time.perf_counter()
    virtual_down = None  # (hwnd, param) of a down-only virtual click
    try:
        while not stop_event.is_set():
            # Physical state comes from the hook (ignores our own clicks)
            right_button_state = self.mouse_hook.is_button_physically_down("right")

            # The user let go after a down-only virtual click: release it in the game too
            if virtual_down and not right_button_state:
                send_virtual_up(*virtual_down, button)
                virtual_down = None

            # Check window focus
            is_focused = not getattr(self, 'focus_filter_enabled', False) or self.currently_in_foreground
            if not is_focused:
                stop_event.wait(0.05)
                next_click_time = time.perf_counter()
                continue

            # Read states
            crouch_key = get_controls(self, "Controls_1", "SHIFT")
            is_crouching = is_key_physically_down(self, crouch_key)
            in_menu = self.currently_in_foreground and (self.currently_in_menu or is_cursor_visible())

            # Decide whether to click based on filters
            should_run_by_menu = True
            if in_menu:
                if allow_menus_shifting and is_crouching:
                    should_run_by_menu = True
                else:
                    should_run_by_menu = False
            else:
                if ignore_shifting and is_crouching:
                    should_run_by_menu = False

            left_held = self.mouse_hook.is_button_physically_down("left")
            if ignore_leftclicking and left_held:
                should_run_by_menu = False

            if should_run_by_menu:
                should_click = (hold and right_button_state) or (not hold)

                if should_click:
                    now = time.perf_counter()
                    if now >= next_click_time:
                        interval = interval_calculator(clicks_per_second, randomize)
                        if eat:
                            hwnd, param = find_win_pos()
                        else:
                            hwnd, param = None, None
                        if click_mouse(hwnd, param, button, eat, right_button_state):
                            virtual_down = (hwnd, param) if right_button_state else None
                        shake_effect(shake)

                        # Drift-compensating schedule
                        next_click_time += interval
                        if time.perf_counter() - next_click_time > interval * 2:
                            next_click_time = time.perf_counter()
                    else:
                        remaining = next_click_time - time.perf_counter()
                        if remaining > 0.0015:
                            stop_event.wait(remaining - 0.0012)
                        while time.perf_counter() < next_click_time:
                            if stop_event.is_set():
                                break
                else:
                    stop_event.wait(0.005)
                    next_click_time = time.perf_counter()
            else:
                stop_event.wait(0.01)
                next_click_time = time.perf_counter()
    finally:
        if virtual_down and not self.mouse_hook.is_button_physically_down("right"):
            send_virtual_up(*virtual_down, button)
        # Never release a button the user is still physically holding
        if not self.mouse_hook.is_button_physically_down("right"):
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0)


def thread_rclick(self, stop_event, module, clicks_per_second, randomize, shake, hold,
                  eat, ignore_shifting, ignore_leftclicking, allow_menus_shifting, button="right"):
    threading.Thread(
        target=rightclick,
        args=(self, stop_event, module, clicks_per_second, randomize, shake, hold, eat,
              ignore_shifting, ignore_leftclicking, allow_menus_shifting, button),
        daemon=True,
    ).start()
