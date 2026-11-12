"""Uninstaller for Google Drive Automation Studio.

Removes the install folder, the Desktop / Start Menu shortcuts and the
Control Panel (Settings > Apps) uninstall entry.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
import winreg

APP_NAME = "Google Drive Automation Studio"
SHORTCUT_NAME = "Google Drive Automation.lnk"
START_MENU_FOLDER = "Google Drive Automation Studio"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DriveAutomation"
INSTALL_DIR_NAME = "DriveAutomation"


def known_folder(csidl):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


try:
    from winpaths import desktop_dir, programs_dir
except ImportError:  # frozen build without the helper module
    def desktop_dir():
        return known_folder(0x0010)  # CSIDL_DESKTOPDIRECTORY

    def programs_dir():
        return known_folder(0x0016)  # CSIDL_PROGRAMS (Start Menu\Programs)


def install_dir():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Programs", INSTALL_DIR_NAME)


def remove_shortcuts():
    removed = []
    desktop_lnk = os.path.join(desktop_dir(), SHORTCUT_NAME)
    if os.path.isfile(desktop_lnk):
        os.remove(desktop_lnk)
        removed.append(desktop_lnk)

    sm = os.path.join(programs_dir(), START_MENU_FOLDER)
    if os.path.isdir(sm):
        shutil.rmtree(sm, ignore_errors=True)
        removed.append(sm)
    return removed


def remove_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def kill_running():
    """Close a running app instance so its files can be deleted."""
    try:
        subprocess.run(
            ["taskkill", "/IM", "DriveAutomation.exe", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def schedule_self_delete(folder):
    """Windows cannot delete a running exe, so remove the folder after exit."""
    quoted = folder.replace('"', '')
    cmd = (
        'cmd /c "ping -n 3 127.0.0.1 >nul & '
        f'rmdir /s /q \"{quoted}\""'
    )
    subprocess.Popen(cmd, shell=False, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def do_uninstall():
    kill_running()
    remove_shortcuts()
    remove_registry()

    folder = install_dir()
    if os.path.isdir(folder):
        # delete everything except this running uninstaller
        for entry in os.listdir(folder):
            if entry.lower().startswith("driveautomation_uninstall"):
                continue
            path = os.path.join(folder, entry)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except OSError:
                pass
        schedule_self_delete(folder)
    return True


def main():
    if "--silent" in sys.argv:
        do_uninstall()
        return 0

    root = tk.Tk()
    root.title(f"Uninstall {APP_NAME}")
    root.geometry("440x230")
    root.configure(bg="#f3f4f6")

    tk.Label(
        root,
        text="Uninstall Google Drive Automation Studio",
        font=("Segoe UI", 13, "bold"),
        bg="#f3f4f6",
        fg="#111827",
    ).pack(pady=(28, 6))
    tk.Label(
        root,
        text="The app, its shortcuts and its uninstall entry will be removed.",
        font=("Segoe UI", 9),
        bg="#f3f4f6",
        fg="#4b5563",
    ).pack()

    status = tk.StringVar(value="Ready")
    tk.Label(root, textvariable=status, font=("Segoe UI", 9), bg="#f3f4f6", fg="#0369a1").pack(pady=18)

    def run():
        status.set("Uninstalling...")
        root.update()
        do_uninstall()
        status.set("Uninstalled successfully.")
        root.update()
        root.after(1200, root.destroy)

    tk.Button(
        root,
        text="Uninstall",
        font=("Segoe UI", 10, "bold"),
        bg="#dc2626",
        fg="#ffffff",
        activebackground="#b91c1c",
        bd=0,
        padx=26,
        pady=8,
        cursor="hand2",
        command=run,
    ).pack()
    tk.Button(
        root,
        text="Cancel",
        font=("Segoe UI", 10),
        bg="#e5e7eb",
        fg="#111827",
        bd=0,
        padx=26,
        pady=8,
        cursor="hand2",
        command=root.destroy,
    ).pack(pady=(10, 0))

    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
