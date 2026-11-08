import ctypes
import logging
import os
import sys
import threading

LOG_FILE = os.path.join(os.path.expanduser("~"), "chione_error.log")


def setup_logging():
    """Send every uncaught error (main thread, module threads, Tk callbacks)
    to ~/chione_error.log. The windowed build has no console, so before this a
    crashing module thread just silently stopped working."""
    try:
        logging.basicConfig(
            filename=LOG_FILE, level=logging.WARNING, encoding="utf-8",
            format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
        )
    except Exception:
        return

    def thread_hook(args):
        logging.error("Uncaught exception in thread %s",
                      getattr(args.thread, "name", "?"),
                      exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    def main_hook(exc_type, exc_value, exc_tb):
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    threading.excepthook = thread_hook
    sys.excepthook = main_hook


def message_box(text, title="Chione"):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    if not is_admin():
        if getattr(sys, 'frozen', False):
            executable = sys.executable
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        else:
            executable = sys.executable
            params = f'"{sys.argv[0]}" ' + " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        
        # Relaunch as admin (UAC prompt will be shown)
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        if result <= 32:
            # UAC was declined or failed: say so instead of silently vanishing
            message_box("Chione needs administrator rights to send clicks and "
                        "keys to Minecraft.\n\nPlease start it again and accept "
                        "the administrator prompt.")
        sys.exit(0)

    # Windowed builds have no console: stdout/stderr can be None, which breaks
    # print(file=sys.stderr). Redirect them to devnull; real errors go to the log.
    if sys.stdout is None or sys.stderr is None or getattr(sys, 'frozen', False):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    setup_logging()

    # Set Windows timer resolution to 1ms for ultra-accurate CPS and sleep times
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    version = "1.0.1"
    title = "Chione"
    dev = "dev by marshall | Modified by AeroMV"
    try:
        from gui.gui_manager import GUI
        app = GUI(version, title, dev)
    except Exception:
        logging.exception("Chione failed to start")
        message_box(f"Chione failed to start.\n\nDetails were written to:\n{LOG_FILE}")
        raise
    app.root.mainloop()


if __name__ == "__main__":
    main()

# KNOWN-BUGS
# BUG: If blockhit is high, the cps will be lower than the set cps. (Blockhit delays further clicks)
# BUG: If "only in menu" is toggled, this indireclty means "only in game" is toggled too.
# BUG: All modules automatically wont work in Chione itself, to keep the program always usable. 
    # The user has to click out of Chione to loose focus, then the modules will work.
# BUG: AC-Shaking not working in Badlion-Client (possibly others too, didn't test).
# BUG: Modules have to be opened in the tab once, to be able to be toggled.
# BUG: Weird delay for hits, when breaking blocks and allowing to eat.