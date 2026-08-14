from utils.module_registry import ModuleRegistry


def ensure_defaults_populated(gui, module):
    """
    Pre-populate gui.sliders / gui.checkboxs / gui.dropdowns with module defaults
    so toggle_and_execute never hits a KeyError even if the tab was never opened.
    """
    mod_def = gui.modules[module]

    for x in range(mod_def.get("slider", 0)):
        key = f"{module}_{x}"
        if key not in gui.sliders or gui.sliders[key] is None:
            gui.sliders[key] = mod_def[f"slider_default{x + 1}"]

    for x in range(mod_def.get("checkbox", 0)):
        key = f"{module}_{x}"
        if key not in gui.checkboxs or gui.checkboxs[key] is None:
            gui.checkboxs[key] = mod_def.get(f"checkbox_default{x + 1}", False)

    for x in range(mod_def.get("dropdown", 0)):
        key = f"{module}_{x}"
        if key not in gui.dropdowns or gui.dropdowns[key] is None:
            gui.dropdowns[key] = mod_def[f"dropdown_values{x + 1}"][0]


def toggle_and_execute(gui, module):
    """
    Toggle a module on or off.

    On  → create a fresh stop_event via registry.start(), launch the command thread.
    Off → signal the stop_event via registry.stop().

    The stop_event is injected between gui and module:
        command(gui, stop_event, module, *params)
    """
    currently_on = gui.registry.is_running(module)
    new_state = not currently_on

    # Pre-populate defaults so get_params never raises KeyError
    ensure_defaults_populated(gui, module)

    # Update toggle button image on main thread safely
    def safe_update_button():
        try:
            button = gui.toggle_buttons.get(module)
            if button is not None and button.winfo_exists():
                img = gui.on if new_state else gui.off
                button.config(image=img)
        except Exception:
            pass
    gui.root.after(0, safe_update_button)

    if new_state:
        command = gui.modules[module]["command"]
        params = get_params(gui, gui.modules[module]["params"], module)
        stop_event = gui.registry.start(module, params)
        command(gui, stop_event, module, *params)

        # Update status bar if present safely
        if hasattr(gui, "status_bar"):
            def safe_status_active():
                try:
                    if gui.status_bar.winfo_exists():
                        gui.status_bar.set_active(module)
                except Exception:
                    pass
            gui.root.after(0, safe_status_active)
    else:
        gui.registry.stop(module)

        # Update status bar if present safely
        if hasattr(gui, "status_bar"):
            def safe_status_inactive():
                try:
                    if gui.status_bar.winfo_exists():
                        gui.status_bar.set_inactive(module)
                except Exception:
                    pass
            gui.root.after(0, safe_status_inactive)


def retoggle(gui, module):
    """
    Stop then immediately restart a module with fresh widget params.
    No hardcoded sleep — stop_event signals the thread instantly.
    """
    if gui.registry.is_running(module):
        gui.registry.stop(module)
        toggle_and_execute(gui, module)


def get_params(gui, funs, module):
    """
    Build the params list by calling each function name in `funs` on `gui`.
    The index resets whenever the function name changes (matching original behaviour).
    """
    params = []
    number = 0
    prev_fun = None
    for fun_name in funs:
        if hasattr(gui, fun_name) and callable(getattr(gui, fun_name)):
            fun = getattr(gui, fun_name)
            if prev_fun is None or fun_name != prev_fun:
                number = 0
            prev_fun = fun_name
            result = fun(module, number)
            params.append(result)
            number += 1
        else:
            print(f"Function '{fun_name}' not found in the class.")
    return params
