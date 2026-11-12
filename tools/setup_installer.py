"""Google Drive Automation Studio - installer.

Installs the one-directory app build into the per-user Programs folder,
creates a Desktop and Start Menu shortcut, registers an uninstall entry in
Windows Settings and (optionally) launches the app.

Run silently with:  DriveAutomation-Setup.exe --silent
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
import zipfile
from tkinter import ttk

APP_NAME = "Google Drive Automation Studio"
APP_EXE = "DriveAutomation.exe"
UNINSTALLER_EXE = "DriveAutomation_Uninstall.exe"
SHORTCUT_NAME = "Google Drive Automation.lnk"
START_MENU_FOLDER = "Google Drive Automation Studio"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DriveAutomation"
PAYLOAD = "payload.zip"
UNINSTALLER_PAYLOAD = os.path.join("uninstaller", UNINSTALLER_EXE)
VERSION = "1.0.0"
LOG_FILE = os.path.join(tempfile.gettempdir(), "DriveAutomation-setup.log")


def log(message):
    """Always trace installer steps - the setup exe runs without a console."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- paths
try:
    from winpaths import desktop_dir, programs_dir, local_app_data
except ImportError:  # frozen build without the helper module
    def _csidl(csidl):
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
        return buf.value

    def desktop_dir():
        return _csidl(0x0010)

    def programs_dir():
        return _csidl(0x0016)

    def local_app_data():
        return os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))


def default_install_dir():
    return os.path.join(local_app_data(), "Programs", "DriveAutomation")


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


# --------------------------------------------------------------------------- helpers
def ps_escape(value):
    return value.replace("'", "''")


def create_shortcut(shortcut_path, target, workdir, description, icon_path):
    script = (
        "$ErrorActionPreference='Stop'; "
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{sp}'); "
        "$s.TargetPath='{t}'; "
        "$s.WorkingDirectory='{w}'; "
        "$s.Description='{d}'; "
        "$s.IconLocation='{i},0'; "
        "$s.WindowStyle=1; "
        "$s.Save()"
    ).format(
        sp=ps_escape(shortcut_path),
        t=ps_escape(target),
        w=ps_escape(workdir),
        d=ps_escape(description),
        i=ps_escape(icon_path),
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        capture_output=True,
    )


def register_uninstall(install_dir, uninstaller_path, app_exe, size_bytes):
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "SN-IT")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller_path}"')
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstaller_path}" --silent')
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, app_exe)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, max(1, size_bytes // 1024))


# --------------------------------------------------------------------------- install
class Installer:
    def __init__(self, install_dir, desktop_shortcut=True, start_menu=True, launch=True):
        self.install_dir = install_dir
        self.desktop_shortcut = desktop_shortcut
        self.start_menu = start_menu
        self.launch = launch
        self.progress = None
        self.status = None
        self.done = False
        self.error = None
        self.root = None

    # -- worker ------------------------------------------------------------
    def run(self):
        try:
            log(f"install start -> {self.install_dir}")
            self._install()
            self.done = True
            log("install finished OK")
        except Exception as exc:  # noqa: BLE001
            self.error = exc
            log(f"install FAILED: {exc!r}\n{traceback.format_exc()}")

    def _install(self):
        payload = resource(PAYLOAD)
        if not os.path.isfile(payload):
            raise FileNotFoundError(f"payload missing: {payload}")

        staging = self.install_dir + ".new"
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)

        with zipfile.ZipFile(payload) as zf:
            members = zf.infolist()
            total = len(members)
            for idx, member in enumerate(members, start=1):
                zf.extract(member, staging)
                if self.progress is not None and (idx % 25 == 0 or idx == total):
                    self.progress["value"] = idx
                    self.status_set(f"Extracting files... {idx}/{total}")
                    self.pump()

        # swap staged copy in
        if os.path.isdir(self.install_dir):
            shutil.rmtree(self.install_dir, ignore_errors=True)
        os.makedirs(os.path.dirname(self.install_dir), exist_ok=True)
        shutil.move(staging, self.install_dir)

        app_exe = os.path.join(self.install_dir, APP_EXE)
        uninstaller_src = resource(UNINSTALLER_PAYLOAD)
        uninstaller_dst = os.path.join(self.install_dir, UNINSTALLER_EXE)
        if os.path.isfile(uninstaller_src):
            shutil.copy2(uninstaller_src, uninstaller_dst)

        self.status_set("Creating shortcuts...")
        self.pump()

        if self.desktop_shortcut:
            target = os.path.join(desktop_dir(), SHORTCUT_NAME)
            log(f"desktop shortcut -> {target}")
            create_shortcut(target, app_exe, self.install_dir, APP_NAME, app_exe)
        if self.start_menu:
            sm_dir = os.path.join(programs_dir(), START_MENU_FOLDER)
            os.makedirs(sm_dir, exist_ok=True)
            target = os.path.join(sm_dir, SHORTCUT_NAME)
            log(f"start menu shortcut -> {target}")
            create_shortcut(target, app_exe, self.install_dir, APP_NAME, app_exe)
            target = os.path.join(sm_dir, "Uninstall " + APP_NAME + ".lnk")
            log(f"start menu uninstall shortcut -> {target}")
            create_shortcut(
                target,
                uninstaller_dst,
                self.install_dir,
                "Uninstall " + APP_NAME,
                uninstaller_dst,
            )

        self.status_set("Registering in Windows Settings...")
        self.pump()
        size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fs in os.walk(self.install_dir)
            for f in fs
        )
        log("writing registry uninstall entry")
        register_uninstall(self.install_dir, uninstaller_dst, app_exe, size)
        log("registry uninstall entry written")

        self.status_set("Installation complete.")
        self.pump()

    # -- thread safe UI helpers -------------------------------------------
    def status_set(self, text):
        if self.status is not None:
            self.status.set(text)

    def pump(self):
        if self.root is not None:
            self.root.update_idletasks()


# --------------------------------------------------------------------------- GUI
class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} - Setup")
        self.root.geometry("560x520")
        self.root.resizable(False, False)
        self.root.configure(bg="#f3f4f6")

        self.install_dir = tk.StringVar(value=default_install_dir())
        self.desktop_shortcut = tk.BooleanVar(value=True)
        self.start_menu = tk.BooleanVar(value=True)
        self.launch = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready to install")
        self.progress = ttk.Progressbar(self.root, mode="determinate", length=480)
        self.installer = None

        self._build_header()
        self._build_body()
        self._build_footer()
        self.root.mainloop()

    def _build_header(self):
        header = tk.Frame(self.root, bg="#1e293b", padx=22, pady=20)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Google Drive Automation Studio",
            font=("Segoe UI", 15, "bold"),
            fg="#ffffff",
            bg="#1e293b",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Setup wizard  •  version " + VERSION,
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1e293b",
        ).pack(anchor="w", pady=(3, 0))

    def _build_body(self):
        card = tk.Frame(
            self.root,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#e5e7eb",
            padx=24,
            pady=20,
        )
        card.pack(fill="both", expand=True, padx=26, pady=20)

        tk.Label(
            card,
            text="Install location",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#111827",
        ).pack(anchor="w")
        entry = tk.Entry(
            card,
            textvariable=self.install_dir,
            font=("Segoe UI", 9),
            bg="#f9fafb",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#d1d5db",
        )
        entry.pack(fill="x", ipady=5, pady=(4, 16))

        tk.Label(
            card,
            text="Options",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#111827",
        ).pack(anchor="w", pady=(0, 4))
        for var, text in (
            (self.desktop_shortcut, "Create a shortcut on the Desktop"),
            (self.start_menu, "Add shortcuts to the Start Menu"),
            (self.launch, "Launch the app when installation finishes"),
        ):
            tk.Checkbutton(
                card,
                text=text,
                variable=var,
                font=("Segoe UI", 9),
                bg="#ffffff",
                fg="#374151",
                activebackground="#ffffff",
                activeforeground="#374151",
                selectcolor="#ffffff",
                anchor="w",
                bd=0,
            ).pack(fill="x", pady=2)

        self.progress.pack(fill="x", pady=(20, 6))
        tk.Label(
            card,
            textvariable=self.status,
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#0369a1",
        ).pack(anchor="w")

    def _build_footer(self):
        footer = tk.Frame(self.root, bg="#f3f4f6", pady=14)
        footer.pack(fill="x")
        tk.Button(
            footer,
            text="Cancel",
            font=("Segoe UI", 10),
            bg="#e5e7eb",
            fg="#111827",
            activebackground="#d1d5db",
            bd=0,
            padx=24,
            pady=8,
            cursor="hand2",
            command=self.root.destroy,
        ).pack(side="right", padx=(0, 26))
        self.install_btn = tk.Button(
            footer,
            text="Install",
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            bd=0,
            padx=30,
            pady=8,
            cursor="hand2",
            command=self.start_install,
        )
        self.install_btn.pack(side="right")

    def start_install(self):
        self.install_btn.config(state="disabled", text="Installing...")
        self.progress["value"] = 0
        self.installer = Installer(
            self.install_dir.get().strip(),
            desktop_shortcut=self.desktop_shortcut.get(),
            start_menu=self.start_menu.get(),
            launch=self.launch.get(),
        )
        self.installer.root = self.root
        self.installer.progress = self.progress
        self.installer.status = self.status
        threading.Thread(target=self.installer.run, daemon=True).start()
        self.root.after(150, self._watch)

    def _watch(self):
        if self.installer is None:
            return
        if self.installer.done:
            self._finish()
        elif self.installer.error is not None:
            self.status.set(f"Installation failed: {self.installer.error}")
            self.install_btn.config(state="normal", text="Retry")
        else:
            self.root.after(150, self._watch)

    def _finish(self):
        self.status.set("Installation complete!")
        self.install_btn.config(
            state="normal",
            text="Launch app",
            bg="#16a34a",
            activebackground="#15803d",
            command=self.launch_app,
        )

    def launch_app(self):
        app_exe = os.path.join(self.install_dir.get().strip(), APP_EXE)
        if os.path.isfile(app_exe):
            subprocess.Popen([app_exe], cwd=os.path.dirname(app_exe))
        self.root.destroy()


# --------------------------------------------------------------------------- entry
def silent_install():
    installer = Installer(default_install_dir())
    installer.run()
    if installer.error:
        print(f"ERROR: {installer.error}")
        return 1
    print(f"Installed to {installer.install_dir}")
    return 0


def main():
    if "--silent" in sys.argv:
        return silent_install()

    window = SetupWindow()
    return 0


if __name__ == "__main__":
    sys.exit(main())
