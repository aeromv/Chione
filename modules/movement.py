import keyboard
import threading
import time
import win32api
import random

from utils.hotkeys import get_controls
from utils.others import modules_should_run
from utils.sendinput import press_key, release_key


# AutoSprint
def autosprint(self, stop_event, module):
    sprint_pressed = False
    sprint_vk = 0x11
    w_release_time = 0.0
    GRACE_PERIOD = 0.15  # keep sprint held for 150ms after W release

    try:
        while not stop_event.is_set():
            if modules_should_run(self):
                sprint_key = get_controls(self, "Controls_0", "CTRL")
                w_key = get_controls(self, "Controls_2", "W")
                sprint_vk = get_vk_code(sprint_key)

                w_held = keyboard.is_pressed(w_key)

                if w_held:
                    w_release_time = 0.0
                    already_held = sprint_vk != 0 and bool(win32api.GetAsyncKeyState(sprint_vk) & 0x8000)
                    if not sprint_pressed and not already_held:
                        press_key(sprint_key)
                        sprint_pressed = True
                else:
                    # W released — start grace timer
                    if sprint_pressed:
                        if w_release_time == 0.0:
                            w_release_time = time.perf_counter()
                        elif time.perf_counter() - w_release_time > GRACE_PERIOD:
                            release_key(sprint_key)
                            sprint_pressed = False
                            w_release_time = 0.0
            else:
                if sprint_pressed:
                    sprint_key = get_controls(self, "Controls_0", "CTRL")
                    release_key(sprint_key)
                    sprint_pressed = False
                w_release_time = 0.0

            stop_event.wait(0.008)
    finally:
        if sprint_pressed:
            try:
                sprint_key = get_controls(self, "Controls_0", "CTRL")
                release_key(sprint_key)
            except Exception:
                pass


def thread_autosprint(self, stop_event, module):
    threading.Thread(target=autosprint, args=(self, stop_event, module), daemon=True).start()


# SprintReset
def get_key_for_mode(mode):
    mapping = {
        "W-Tap":  {"control": "Controls_2", "key": "W"},
        "S-Tap":  {"control": "Controls_4", "key": "S"},
        "Crouch": {"control": "Controls_1", "key": "CTRL"},
    }
    return mapping.get(mode)


def get_vk_code(key_str: str) -> int:
    key_str = key_str.lower()
    special_vk = {
        'shift': 0x10,
        'ctrl': 0x11,
        'control': 0x11,
        'alt': 0x12,
        'space': 0x20,
        'escape': 0x1B,
        'capslock': 0x14,
    }
    if key_str in special_vk:
        return special_vk[key_str]
    if len(key_str) == 1:
        import ctypes
        try:
            ctypes.windll.user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
            ctypes.windll.user32.VkKeyScanW.restype = ctypes.c_short
            vk = ctypes.windll.user32.VkKeyScanW(key_str) & 0xFF
            return vk
        except Exception:
            pass
    return 0


def sprintreset(self, stop_event, module, delay, randomize, hold, mode):
    control, key = get_key_for_mode(mode).values()
    w_key = get_controls(self, "Controls_2", "W")
    tap_key = get_controls(self, control, key)

    prev_left_state = False
    last_hit_time = 0.0
    COMBAT_WINDOW = 0.6

    vk_w = get_vk_code(w_key)

    try:
        while not stop_event.is_set():
            if modules_should_run(self):
                # Unstick W if user stopped holding it
                if vk_w != 0:
                    physical_w = bool(win32api.GetAsyncKeyState(vk_w) & 0x8000)
                    if not physical_w and keyboard.is_pressed(w_key):
                        release_key(w_key)

                current_left = self.mouse_hook.left_pressed
                
                lc_running = self.registry.is_running("LeftClicker")
                lc_toggle_mode = lc_running and not self.get_checkbox_value("LeftClicker", 0)
                
                if current_left and not prev_left_state:
                    last_hit_time = time.perf_counter()
                prev_left_state = current_left

                time_since_hit = time.perf_counter() - last_hit_time
                in_combat = (time_since_hit < COMBAT_WINDOW) or lc_toggle_mode

                is_running_forward = False
                if vk_w != 0:
                    is_running_forward = bool(win32api.GetAsyncKeyState(vk_w) & 0x8000)
                else:
                    is_running_forward = keyboard.is_pressed(w_key)

                if is_running_forward and in_combat:
                    if mode == "W-Tap":
                        release_key(w_key)
                        stop_event.wait(min(max(hold, 0.02), 0.05))
                        
                        if not stop_event.is_set():
                            press_key(w_key)
                            
                            sprint_key = get_controls(self, "Controls_0", "SHIFT")
                            stop_event.wait(0.01)
                            press_key(sprint_key)
                            stop_event.wait(0.02)
                            release_key(sprint_key)

                    elif mode == "S-Tap":
                        press_key(tap_key)
                        stop_event.wait(min(hold, 0.06))
                        release_key(tap_key)

                    elif mode == "Crouch":
                        press_key(tap_key)
                        stop_event.wait(min(hold, 0.05))
                        release_key(tap_key)

                    rand_delay = delay + random.uniform(-randomize, randomize)
                    stop_event.wait(max(rand_delay, 0.05))
                else:
                    stop_event.wait(0.03)
            else:
                stop_event.wait(0.1)
    finally:
        try:
            release_key(w_key)
        except Exception:
            pass
        try:
            release_key(tap_key)
        except Exception:
            pass


def thread_sprintreset(self, stop_event, module, slider, randomize, hold, mode):
    threading.Thread(
        target=sprintreset,
        args=(self, stop_event, module, slider, randomize, hold, mode),
        daemon=True,
    ).start()


# Strafing
def strafing(self, stop_event, module, delay, randomize, hold, randomize_direction):
    a_key = get_controls(self, "Controls_3", "a")
    d_key = get_controls(self, "Controls_5", "d")
    vk_a = get_vk_code(a_key)
    vk_d = get_vk_code(d_key)
    last_key_pressed = random.choice([a_key, d_key])

    try:
        while not stop_event.is_set():
            if modules_should_run(self):
                w_key = get_controls(self, "Controls_2", "W")
                
                # Don't interfere with manual steering
                user_steering = False
                if vk_a != 0 and (win32api.GetAsyncKeyState(vk_a) & 0x8000):
                    user_steering = True
                if vk_d != 0 and (win32api.GetAsyncKeyState(vk_d) & 0x8000):
                    user_steering = True
                
                if keyboard.is_pressed(w_key) and self.mouse_hook.left_pressed and not user_steering:
                    if not randomize_direction:
                        key_to_press = d_key if last_key_pressed == a_key else a_key
                    else:
                        key_to_press = random.choice([a_key, d_key])

                    press_key(key_to_press)
                    
                    # Proportional hold with slight randomness
                    hold_time = hold + random.uniform(-0.01, 0.01)
                    stop_event.wait(max(hold_time, 0.008))
                    
                    release_key(key_to_press)
                    last_key_pressed = key_to_press
                    
                    # Short gap between direction switches
                    stop_event.wait(random.uniform(0.008, 0.020))

                    # Strafe delay
                    rand_delay = delay + random.uniform(-randomize, randomize)
                    stop_event.wait(max(rand_delay, 0.01))
                else:
                    stop_event.wait(0.03)
            else:
                stop_event.wait(0.1)
    finally:
        try:
            release_key(a_key)
        except Exception:
            pass
        try:
            release_key(d_key)
        except Exception:
            pass


def thread_strafing(self, stop_event, module, delay, randomize, hold, randomize_direction):
    threading.Thread(
        target=strafing,
        args=(self, stop_event, module, delay, randomize, hold, randomize_direction),
        daemon=True,
    ).start()


