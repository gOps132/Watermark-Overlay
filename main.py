import os
import tkinter as tk


def resolve_app_class():
    force_classic = os.environ.get("WATERMARK_OVERLAY_FORCE_CLASSIC_UI") == "1"
    if force_classic or tk.TkVersion < 8.6:
        from classic_gui import ClassicApp

        return ClassicApp

    from gui_app import App

    return App

if __name__ == "__main__":
    AppClass = resolve_app_class()
    app = AppClass()
    app.mainloop()
