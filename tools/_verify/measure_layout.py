"""Measure the real layout heights so the window can be sized exactly."""
import os
import sys
import tkinter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ["DRIVE_COMPACT"] = "1"

RealTk = tkinter.Tk


class NoLoopTk(RealTk):
    def mainloop(self, *args, **kwargs):
        pass


tkinter.Tk = NoLoopTk

import gmail_drive_login as app  # noqa: E402

app.root.update_idletasks()
print("compact          :", app.COMPACT)
print("root req height  :", app.root.winfo_reqheight())
print("root req width   :", app.root.winfo_reqwidth())
print("root height      :", app.root.winfo_height())
print("body req height  :", app.body_frame.winfo_reqheight())
print("body height      :", app.body_frame.winfo_height())
for child in app.body_frame.winfo_children():
    print(f"   child {child.__class__.__name__:12s} req_h={child.winfo_reqheight():4d} "
          f"h={child.winfo_height():4d} y={child.winfo_y():4d} -> {child}")
print("header req height:", app.header_frame.winfo_reqheight())
print("action req height:", app.action_frame.winfo_reqheight())
