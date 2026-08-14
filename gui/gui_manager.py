# Internal Imports - Utils
from utils.hotkeys import set_hotkey, on_key_press
from utils.listeners import install_win_event_hook
from utils.module_registry import ModuleRegistry
from utils.options import load_settings, save_settings
from utils.executor import toggle_and_execute, retoggle
from utils.others import get_file_path, set_icon, set_settings, open_web, resource

# Internal Imports - Configs
from config.categories import ModuleCategory
from config.modules import modules
from config.setup import *

# Internal Imports - GUI
from gui.gui_dropdown import Dropdown
from gui.gui_tooltip import ToolTip
from gui.sidebar import SidebarNav
from gui.content_canvas import ScrollableContentCanvas
from gui.status_bar import StatusBar

# Third-party Library Imports
import keyboard

# Standard Library Imports
import tkinter as tk
import threading


class GUI:
    def __init__(self, version, title, dev):
        # ----------------------------------------------------------------
        # Attributes
        # ----------------------------------------------------------------
        self.version = version
        self.title   = title
        self.dev     = dev
        self.modules = modules

        # Widget-value dicts (raw values when tab not open, widgets otherwise)
        self.buttons  = {}
        self.sliders  = {}
        self.checkboxs = {}
        self.dropdowns = {}
        self.toggle_buttons = {}

        self._initialize_factory_defaults()

        self.hotkeys_enabled  = True
        self.tooltips_enabled = True

        # Module registry (owns stop events)
        self.registry = ModuleRegistry()

        # Lock for atomic focus-state writes from listener thread
        self._state_lock = threading.Lock()

        # Filter flags (set by settings.py thread_window / thread_menu)
        self.focus_filter_enabled = False
        self.menu_filter_enabled  = False

        # Focus / menu state
        self.focused_process         = None
        self.currently_in_foreground = True
        self.currently_in_menu       = False

        # JSON settings file
        self.json_file = resource(get_file_path("options.json"))

        # ----------------------------------------------------------------
        # Root window
        # ----------------------------------------------------------------
        self.root = tk.Tk()
        self.root.title(title)
        self.root.minsize(MIN_SIZE_W, MIN_SIZE_H)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(True, True)
        self.root.configure(bg=CONTENT_COLOR)
        set_icon(self.root)
        self.root.protocol("WM_DELETE_WINDOW",
                           lambda: save_settings(self, self.json_file))

        # ----------------------------------------------------------------
        # Load GUI assets
        # ----------------------------------------------------------------
        self.on   = tk.PhotoImage(file=resource(get_file_path("on.png")))
        self.off  = tk.PhotoImage(file=resource(get_file_path("off.png")))
        self.save = tk.PhotoImage(file=resource(get_file_path("save.png")))
        self.load = tk.PhotoImage(file=resource(get_file_path("load.png")))

        # ----------------------------------------------------------------
        # Keyboard listener (hotkeys) — suppress=False ensures volume/Fn
        # keys are never blocked by the hook.
        # ----------------------------------------------------------------
        self.listener = keyboard.on_press(
            lambda event: on_key_press(self, event), suppress=False
        )

        # ----------------------------------------------------------------
        # Mouse hook (for physical hold detection)
        # ----------------------------------------------------------------
        from utils.mouse_hook import MouseHook
        self.mouse_hook = MouseHook(self)

        # ----------------------------------------------------------------
        # Window focus detection (event-driven, falls back to polling)
        # ----------------------------------------------------------------
        install_win_event_hook(self)

        # ----------------------------------------------------------------
        # Load + apply settings
        # ----------------------------------------------------------------
        load_settings(self, self.json_file)
        set_settings(self)

        # ----------------------------------------------------------------
        # Build GUI
        # ----------------------------------------------------------------
        self._build_layout()

        # Show default page
        self.on_navigate(DEFAULT_PAGE)

    def _initialize_factory_defaults(self):
        for module_name, mod_def in self.modules.items():
            # Sliders
            for x in range(mod_def.get("slider", 0)):
                self.sliders[f"{module_name}_{x}"] = mod_def[f"slider_default{x + 1}"]
            # Checkboxes
            for x in range(mod_def.get("checkbox", 0)):
                self.checkboxs[f"{module_name}_{x}"] = False
            # Dropdowns
            for x in range(mod_def.get("dropdown", 0)):
                self.dropdowns[f"{module_name}_{x}"] = mod_def[f"dropdown_values{x + 1}"][0]
            # Buttons (controls defaults)
            for x in range(mod_def.get("button", 0)):
                btn_text = mod_def.get(f"button_text{x + 1}")
                if btn_text:
                    self.buttons[f"{module_name}_{x}"] = btn_text

    # ====================================================================
    # Layout builders
    # ====================================================================

    def _build_layout(self):
        """Build the three-panel layout: sidebar | content | (status bar at bottom)."""

        # Status bar (bottom)
        self.status_bar = StatusBar(self.root, self.version, self.dev)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Sidebar (left)
        categories = list(ModuleCategory)
        self.sidebar = SidebarNav(self.root, categories,
                                  on_select=self.on_navigate)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # Scrollable content area (right)
        self.content_canvas = ScrollableContentCanvas(self.root)
        self.content_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Keep a reference to the inner frame for widget placement
        self.content_frame = self.content_canvas.get_inner_frame()

        # Keep option_buttons as an alias for backward compat (store sidebar)
        self.option_buttons = []

    # ====================================================================
    # Navigation
    # ====================================================================

    def on_navigate(self, category):
        """Switch to a new category page (no flicker, no overlay hack)."""
        # 1. Save current widget values
        self._store_all_values()

        # Clear toggle buttons references before destroying widgets
        self.toggle_buttons.clear()

        # 2. Clear content area
        self.content_canvas.clear()

        # 3. Build widgets for new category
        modules_for_category = {
            name: info for name, info in self.modules.items()
            if info.get("category") == category
        }
        self._create_widgets_for_modules(modules_for_category)

        # 4. Restore saved values for all modules on this page
        for module_name in modules_for_category:
            self._restore_values(module_name)

        # 5. Update sidebar highlight
        self.sidebar.set_active(category)

        # 6. Scroll to top
        self.content_canvas.scroll_to_top()

    # ====================================================================
    # Value store / restore
    # ====================================================================

    def _store_all_values(self):
        """Persist current widget values into the raw-value dicts."""
        for card in self.content_frame.winfo_children():
            module_name = getattr(card, "module_name", None)
            if module_name:
                self.store_values(module_name, self.sliders,   (int, float), tk.Scale)
                self.store_values(module_name, self.checkboxs,  bool,         tk.BooleanVar)
                self.store_values(module_name, self.dropdowns,  str,          Dropdown)
                self.store_values(module_name, self.buttons,    str,          tk.Button)

    def store_values(self, module_name, objects, data_type, obj_type):
        index = 0
        while True:
            obj_name = f"{module_name}_{index}"
            if obj_name not in objects:
                break
            if not isinstance(objects[obj_name], data_type):
                obj = objects[obj_name]
                try:
                    if obj_type in (tk.Scale, tk.BooleanVar):
                        if hasattr(obj, 'winfo_exists') and not obj.winfo_exists():
                            pass  # widget destroyed, skip
                        else:
                            objects[obj_name] = obj.get()
                    elif obj_type == tk.Button:
                        if hasattr(obj, 'winfo_exists') and not obj.winfo_exists():
                            pass  # widget destroyed, skip
                        else:
                            objects[obj_name] = obj.cget("text")
                    elif obj_type == Dropdown:
                        if hasattr(obj, 'winfo_exists') and not obj.winfo_exists():
                            pass  # widget destroyed, skip
                        else:
                            objects[obj_name] = obj.selected_option.get()
                except Exception:
                    pass  # widget was destroyed between check and access
            index += 1

    def _restore_values(self, module_name):
        """After rebuilding widgets, push saved raw values back into them."""
        # Sliders
        x = 0
        while True:
            key = f"{module_name}_{x}"
            if key not in self.sliders:
                break
            widget = self.sliders[key]
            if hasattr(widget, 'set') and not isinstance(widget, (int, float)):
                saved = self.sliders.get(key)
                if isinstance(saved, (int, float)):
                    widget.set(saved)
            x += 1

        # Checkboxes
        x = 0
        while True:
            key = f"{module_name}_{x}"
            if key not in self.checkboxs:
                break
            var = self.checkboxs[key]
            if hasattr(var, 'set') and not isinstance(var, bool):
                saved = self.checkboxs.get(key)
                if isinstance(saved, bool):
                    var.set(saved)
            x += 1

        # Dropdowns
        x = 0
        while True:
            key = f"{module_name}_{x}"
            if key not in self.dropdowns:
                break
            dd = self.dropdowns[key]
            if hasattr(dd, 'selected_option'):
                saved = self.dropdowns.get(key)
                if isinstance(saved, str):
                    dd.selected_option.set(saved)
                    dd.dropdown_button.config(text=f"{saved} ↓")
            x += 1

    # ====================================================================
    # Widget factories
    # ====================================================================

    def _create_widgets_for_modules(self, modules_dict):
        # Use grid layout so all cards fill the full height evenly
        module_list = list(modules_dict.keys())
        num_modules = len(module_list)

        # Configure the content_frame to use grid
        self.content_frame.rowconfigure(0, weight=1)
        for col_idx in range(num_modules):
            self.content_frame.columnconfigure(col_idx, weight=1, uniform="card")

        for col_idx, module in enumerate(module_list):
            self._create_module_card(module, col_idx)

    def _create_module_card(self, module, col_idx=0):
        # Outer card frame using grid for full height
        card = tk.Frame(
            self.content_frame,
            bg=CONTENT_COLOR,
            borderwidth=8,
            relief=RELIEF_FRAME,
        )
        card.module_name = module
        card.grid(row=0, column=col_idx, sticky="nsew", padx=0, pady=0)

        # Top section (title, sliders, checkboxes, dropdowns, buttons)
        top_section = tk.Frame(card, bg=CONTENT_COLOR)
        top_section.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.create_title_label(top_section, module)
        self.create_label(top_section, module)
        self.create_slider(top_section, module)
        self.create_check_box(top_section, module)
        self.create_dropdown(top_section, module)
        self.create_button(top_section, module)

        # Hotkey + toggle row pinned at bottom of card
        bottom_row = tk.Frame(card, bg=CONTENT_COLOR)
        bottom_row.pack(side=tk.BOTTOM, fill=tk.X, anchor=tk.S)
        self.create_hotkey_button(bottom_row, module)
        self.create_toggle_button(bottom_row, module)

    # ====================================================================
    # Individual widget creators (unchanged from v0.1.8)
    # ====================================================================

    def create_title_label(self, parent, module):
        title = self.modules.get(module)["name"]
        label = tk.Label(
            parent, text=title, width=WIDTH,
            fg=FONT_COLOR, font=(FONT, FONT_SIZE_SUBTITLE, "bold"),
            bg=CONTENT_COLOR,
        )
        label.pack(side=tk.TOP, padx=2 * CONTENT_PAD_X, pady=(CONTENT_PAD_Y, 0))

    def create_label(self, parent, module):
        mod = self.modules.get(module)
        if not mod.get("label"):
            return
        for x in range(mod.get("label")):
            text = mod.get(f"label_text{x + 1}")
            label = tk.Label(
                parent, text=text, fg=FONT_COLOR,
                font=(FONT, FONT_SIZE_CONTENT), bg=CONTENT_COLOR,
                wraplength=LENGTH, width=WIDTH,
            )
            label.pack(fill=tk.BOTH, expand=True, pady=CONTENT_PAD_Y)
            if mod.get(f"label_link{x + 1}"):
                link_key = f"label_link{x + 1}"
                label.bind("<Button-1>",
                           lambda e, lk=link_key: open_web(mod.get(lk)))

    def create_slider(self, parent, module):
        mod = self.modules.get(module)
        if not mod.get("slider"):
            return
        for x in range(mod.get("slider")):
            name         = f"{module}_{x}"
            slider_min   = mod.get(f"slider_min{x + 1}")
            slider_max   = mod.get(f"slider_max{x + 1}")
            slider_text  = mod.get(f"slider_text{x + 1}")
            slider_step  = mod.get(f"slider_step{x + 1}")
            slider_def   = mod.get(f"slider_default{x + 1}")
            slider_tip   = mod.get(f"slider_tooltip{x + 1}")

            slider = tk.Scale(
                parent, bg=CONTENT_COLOR, fg=FONT_COLOR,
                troughcolor=SLIDER_COLOR, activebackground=FONT_COLOR,
                sliderrelief=RELIEF_BASIC, highlightthickness=0,
                font=(FONT, FONT_SIZE_CONTENT), label=slider_text,
                from_=slider_min, to=slider_max,
                orient=tk.HORIZONTAL, bd=0, resolution=slider_step,
            )
            slider.bind("<ButtonRelease-1>",
                        lambda _e, m=module: retoggle(self, m))
            slider.pack(side=tk.TOP, fill=tk.X, expand=True, anchor=tk.CENTER,
                        padx=2 * CONTENT_PAD_X, pady=CONTENT_PAD_Y / 2)

            ToolTip(slider, slider_tip, self.tooltips_enabled)

            # Set saved or default value
            saved = self.sliders.get(name)
            if isinstance(saved, (int, float)):
                slider.set(saved)
            else:
                slider.set(slider_def)

            self.sliders[name] = slider

    def get_slider_value(self, module, x):
        name = f"{module}_{x}"
        obj = self.sliders.get(name)
        if isinstance(obj, tk.Scale):
            try:
                if obj.winfo_exists():
                    return obj.get()
            except Exception:
                pass
            # Widget destroyed — return factory default
            mod_def = self.modules.get(module, {})
            return mod_def.get(f"slider_default{x + 1}", 0)
        return obj if obj is not None else 0

    def create_check_box(self, parent, module):
        mod = self.modules.get(module)
        if not mod.get("checkbox"):
            return
        for x in range(mod.get("checkbox")):
            name     = f"{module}_{x}"
            cb_text  = mod.get(f"checkbox_text{x + 1}")
            cb_tip   = mod.get(f"checkbox_tooltip{x + 1}")
            cb_var   = tk.BooleanVar()

            cb_command = mod.get(f"checkbox_command{x + 1}")
            if cb_command:
                checkbox = tk.Checkbutton(
                    parent, text=f"  {cb_text}",
                    font=(FONT, FONT_SIZE_CONTENT), variable=cb_var,
                    bg=CONTENT_COLOR, fg=FONT_COLOR, selectcolor=CONTENT_COLOR,
                    relief=RELIEF_BASIC, activebackground=PRESS_COLOR,
                    highlightthickness=0, anchor=tk.W,
                    command=lambda cb=cb_command, v=cb_var:
                        cb(self, module, v.get()),
                )
            else:
                checkbox = tk.Checkbutton(
                    parent, text=f"  {cb_text}",
                    font=(FONT, FONT_SIZE_CONTENT), variable=cb_var,
                    bg=CONTENT_COLOR, fg=FONT_COLOR, selectcolor=CONTENT_COLOR,
                    relief=RELIEF_BASIC, activebackground=PRESS_COLOR,
                    highlightthickness=0, anchor=tk.W,
                    command=lambda m=module: retoggle(self, m),
                )

            checkbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True,
                          padx=2 * CONTENT_PAD_X, pady=CONTENT_PAD_Y)
            ToolTip(checkbox, cb_tip, self.tooltips_enabled)

            saved = self.checkboxs.get(name)
            cb_var.set(bool(saved) if isinstance(saved, bool) else mod.get(f"checkbox_default{x + 1}", False))
            self.checkboxs[name] = cb_var

    def get_checkbox_value(self, module, x):
        name = f"{module}_{x}"
        obj = self.checkboxs.get(name)
        if isinstance(obj, tk.BooleanVar):
            try:
                return obj.get()
            except Exception:
                return False
        return bool(obj) if obj is not None else False

    def create_dropdown(self, parent, module):
        mod = self.modules.get(module)
        if not mod.get("dropdown"):
            return
        for x in range(mod.get("dropdown")):
            name    = f"{module}_{x}"
            label   = mod.get(f"dropdown_label{x + 1}")
            values  = mod.get(f"dropdown_values{x + 1}")
            tip     = mod.get(f"dropdown_tooltip{x + 1}")

            border = tk.Frame(parent, bg=PRESS_COLOR,
                              highlightbackground=PRESS_COLOR,
                              highlightthickness=2, bd=0)
            dd = Dropdown(border, label, values,
                          relief=RELIEF_BASIC,
                          command=lambda m=module: retoggle(self, m))
            border.pack(side=tk.TOP, fill=tk.X, expand=True,
                        padx=2 * CONTENT_PAD_X, pady=CONTENT_PAD_Y)
            dd.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            ToolTip(dd, tip, self.tooltips_enabled)

            saved = self.dropdowns.get(name)
            if isinstance(saved, str) and saved in values:
                dd.selected_option.set(saved)
                dd.dropdown_button.config(text=f"{saved} ↓")

            self.dropdowns[name] = dd

    def get_dropdown_value(self, module, x):
        name = f"{module}_{x}"
        dd = self.dropdowns.get(name)
        if hasattr(dd, 'selected_option'):
            return dd.selected_option.get()
        return dd if isinstance(dd, str) else ""

    def create_button(self, parent, module):
        mod = self.modules.get(module)
        if not mod.get("button"):
            return
        for x in range(mod.get("button")):
            name = f"{module}_{x}"

            # Optional label above the button
            if mod.get(f"button_label{x + 1}"):
                btn_label_text = mod.get(f"button_label{x + 1}")
                lbl = tk.Label(
                    parent, text=btn_label_text, fg=FONT_COLOR,
                    font=(FONT, FONT_SIZE_CONTENT), bg=CONTENT_COLOR,
                    wraplength=LENGTH, width=WIDTH, anchor=tk.W,
                )
                lbl.pack(fill=tk.BOTH, expand=True, padx=2 * CONTENT_PAD_X)

            # Image button (Save / Load Config)
            if mod.get(f"button_img{x + 1}"):
                image     = self.load if mod[f"button_img{x + 1}"] == "Load" else self.save
                b_command = mod[f"button_command{x + 1}"]
                border_sl = tk.Frame(parent, bg=FEATURE_COLOR,
                                     highlightbackground=FEATURE_COLOR,
                                     highlightthickness=2, bd=0)
                btn = tk.Button(
                    border_sl, image=image, bg=CONTENT_COLOR,
                    relief=RELIEF_BASIC, activebackground=CONTENT_COLOR,
                    bd=0, command=lambda cmd=b_command: cmd(self, module),
                )
                border_sl.pack(side=tk.BOTTOM, padx=2 * CONTENT_PAD_X,
                               pady=2 * CONTENT_PAD_Y)
                btn.pack(side=tk.BOTTOM)

            else:
                # Text button (Controls, Reset, etc.)
                btn_text    = mod.get(f"button_text{x + 1}")
                btn_command = mod.get(f"button_command{x + 1}")
                border = tk.Frame(parent, bg=PRESS_COLOR,
                                  highlightbackground=PRESS_COLOR,
                                  highlightthickness=2, bd=0)
                btn = tk.Button(
                    border, bg=CONTENT_COLOR,
                    font=(FONT, FONT_SIZE_CONTENT), fg=FONT_COLOR,
                    relief=RELIEF_BASIC, text=btn_text,
                    activebackground=PRESS_COLOR,
                    command=lambda bt=btn_text, n=name:
                        btn_command(self, module, n, bt),
                )
                border.pack(side=tk.TOP, fill=tk.X, expand=True,
                            padx=2 * CONTENT_PAD_X, pady=(0, CONTENT_PAD_Y))
                btn.pack(side=tk.TOP, fill=tk.X, expand=True)

            # Tooltip
            if mod.get(f"button_tooltip{x + 1}"):
                ToolTip(btn, mod[f"button_tooltip{x + 1}"], self.tooltips_enabled)

            # Restore saved button text
            saved = self.buttons.get(name)
            if isinstance(saved, str):
                btn.config(text=saved)

            self.buttons[name] = btn

    def create_hotkey_button(self, parent, module):
        if not self.modules.get(module).get("hotkey", False):
            return
        hotkey_val = self.modules[module].get("hotkey")
        if hotkey_val and hotkey_val != "None":
            hotkey_text = f"Key: [{hotkey_val.upper()}]"
        else:
            hotkey_text = "Bind Hotkey"

        border = tk.Frame(parent, bg=PRESS_COLOR,
                          highlightbackground=PRESS_COLOR,
                          highlightthickness=2, bd=0)
        btn = tk.Button(
            border, bg=CONTENT_COLOR,
            font=(FONT, FONT_SIZE_CONTENT), fg=FONT_COLOR,
            relief=RELIEF_BASIC, text=hotkey_text,
            activebackground=PRESS_COLOR,
            command=lambda: set_hotkey(self, btn, module),
        )
        border.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                    padx=(2 * CONTENT_PAD_X, CONTENT_PAD_X / 2),
                    pady=CONTENT_PAD_Y)
        btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        border.after(50, border.pack_propagate, False)
        btn.after(50, btn.pack_propagate, False)

    def create_toggle_button(self, parent, module):
        if not self.modules.get(module).get("toggle"):
            return
        image = self.on if self.registry.is_running(module) else self.off

        border = tk.Frame(parent, bg=FEATURE_COLOR,
                          highlightbackground=FEATURE_COLOR,
                          highlightthickness=2, bd=0)
        toggle_btn = tk.Button(
            border, image=image, bg=CONTENT_COLOR,
            relief=RELIEF_BASIC, activebackground=CONTENT_COLOR, bd=0,
            command=lambda m=module: toggle_and_execute(self, m),
        )
        border.pack(side=tk.LEFT,
                    padx=(CONTENT_PAD_X / 2, 2 * CONTENT_PAD_X),
                    pady=CONTENT_PAD_Y)
        toggle_btn.pack(side=tk.LEFT)

        self.toggle_buttons[module] = toggle_btn

    # ====================================================================
    # Window resize helper
    # ====================================================================

    def resize_window(self):
        old_w = self.root.winfo_width()
        old_h = self.root.winfo_height()
        new_w = max(self.root.winfo_reqwidth()  + 10, old_w)
        new_h = max(self.root.winfo_reqheight() + 10, old_h)
        if new_w != old_w or new_h != old_h:
            self.root.geometry(f"{new_w}x{new_h}")

    # ====================================================================
    # Back-compat aliases (some internal callers still use old names)
    # ====================================================================

    def option_content(self, option):
        """Alias for on_navigate, keeps backward compat with any call sites."""
        self.on_navigate(option)

    def reset_content_frame(self):
        self.content_canvas.clear()

    def reset_button_colors(self):
        pass  # handled by SidebarNav.set_active
