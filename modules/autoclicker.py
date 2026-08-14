import random
import threading
import time

import win32api
import win32con
import win32gui

from utils.others import modules_should_run
import keyboard
from utils.hotkeys import get_controls

# Overhead constant — subtracted from the raw interval so actual CPS converges
# to the target despite Win32 round-trip latency (~0.5–2 ms per click).
CLICK_OVERHEAD_SECONDS = 0.0


# Helpers
def find_win_pos():
    x, y = win32api.GetCursorPos()
    # Use WindowFromPoint to find the actual input-receiving window
    # (fixes Break Blocks on Lunar Client and other launchers with nested windows)
    hwnd = win32gui.WindowFromPoint((x, y))
    if not hwnd:
        hwnd = win32gui.GetForegroundWindow()
    rel_x, rel_y = win32gui.ScreenToClient(hwnd, (x, y))
    param = win32api.MAKELONG(rel_x, rel_y)
    return hwnd, param


def click_mouse(title, param, button, bblock=False):
    if bblock:
        # Use SendMessage for virtual clicks (preserves physical hold for block breaking/eating on vanilla)
        msg_down = win32con.WM_LBUTTONDOWN if button == 'left' else win32con.WM_RBUTTONDOWN
        msg_up   = win32con.WM_LBUTTONUP   if button == 'left' else win32con.WM_RBUTTONUP
        state    = win32con.MK_LBUTTON      if button == 'left' else win32con.MK_RBUTTON
        win32api.SendMessage(title, msg_down, state, param)
        win32api.SendMessage(title, msg_up,   state, param)
    else:
        # Use hardware mouse_event with realistic hold time (compatible with Badlion/Lunar and bypasses anti-cheats)
        msg_down_bb = win32con.MOUSEEVENTF_LEFTDOWN if button == 'left' else win32con.MOUSEEVENTF_RIGHTDOWN
        msg_up_bb   = win32con.MOUSEEVENTF_LEFTUP   if button == 'left' else win32con.MOUSEEVENTF_RIGHTUP
        
        win32api.mouse_event(msg_down_bb, 0, 0)
        time.sleep(random.uniform(0.005, 0.010))
        win32api.mouse_event(msg_up_bb, 0, 0)


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
    try:
        while not stop_event.is_set():
            # Get physical state fallback if hook drops
            left_button_state = self.mouse_hook.left_pressed or bool(win32api.GetAsyncKeyState(0x01) & 0x8000)

            if modules_should_run(self):
                crouch_key = get_controls(self, "Controls_1", "SHIFT")
                is_crouching = keyboard.is_pressed(crouch_key)
                
                if bblock and is_crouching and not allow_shifting:
                    should_click = False
                else:
                    should_click = (hold and left_button_state) or (not hold)

                if should_click:
                    now = time.perf_counter()
                    if now >= next_click_time:
                        interval = interval_calculator(clicks_per_second, randomize)
                        if bblock:
                            title, param = find_win_pos()
                        else:
                            title, param = None, None
                        click_mouse(title, param, button, bblock)

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
    from utils.others import is_cursor_visible
    next_click_time = time.perf_counter()
    try:
        while not stop_event.is_set():
            # Check window focus
            is_focused = not getattr(self, 'focus_filter_enabled', False) or self.currently_in_foreground
            if not is_focused:
                stop_event.wait(0.05)
                next_click_time = time.perf_counter()
                continue

            # Read states
            right_button_state = self.mouse_hook.right_pressed or bool(win32api.GetAsyncKeyState(0x02) & 0x8000)
            crouch_key = get_controls(self, "Controls_1", "SHIFT")
            is_crouching = keyboard.is_pressed(crouch_key)
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

            left_held = self.mouse_hook.left_pressed or bool(win32api.GetAsyncKeyState(0x01) & 0x8000)
            if ignore_leftclicking and left_held:
                should_run_by_menu = False

            if should_run_by_menu:
                should_click = (hold and right_button_state) or (not hold)

                if should_click:
                    now = time.perf_counter()
                    if now >= next_click_time:
                        interval = interval_calculator(clicks_per_second, randomize)
                        if eat:
                            title, param = find_win_pos()
                        else:
                            title, param = None, None
                        click_mouse(title, param, button, eat)
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
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0)


def thread_rclick(self, stop_event, module, clicks_per_second, randomize, shake, hold,
                  eat, ignore_shifting, ignore_leftclicking, allow_menus_shifting, button="right"):
    threading.Thread(
        target=rightclick,
        args=(self, stop_event, module, clicks_per_second, randomize, shake, hold, eat,
              ignore_shifting, ignore_leftclicking, allow_menus_shifting, button),
        daemon=True,
    ).start()
