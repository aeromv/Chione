from gui.gui_manager import GUI
from tkinter import *
import ctypes
import sys


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
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        sys.exit(0)

    # Redirect stdout and stderr to devnull in frozen windowed mode to prevent crashes from print calls
    if getattr(sys, 'frozen', False):
        import os
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    # Set Windows timer resolution to 1ms for ultra-accurate CPS and sleep times
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    version = "1.0.0"
    title = "Chione"
    dev = "dev by marshall | Modified by AeroMV"
    app = GUI(version, title, dev)
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