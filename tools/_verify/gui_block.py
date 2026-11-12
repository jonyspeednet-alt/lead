# ----------------- MODERN GUI DESIGN -----------------
BG = "#f3f4f6"
CARD_BG = "#ffffff"
BORDER = "#e5e7eb"
INK = "#111827"
MUTED = "#6b7280"
ACCENT = "#2563eb"

root = tk.Tk()
root.title("Google Drive Automation Studio")
root.configure(bg=BG)

# responsive start size - the whole app fits on screen, no scrollbar
screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
max_h = max(640, screen_h - 70)          # never taller than the screen
COMPACT = screen_h < 900 or os.environ.get("DRIVE_COMPACT") == "1"
PAD_X = 12 if COMPACT else 14
PAD_Y = 5 if COMPACT else 10
HEAD_PADY = 5 if COMPACT else 8
ENTRY_PADY = 2 if COMPACT else 4
CARD_GAP = 3 if COMPACT else 5
TITLE_FONT = ("Segoe UI", 13 if COMPACT else 15, "bold")
CARD_FONT = ("Segoe UI", 9 if COMPACT else 10, "bold")
HINT_FONT = ("Segoe UI", 7 if COMPACT else 8, "italic")
BODY_FONT = ("Segoe UI", 8 if COMPACT else 9)
ENTRY_FONT = ("Segoe UI", 9 if COMPACT else 10)

root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

try:
    if getattr(sys, "frozen", False):
        root.iconbitmap(sys.executable)
except Exception:
    pass

CURRENT_EMAILS = []
CURRENT_PARSED = {"found": 0, "valid": [], "invalid": [], "dropped": [], "limited": False}
WRAPPABLE = []
pos_x = 0
pos_y = 0


# --------------------------------------------------------------------------- previews
def update_plan_preview():
    """Live summary of how many e-mails the current folder count will use."""
    try:
        n = int(folder_count.get())
    except ValueError:
        n = 0
    valid = CURRENT_PARSED.get("valid", [])
    if n <= 0:
        plan_hint.set(f"Set the number of folders (1-{MAX_FOLDERS}).")
        return
    if not valid:
        plan_hint.set(f"Each folder receives the next {PER_FOLDER} e-mails from the list below.")
        return
    usable = min(n * PER_FOLDER, len(valid))
    left = len(valid) - usable
    dropped = len(CURRENT_PARSED.get("dropped", []))
    if left > 0:
        text = (f"{n} folder(s) x {PER_FOLDER} = {usable:,} e-mail(s) will be shared - "
                f"{left:,} left over for the next run.")
    else:
        text = (f"{n} folder(s) x {PER_FOLDER} = {usable:,} e-mail(s) will be shared - "
                "the whole list is used.")
    if dropped:
        text += f" ({dropped:,} more are over the {MAX_EMAILS} limit - they stay in the report)"
    plan_hint.set(text)


def update_folder_preview():
    count = len(FOLDER_NAMES)
    if count == 0:
        folder_preview.set("")
    elif count <= 3:
        folder_preview.set(", ".join(FOLDER_NAMES))
    else:
        folder_preview.set(
            f"{FOLDER_NAMES[0]} ... {FOLDER_NAMES[-1]}   ({count} folders - use 'Rename folders' to customise)"
        )


def open_rename_dialog():
    """Edit the folder names in a separate window so the main one stays compact."""
    window = tk.Toplevel(root)
    window.title("Rename folders")
    window.geometry("560x470")
    window.configure(bg=BG)
    window.transient(root)

    window.grid_columnconfigure(0, weight=1)
    window.grid_rowconfigure(0, weight=1)

    list_holder = tk.Frame(window, bg=BG)
    list_holder.grid(row=0, column=0, sticky="nsew", padx=14, pady=(14, 6))
    list_holder.grid_columnconfigure(0, weight=1)
    list_holder.grid_rowconfigure(0, weight=1)

    canvas = tk.Canvas(list_holder, bg=BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(list_holder, orient="vertical", command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))

    inner = tk.Frame(canvas, bg=BG)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    window_item = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.itemconfig(window_item, width=e.width))
    canvas.configure(yscrollcommand=scrollbar.set)

    name_vars = [tk.StringVar(value=name) for name in FOLDER_NAMES]
    for index, var in enumerate(name_vars):
        row = tk.Frame(inner, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=f"Folder {index + 1}:", width=10, anchor="w",
                 font=("Segoe UI", 9), bg=BG, fg=MUTED).pack(side="left")
        tk.Entry(row, textvariable=var, font=("Segoe UI", 10), bg=CARD_BG, relief="flat",
                 highlightthickness=1, highlightbackground="#d1d5db").pack(
            side="left", fill="x", expand=True, ipady=3)

    def apply_names():
        global FOLDER_NAMES
        FOLDER_NAMES = [
            var.get().strip() or f"Folder {index + 1}" for index, var in enumerate(name_vars)
        ]
        for entry_var, name in zip(FOLDER_ENTRIES, FOLDER_NAMES):
            entry_var.set(name)
        update_folder_preview()
        window.destroy()

    footer = tk.Frame(window, bg=BG)
    footer.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
    tk.Button(footer, text="Cancel", font=("Segoe UI", 10), bg="#e5e7eb", fg=INK, bd=0,
              padx=20, pady=7, cursor="hand2", command=window.destroy).pack(side="right")
    tk.Button(footer, text="Apply names", font=("Segoe UI", 10, "bold"), bg=ACCENT, fg="#ffffff",
              activebackground="#1d4ed8", bd=0, padx=20, pady=7, cursor="hand2",
              command=apply_names).pack(side="right", padx=(0, 10))


# --------------------------------------------------------------------------- header
header_frame = tk.Frame(root, bg="#1e293b", padx=20, pady=(14 if not COMPACT else 8))
header_frame.grid(row=0, column=0, sticky="ew")

title_lbl = tk.Label(header_frame, text="⚡ Google Drive Automation", font=TITLE_FONT,
                     fg="#ffffff", bg="#1e293b")
title_lbl.pack(anchor="w")
if not COMPACT:
    sub_lbl = tk.Label(header_frame, text="Auto Login, Create Folders, Upload Files & Share with Team",
                        font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
    sub_lbl.pack(anchor="w", pady=(2, 0))

body_frame = tk.Frame(root, bg=BG)
body_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(10 if not COMPACT else 6))
body_frame.grid_columnconfigure(0, weight=1)


def create_card(parent, title, hint=""):
    card = tk.Frame(parent, bg=CARD_BG, bd=0, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="x", pady=CARD_GAP)

    head = tk.Frame(card, bg=CARD_BG, padx=PAD_X, pady=HEAD_PADY)
    head.pack(fill="x")
    tk.Label(head, text=title, font=CARD_FONT, fg=INK, bg=CARD_BG).pack(side="left")
    if hint:
        tk.Label(head, text=hint, font=HINT_FONT, fg=MUTED, bg=CARD_BG).pack(side="right")

    separator = tk.Frame(card, bg=BORDER, height=1)
    separator.pack(fill="x")

    body = tk.Frame(card, bg=CARD_BG, padx=PAD_X, pady=PAD_Y)
    body.pack(fill="x")
    return body


def section_title(parent, text):
    tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"), bg=CARD_BG,
             fg="#374151").pack(anchor="w", pady=(0, 2))


def section_rule(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(6, 6))


# --------------------------------------------------------------------------- sections
def build_credentials(parent):
    """Render the credential fields into the given parent (no card wrapper)."""
    global entry_user, entry_pass
    holder = tk.Frame(parent, bg=CARD_BG)
    holder.pack(fill="x")
    c = holder
    c.grid_columnconfigure(1, weight=1)

    tk.Label(c, text="Gmail Address", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").grid(row=0, column=0, sticky="w", padx=(0, 10))
    entry_user = tk.Entry(c, font=ENTRY_FONT, bg="#f9fafb", relief="flat", highlightthickness=1,
                          highlightbackground="#d1d5db", highlightcolor=ACCENT)
    entry_user.grid(row=0, column=1, sticky="ew", ipady=ENTRY_PADY)

    tk.Label(c, text="Password", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(6, 0))
    entry_pass = tk.Entry(c, font=ENTRY_FONT, show="•", bg="#f9fafb", relief="flat",
                          highlightthickness=1, highlightbackground="#d1d5db", highlightcolor=ACCENT)
    entry_pass.grid(row=1, column=1, sticky="ew", ipady=ENTRY_PADY, pady=(6, 0))
    return c


def build_folder_section(parent):
    global folder_count, folder_preview, plan_hint
    folder_row = tk.Frame(parent, bg=CARD_BG)
    folder_row.pack(fill="x")

    left_box = tk.Frame(folder_row, bg=CARD_BG)
    left_box.pack(side="left")
    tk.Label(left_box, text="Total Folders:", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").pack(side="left")
    folder_count = tk.Entry(left_box, width=6, font=("Segoe UI", 10), justify="center",
                            bg="#f9fafb", relief="flat", highlightthickness=1,
                            highlightbackground="#d1d5db")
    folder_count.pack(side="left", padx=8, ipady=2)
    folder_count.insert(0, "1")
    set_btn = tk.Button(left_box, text="Set Quantity", font=("Segoe UI", 9, "bold"), bg="#f1f5f9",
                         fg="#0f172a", activebackground="#e2e8f0", bd=0, padx=12, pady=4,
                         cursor="hand2", command=rebuild_folders)
    set_btn.pack(side="left")

    rename_btn = tk.Button(folder_row, text="Rename folders...", font=("Segoe UI", 9, "bold"),
                           bg="#f1f5f9", fg="#0f172a", activebackground="#e2e8f0", bd=0, padx=12,
                           pady=4, cursor="hand2", command=open_rename_dialog)
    rename_btn.pack(side="right")

    folder_preview = tk.StringVar(value="")
    preview_label = tk.Label(parent, textvariable=folder_preview, font=HINT_FONT, bg=CARD_BG,
                             fg=MUTED, anchor="w")
    preview_label.pack(fill="x", pady=(5, 0))
    WRAPPABLE.append(preview_label)

    plan_hint = tk.StringVar(value=f"Each folder receives the next {PER_FOLDER} e-mails from the list below.")
    plan_hint_label = tk.Label(parent, textvariable=plan_hint, font=BODY_FONT, bg=CARD_BG,
                               fg="#0369a1", anchor="w")
    plan_hint_label.pack(fill="x", pady=(2, 0))
    WRAPPABLE.append(plan_hint_label)


def build_file_section(parent):
    global content_file_path
    content_file_path = tk.StringVar()
    file_row = tk.Frame(parent, bg=CARD_BG)
    file_row.pack(fill="x")
    entry_file = tk.Entry(file_row, textvariable=content_file_path, font=BODY_FONT, bg="#f9fafb",
                          relief="flat", highlightthickness=1, highlightbackground="#d1d5db")
    entry_file.pack(side="left", fill="x", expand=True, ipady=ENTRY_PADY)

    def browse_content():
        chosen = filedialog.askopenfilename(title="Select file to upload into every folder")
        if chosen:
            content_file_path.set(chosen)

    browse_btn = tk.Button(file_row, text="Browse...", font=("Segoe UI", 9, "bold"), bg="#0284c7",
                           fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff",
                           bd=0, padx=14, pady=4, cursor="hand2", command=browse_content)
    browse_btn.pack(side="right", padx=(8, 0))


def build_email_section(parent):
    global email_file_path, email_info
    email_file_path = tk.StringVar()
    email_row = tk.Frame(parent, bg=CARD_BG)
    email_row.pack(fill="x")
    entry_emails_file = tk.Entry(email_row, textvariable=email_file_path, font=BODY_FONT,
                                 bg="#f9fafb", relief="flat", highlightthickness=1,
                                 highlightbackground="#d1d5db", state="readonly")
    entry_emails_file.pack(side="left", fill="x", expand=True, ipady=ENTRY_PADY)

    browse_emails_btn = tk.Button(email_row, text="Browse...", font=("Segoe UI", 9, "bold"),
                                   bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                                   activeforeground="#ffffff", bd=0, padx=14, pady=4,
                                   cursor="hand2", command=choose_email_file)
    browse_emails_btn.pack(side="right", padx=(8, 0))

    email_info = tk.StringVar(value="No file selected yet.")
    email_info_label = tk.Label(parent, textvariable=email_info, font=BODY_FONT, bg=CARD_BG,
                                fg="#0369a1", anchor="w")
    email_info_label.pack(fill="x", pady=(5, 0))
    WRAPPABLE.append(email_info_label)

    general_row = tk.Frame(parent, bg=CARD_BG)
    general_row.pack(fill="x", pady=(4, 0))
    tk.Label(general_row, text="General Access:", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").pack(side="left")
    tk.Label(general_row, text="✓ Anyone with the link can view", font=HINT_FONT,
             bg=CARD_BG, fg="#16a34a").pack(side="left", padx=(8, 0))


def build_report_card(parent):
    global report_info, view_report_btn, export_report_btn
    c = create_card(parent, "📊 Run Report")
    report_info = tk.StringVar(value="Run the automation to generate a report.")
    report_info_label = tk.Label(c, textvariable=report_info, font=BODY_FONT, bg=CARD_BG,
                                 fg=MUTED, anchor="w")
    report_info_label.pack(fill="x", pady=(0, 6))
    WRAPPABLE.append(report_info_label)

    report_row = tk.Frame(c, bg=CARD_BG)
    report_row.pack(fill="x")
    view_report_btn = tk.Button(report_row, text="View Report", font=("Segoe UI", 9, "bold"),
                                 bg="#f1f5f9", fg="#0f172a", activebackground="#e2e8f0", bd=0,
                                 padx=16, pady=5, cursor="hand2", state="disabled",
                                 command=open_report_window)
    view_report_btn.pack(side="left")
    export_report_btn = tk.Button(report_row, text="Download Excel Report",
                                  font=("Segoe UI", 9, "bold"), bg="#0f766e", fg="#ffffff",
                                  activebackground="#115e59", bd=0, padx=16, pady=5,
                                  cursor="hand2", state="disabled", command=export_report)
    export_report_btn.pack(side="left", padx=(10, 0))
    return c


# --------------------------------------------------------------------------- assemble
if COMPACT:
    combined = create_card(body_frame, "⚙ Setup", f"{PER_FOLDER} e-mails per folder")
    section_title(combined, "Google account")
    build_credentials(combined)
    section_rule(combined)
    section_title(combined, "Folder setup")
    build_folder_section(combined)
    section_rule(combined)
    section_title(combined, "File to upload into every folder")
    build_file_section(combined)
    section_rule(combined)
    section_title(combined, "Office e-mail list (.txt / .csv / .xlsx)")
    build_email_section(combined)
else:
    c1 = create_card(body_frame, "🔑 Google Account Credentials")
    build_credentials(c1)

    c2 = create_card(body_frame, "📁 Folder Management")
    build_folder_section(c2)

    c3 = create_card(body_frame, "📤 File Upload (Optional)", "uploaded into every created folder")
    build_file_section(c3)

    c4 = create_card(body_frame, "👥 Office E-mail List (File)", f"{PER_FOLDER} e-mails per folder")
    build_email_section(c4)

build_report_card(body_frame)

# --------------------------------------------------------------------------- action area
action_frame = tk.Frame(root, bg=BG)
action_frame.grid_columnconfigure(0, weight=1)
if COMPACT:
    # on short screens the action bar follows the cards directly, so the
    # Start button stays reachable even if the window is cut off
    action_frame.pack(fill="x", pady=(8, 0), in_=body_frame)
else:
    action_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 12))

status = tk.StringVar(value="Ready to execute")
status_card = tk.Frame(action_frame, bg="#e0f2fe", highlightthickness=1,
                       highlightbackground="#bae6fd", padx=12, pady=6)
status_card.grid(row=0, column=0, sticky="ew")
tk.Label(status_card, text="Status:", font=("Segoe UI", 9, "bold"), bg="#e0f2fe",
         fg="#0369a1").pack(side="left")
status_label = tk.Label(status_card, textvariable=status, font=("Segoe UI", 9), bg="#e0f2fe",
                        fg="#0c4a6e", justify="left", anchor="w")
status_label.pack(side="left", padx=6, fill="x", expand=True)
WRAPPABLE.append(status_label)

btn = tk.Button(
    action_frame,
    text="🚀 Start Automation (Login & Create)",
    font=("Segoe UI", 11, "bold"),
    bg=ACCENT,
    fg="#ffffff",
    activebackground="#1d4ed8",
    activeforeground="#ffffff",
    bd=0,
    pady=8,
    cursor="hand2",
    command=on_submit,
)
btn.grid(row=1, column=0, sticky="ew", pady=(6, 0))


def copy_status():
    text = status.get()
    text += "\n\nLog file: " + current_log_path()
    if RUN_LOG_LINES:
        text += "\n\n--- LOG ---\n" + "\n".join(RUN_LOG_LINES[-80:])
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    set_status(status, "Status log copied to the clipboard.")


copy_btn = tk.Button(
    action_frame,
    text="📋 Copy Current Status Log",
    font=("Segoe UI", 8),
    bg=BG,
    fg=MUTED,
    activebackground="#e5e7eb",
    bd=0,
    cursor="hand2",
    command=copy_status,
)
copy_btn.grid(row=2, column=0, sticky="e", pady=(3, 0))


# --------------------------------------------------------------------------- responsiveness
def set_wrap(width):
    for label in WRAPPABLE:
        try:
            label.config(wraplength=max(240, width))
        except Exception:
            pass


fitted = {"done": False}


def ensure_fits():
    """Grow the window when the wrapped text needs more room than the client area."""
    try:
        client = root.winfo_height()
        needed = root.winfo_reqheight()
    except Exception:
        return
    if needed > client:
        target = min(needed + 12, max_h)
        if target > client:
            root.geometry(f"{root.winfo_width()}x{target}+{pos_x}+{pos_y}")


def shrink_to_fit():
    """Remove the leftover space once the window is on screen."""
    try:
        client = root.winfo_height()
        needed = root.winfo_reqheight()
    except Exception:
        return
    if needed and client - needed > 40:
        root.geometry(f"{root.winfo_width()}x{needed + 20}+{pos_x}+{pos_y}")


def on_resize(event):
    if event.widget is not root:
        return
    set_wrap(event.width - 90)
    ensure_fits()
    if not fitted["done"] and root.winfo_height() > 1:
        fitted["done"] = True
        root.after(400, shrink_to_fit)


root.bind("<Configure>", on_resize)
folder_count.bind("<Return>", lambda e: rebuild_folders())

# --- auto-fit: the window can never become smaller than the content ---------
win_w = max(620, min(980, screen_w - 120))
set_wrap(win_w - 90)
root.update_idletasks()

req_w = root.winfo_reqwidth()
req_h = root.winfo_reqheight()

win_h = min(max(req_h + 40, 600), max_h)
pos_x = max(0, (screen_w - win_w) // 2)
pos_y = max(0, min(40, (screen_h - win_h) // 3))
root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
root.update_idletasks()

root.minsize(max(560, req_w), max(600, req_h))

rebuild_folders()
root.update_idletasks()
ensure_fits()
root.mainloop()
