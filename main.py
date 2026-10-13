import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import re
import csv
import os
import hashlib
from datetime import datetime
import webbrowser
import sys


# ===================== COLORS =====================
COLORS = {
    "sidebar":       "#0f172a",
    "sidebar_hover": "#1e293b",
    "bg":            "#f1f5f9",
    "card":          "#ffffff",
    "primary":       "#2563eb",
    "primary_dark":  "#1d4ed8",
    "success":       "#10b981",
    "danger":        "#ef4444",
    "warning":       "#f59e0b",
    "purple":        "#8b5cf6",
    "text":          "#0f172a",
    "text_light":    "#64748b",
    "border":        "#e2e8f0",
}


# ===================== DATABASE =====================
class Database:
    def __init__(self, db_name="students.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.seed_admin()

    def create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                gpa REAL NOT NULL,
                course TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def seed_admin(self):
        cur = self.conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            self.conn.execute(
                "INSERT INTO users VALUES (?, ?)",
                ("admin", self.hash_password("admin123"))
            )
            self.conn.commit()

    @staticmethod
    def hash_password(pw):
        return hashlib.sha256(pw.encode()).hexdigest()

    def check_login(self, username, password):
        cur = self.conn.execute(
            "SELECT password_hash FROM users WHERE username=?",
            (username,)
        )
        row = cur.fetchone()
        return row is not None and row[0] == self.hash_password(password)

    def change_password(self, username, new_pw):
        self.conn.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (self.hash_password(new_pw), username)
        )
        self.conn.commit()

    def add(self, sid, name, email, gpa, course):
        try:
            self.conn.execute(
                "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
                (sid, name, email, gpa, course,
                 datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            self.conn.commit()
            return True, "Student added successfully."
        except sqlite3.IntegrityError as e:
            if "student_id" in str(e):
                return False, "Student ID already exists."
            if "email" in str(e):
                return False, "Email already registered."
            return False, str(e)

    def update(self, sid, name, email, gpa, course):
        try:
            cur = self.conn.execute(
                "UPDATE students SET name=?, email=?, gpa=?, course=? WHERE student_id=?",
                (name, email, gpa, course, sid)
            )
            self.conn.commit()
            if cur.rowcount == 0:
                return False, "Student not found."
            return True, "Student updated successfully."
        except sqlite3.IntegrityError:
            return False, "Email already used by another student."

    def delete(self, sid):
        cur = self.conn.execute("DELETE FROM students WHERE student_id=?", (sid,))
        self.conn.commit()
        if cur.rowcount == 0:
            return False, "Student not found."
        return True, "Student deleted successfully."

    def get_all(self, keyword=""):
        if keyword:
            p = f"%{keyword}%"
            cur = self.conn.execute(
                "SELECT * FROM students WHERE student_id LIKE ? OR name LIKE ? "
                "OR email LIKE ? OR course LIKE ? ORDER BY name",
                (p, p, p, p)
            )
        else:
            cur = self.conn.execute("SELECT * FROM students ORDER BY name")
        return cur.fetchall()

    def get_one(self, sid):
        cur = self.conn.execute(
            "SELECT * FROM students WHERE student_id=?", (sid,))
        return cur.fetchone()

    def exists(self, sid):
        cur = self.conn.execute(
            "SELECT 1 FROM students WHERE student_id=?", (sid,))
        return cur.fetchone() is not None

    def stats(self):
        cur = self.conn.execute(
            "SELECT COUNT(*) AS total, AVG(gpa) AS avg_gpa FROM students")
        row = cur.fetchone()
        total = row["total"] or 0
        avg = row["avg_gpa"] or 0.0
        cur2 = self.conn.execute(
            "SELECT COUNT(DISTINCT course) AS c FROM students WHERE course <> ''")
        courses = cur2.fetchone()["c"] or 0
        return total, avg, courses

    def gpa_distribution(self):
        buckets = {"0.0-1.0": 0, "1.0-2.0": 0, "2.0-3.0": 0,
                   "3.0-3.5": 0, "3.5-4.0": 0}
        cur = self.conn.execute("SELECT gpa FROM students")
        for r in cur.fetchall():
            g = r["gpa"]
            if g < 1.0:   buckets["0.0-1.0"] += 1
            elif g < 2.0: buckets["1.0-2.0"] += 1
            elif g < 3.0: buckets["2.0-3.0"] += 1
            elif g < 3.5: buckets["3.0-3.5"] += 1
            else:         buckets["3.5-4.0"] += 1
        return buckets

    def course_distribution(self):
        cur = self.conn.execute(
            "SELECT course, COUNT(*) c FROM students WHERE course <> '' "
            "GROUP BY course ORDER BY c DESC")
        return [(r["course"], r["c"]) for r in cur.fetchall()]


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
def valid_email(e):
    return bool(EMAIL_RE.match(e))


# ===================== FLAT BUTTON =====================
class FlatButton(tk.Button):
    def __init__(self, parent, text, command=None, bg=COLORS["primary"],
                 fg="white", hover=None, width=14, height=1,
                 font=("Segoe UI", 9, "bold")):
        hover = hover or self._darken(bg)
        super().__init__(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            relief="flat", bd=0, cursor="hand2",
            font=font, width=width, height=height,
            highlightthickness=0
        )
        self.default_bg = bg
        self.hover_bg = hover
        self.bind("<Enter>", lambda e: self.config(bg=self.hover_bg))
        self.bind("<Leave>", lambda e: self.config(bg=self.default_bg))

    @staticmethod
    def _darken(hex_color, factor=0.85):
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = int(r*factor), int(g*factor), int(b*factor)
        return f"#{r:02x}{g:02x}{b:02x}"


# ===================== LOGIN WINDOW =====================
class LoginWindow:
    def __init__(self, root, db, on_success):
        self.root = root
        self.db = db
        self.on_success = on_success

        self.root.title("CodeNova • Login")
        self.root.configure(bg=COLORS["sidebar"])
        self.root.resizable(False, False)

        self._center_window()
        self._build()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 400, 460
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        tk.Label(self.root, text="◆", bg=COLORS["sidebar"], fg=COLORS["primary"],
                 font=("Segoe UI", 30)).pack(pady=(35, 3))
        tk.Label(self.root, text="CodeNova", bg=COLORS["sidebar"],
                 fg="white", font=("Segoe UI", 20, "bold")).pack()
        tk.Label(self.root, text="Student Management System",
                 bg=COLORS["sidebar"], fg="#94a3b8",
                 font=("Segoe UI", 9)).pack(pady=(2, 22))

        card = tk.Frame(self.root, bg="white")
        card.pack(padx=35, fill="x", ipady=15)

        tk.Label(card, text="Sign In", bg="white", fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=22, pady=(12, 2))
        tk.Label(card, text="Enter your credentials to continue",
                 bg="white", fg=COLORS["text_light"],
                 font=("Segoe UI", 8)).pack(anchor="w", padx=22, pady=(0, 12))

        tk.Label(card, text="Username", bg="white", fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(5, 3))
        self.e_user = tk.Entry(card, font=("Segoe UI", 10), bd=0, bg="#f8fafc",
                               highlightthickness=1,
                               highlightbackground=COLORS["border"],
                               highlightcolor=COLORS["primary"])
        self.e_user.pack(fill="x", padx=22, ipady=6)
        self.e_user.insert(0, "admin")

        tk.Label(card, text="Password", bg="white", fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(10, 3))
        self.e_pass = tk.Entry(card, show="•", font=("Segoe UI", 10), bd=0,
                               bg="#f8fafc", highlightthickness=1,
                               highlightbackground=COLORS["border"],
                               highlightcolor=COLORS["primary"])
        self.e_pass.pack(fill="x", padx=22, ipady=6)
        self.e_pass.insert(0, "admin123")

        FlatButton(card, "SIGN IN", self.login,
                   bg=COLORS["primary"], width=20).pack(pady=16)

        tk.Label(card, text="Default: admin / admin123",
                 bg="white", fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "italic")).pack(pady=(0, 10))

        self.e_pass.bind("<Return>", lambda e: self.login())

    def login(self):
        u = self.e_user.get().strip()
        p = self.e_pass.get().strip()
        if not u or not p:
            messagebox.showerror("Error", "Both fields are required.")
            return
        if self.db.check_login(u, p):
            self.root.destroy()
            self.on_success(u)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")


# ===================== MAIN APP =====================
class App:
    def __init__(self, root, db, username):
        self.root = root
        self.db = db
        self.username = username
        self.selected_id = None

        self.root.title(f"CodeNova  •  Student Management System  —  {username}")
        self.root.geometry("1050x640")
        self.root.minsize(950, 580)
        self.root.configure(bg=COLORS["bg"])

        self._setup_style()
        self._build_sidebar()
        self._build_main()
        self.refresh_table()
        self.update_stats()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Modern.Treeview",
            background=COLORS["card"], fieldbackground=COLORS["card"],
            foreground=COLORS["text"], rowheight=28, borderwidth=0,
            font=("Segoe UI", 9))
        style.configure("Modern.Treeview.Heading",
            background="#f8fafc", foreground=COLORS["text_light"],
            font=("Segoe UI", 9, "bold"), relief="flat", padding=(6, 6))
        style.map("Modern.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "white")])

    # ============ SIDEBAR ============
    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=COLORS["sidebar"], width=175)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = tk.Frame(sidebar, bg=COLORS["sidebar"])
        logo.pack(fill="x", pady=(18, 12))
        tk.Label(logo, text="◆  CodeNova", bg=COLORS["sidebar"],
                 fg="white", font=("Segoe UI", 13, "bold")).pack()
        tk.Label(logo, text="Batch 01 • Python Track",
                 bg=COLORS["sidebar"], fg="#94a3b8",
                 font=("Segoe UI", 8)).pack(pady=(2, 0))

        ub = tk.Frame(sidebar, bg=COLORS["sidebar_hover"])
        ub.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(ub, text="👤", bg=COLORS["sidebar_hover"], fg="#cbd5e1",
                 font=("Segoe UI", 10)).pack(side="left", padx=(8, 6), pady=6)
        tk.Label(ub, text=self.username, bg=COLORS["sidebar_hover"],
                 fg="#e2e8f0", font=("Segoe UI", 9, "bold")).pack(side="left")

        menu = [
            ("🏠", "Dashboard",    self.show_dashboard),
            ("🎓", "All Students", self.show_all),
            ("👁️", "View Details", self.view_details),
            ("➕", "Add New",      self.focus_form),
            ("📤", "Export CSV",   self.export_csv),
            ("🖨️", "Report",       self.generate_report),
            ("📊", "Charts",       self.show_charts),
            ("🔒", "Change Pass",  self.change_password),
            ("⚙️", "About",        self.show_about),
        ]
        for icon, label, cmd in menu:
            self._nav_item(sidebar, icon, label, cmd)

        FlatButton(sidebar, "⎋  LOGOUT", self.logout,
                   bg=COLORS["danger"], width=14).pack(side="bottom", pady=12, padx=12)

    def _nav_item(self, parent, icon, label, cmd):
        frame = tk.Frame(parent, bg=COLORS["sidebar"], cursor="hand2")
        frame.pack(fill="x", padx=10, pady=1)
        inner = tk.Frame(frame, bg=COLORS["sidebar"])
        inner.pack(fill="x", padx=8, pady=6)
        tk.Label(inner, text=icon, bg=COLORS["sidebar"], fg="#cbd5e1",
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        tk.Label(inner, text=label, bg=COLORS["sidebar"], fg="#cbd5e1",
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        def on_enter(e):
            frame.config(bg=COLORS["sidebar_hover"])
            inner.config(bg=COLORS["sidebar_hover"])
            for w in inner.winfo_children():
                w.config(bg=COLORS["sidebar_hover"])
        def on_leave(e):
            frame.config(bg=COLORS["sidebar"])
            inner.config(bg=COLORS["sidebar"])
            for w in inner.winfo_children():
                w.config(bg=COLORS["sidebar"])
        def on_click(e):
            if cmd: cmd()

        for w in (frame, inner, *inner.winfo_children()):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

    # ============ MAIN AREA ============
    def _build_main(self):
        main = tk.Frame(self.root, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        header = tk.Frame(main, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="Student Records", bg=COLORS["bg"],
                 fg=COLORS["text"], font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="Manage, search and update student data",
                 bg=COLORS["bg"], fg=COLORS["text_light"],
                 font=("Segoe UI", 9)).pack(side="left", padx=12, pady=(6, 0))

        stats = tk.Frame(main, bg=COLORS["bg"])
        stats.pack(fill="x", pady=(0, 10))
        self.card_total   = self._stat_card(stats, "Total Students", "0",    "🎓", COLORS["primary"])
        self.card_avg     = self._stat_card(stats, "Average GPA",    "0.00", "📊", COLORS["success"])
        self.card_courses = self._stat_card(stats, "Courses",         "0",    "📚", COLORS["warning"])

        content = tk.Frame(main, bg=COLORS["bg"])
        content.pack(fill="both", expand=True)

        # LEFT: form
        form_card = tk.Frame(content, bg=COLORS["card"], width=280,
                             highlightthickness=1, highlightbackground=COLORS["border"])
        form_card.pack(side="left", fill="y", padx=(0, 12))
        form_card.pack_propagate(False)

        hdr = tk.Frame(form_card, bg=COLORS["card"])
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(hdr, text="Student Information", bg=COLORS["card"],
                 fg=COLORS["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Fill the fields below", bg=COLORS["card"],
                 fg=COLORS["text_light"], font=("Segoe UI", 8)).pack(anchor="w")

        fields = tk.Frame(form_card, bg=COLORS["card"])
        fields.pack(fill="x", padx=16)
        self.entry_id     = self._form_field(fields, "Student ID")
        self.entry_name   = self._form_field(fields, "Full Name")
        self.entry_email  = self._form_field(fields, "Email Address")
        self.entry_gpa    = self._form_field(fields, "GPA (0.0 - 4.0)")
        self.entry_course = self._form_field(fields, "Course")

        # Buttons (bottom-anchored)
        btn_box = tk.Frame(form_card, bg=COLORS["card"])
        btn_box.pack(side="bottom", fill="x", padx=16, pady=12)

        FlatButton(btn_box, "＋   ADD STUDENT",    self.add_student,
                   bg=COLORS["success"]).pack(fill="x", pady=(0, 4))
        FlatButton(btn_box, "✎   UPDATE STUDENT", self.update_student,
                   bg=COLORS["primary"]).pack(fill="x", pady=4)

        row2 = tk.Frame(btn_box, bg=COLORS["card"])
        row2.pack(fill="x", pady=(4, 0))
        FlatButton(row2, "👁  VIEW", self.view_details,
                   bg=COLORS["purple"], width=5).pack(
                       side="left", fill="x", expand=True, padx=(0, 2))
        FlatButton(row2, "🗑  DEL", self.delete_student,
                   bg=COLORS["danger"], width=5).pack(
                       side="left", fill="x", expand=True, padx=2)
        FlatButton(row2, "↺  CLR", self.clear_form,
                   bg="#64748b", width=5).pack(
                       side="left", fill="x", expand=True, padx=(2, 0))

        # RIGHT: table
        table_card = tk.Frame(content, bg=COLORS["card"],
                              highlightthickness=1, highlightbackground=COLORS["border"])
        table_card.pack(side="right", fill="both", expand=True)

        top = tk.Frame(table_card, bg=COLORS["card"])
        top.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(top, text="All Students", bg=COLORS["card"],
                 fg=COLORS["text"], font=("Segoe UI", 11, "bold")).pack(side="left")

        search_frame = tk.Frame(top, bg=COLORS["card"])
        search_frame.pack(side="right")
        tk.Label(search_frame, text="🔍  Search:",
                 bg=COLORS["card"], fg=COLORS["text_light"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))

        sbox = tk.Frame(search_frame, bg="#f1f5f9",
                        highlightthickness=1, highlightbackground=COLORS["border"])
        sbox.pack(side="left")
        self.entry_search = tk.Entry(sbox, bd=0, bg="#f1f5f9",
                                     font=("Segoe UI", 9), width=18,
                                     fg=COLORS["text"], insertbackground=COLORS["text"])
        self.entry_search.pack(padx=8, pady=5)
        self.entry_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        FlatButton(search_frame, "✕", self.show_all,
                   bg="#64748b", width=3,
                   font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 0))

        tree_frame = tk.Frame(table_card, bg=COLORS["card"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        cols = ("ID", "Name", "Email", "GPA", "Course", "Created")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 style="Modern.Treeview")
        for c in cols:
            self.tree.heading(c, text=c.upper())
        self.tree.column("ID",      width=60,  anchor="w", stretch=False)
        self.tree.column("Name",    width=120, anchor="w", stretch=False)
        self.tree.column("Email",   width=160, anchor="w", stretch=False)
        self.tree.column("GPA",     width=50,  anchor="center", stretch=False)
        self.tree.column("Course",  width=110, anchor="w", stretch=False)
        self.tree.column("Created", width=110, anchor="w", stretch=False)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", lambda e: self.view_details())

        # Status bar
        self.status = tk.Label(self.root, text="● Ready",
                               bg=COLORS["bg"], fg=COLORS["text_light"],
                               anchor="w", font=("Segoe UI", 8), padx=14)
        self.status.pack(side="bottom", fill="x")

    def _stat_card(self, parent, title, value, icon, accent):
        card = tk.Frame(parent, bg=COLORS["card"],
                        highlightthickness=1, highlightbackground=COLORS["border"])
        card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        left = tk.Frame(card, bg=COLORS["card"])
        left.pack(side="left", padx=12, pady=8)
        tk.Label(left, text=title, bg=COLORS["card"],
                 fg=COLORS["text_light"], font=("Segoe UI", 8)).pack(anchor="w")
        val_lbl = tk.Label(left, text=value, bg=COLORS["card"],
                           fg=COLORS["text"], font=("Segoe UI", 16, "bold"))
        val_lbl.pack(anchor="w")
        right = tk.Frame(card, bg=accent, width=38, height=38)
        right.pack(side="right", padx=12)
        right.pack_propagate(False)
        tk.Label(right, text=icon, bg=accent, fg="white",
                 font=("Segoe UI", 14)).pack(expand=True)
        return val_lbl

    def _form_field(self, parent, label):
        tk.Label(parent, text=label, bg=COLORS["card"], fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(5, 2))
        entry = tk.Entry(parent, font=("Segoe UI", 9), bd=0,
                         bg="#f8fafc", fg=COLORS["text"],
                         highlightthickness=1,
                         highlightbackground=COLORS["border"],
                         highlightcolor=COLORS["primary"],
                         insertbackground=COLORS["text"])
        entry.pack(fill="x", ipady=5)
        return entry

    def set_status(self, msg, kind="ok"):
        colors = {"ok": COLORS["success"], "err": COLORS["danger"],
                  "info": COLORS["text_light"]}
        self.status.config(text=f"● {msg}", fg=colors.get(kind, COLORS["text_light"]))

    # ============ CRUD ============
    def validate(self):
        sid    = self.entry_id.get().strip()
        name   = self.entry_name.get().strip()
        email  = self.entry_email.get().strip()
        gpa_s  = self.entry_gpa.get().strip()
        course = self.entry_course.get().strip()

        if not sid:
            return None, "Student ID is required."
        if not re.match(r"^[A-Za-z0-9_-]+$", sid):
            return None, "ID: only letters, numbers, _ and - allowed."
        if len(name) < 2:
            return None, "Name must be at least 2 characters."
        if not valid_email(email):
            return None, "Enter a valid email address."
        try:
            gpa = float(gpa_s)
        except ValueError:
            return None, "GPA must be a number."
        if gpa < 0 or gpa > 4:
            return None, "GPA must be between 0.0 and 4.0."

        return (sid, name, email, gpa, course), None

    def add_student(self):
        data, err = self.validate()
        if err:
            messagebox.showerror("Validation Error", err)
            self.set_status(err, "err"); return
        ok, msg = self.db.add(*data)
        if ok:
            self.set_status(msg, "ok"); self.clear_form()
            self.refresh_table(); self.update_stats()
        else:
            messagebox.showerror("Error", msg); self.set_status(msg, "err")

    def update_student(self):
        # ID chahe row select kar ke aaye ya user type kare
        sid = self.entry_id.get().strip()
        if not sid:
            messagebox.showwarning("Warning",
                "Enter Student ID in form OR select a row from table to update.")
            return

        # Check karo ke student exist karta hai
        if not self.db.exists(sid):
            messagebox.showerror("Not Found",
                f"Student ID '{sid}' not found.\n"
                "Please enter a valid ID or select a row.")
            self.set_status(f"ID '{sid}' not found.", "err")
            return

        data, err = self.validate()
        if err:
            messagebox.showerror("Validation Error", err)
            self.set_status(err, "err")
            return

        ok, msg = self.db.update(*data)
        if ok:
            self.set_status(msg, "ok")
            self.clear_form()
            self.refresh_table()
            self.update_stats()
        else:
            messagebox.showerror("Error", msg)
            self.set_status(msg, "err")

    def delete_student(self):
        sid = self.selected_id or self.entry_id.get().strip()
        if not sid:
            messagebox.showwarning("Warning",
                "Select a row OR enter Student ID to delete.")
            return
        if not self.db.exists(sid):
            messagebox.showerror("Not Found", f"Student ID '{sid}' not found.")
            return
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete student '{sid}'?"):
            return
        ok, msg = self.db.delete(sid)
        if ok:
            self.set_status(msg, "ok"); self.clear_form()
            self.refresh_table(); self.update_stats()
        else:
            messagebox.showerror("Error", msg); self.set_status(msg, "err")

    def clear_form(self):
        for e in (self.entry_id, self.entry_name, self.entry_email,
                  self.entry_gpa, self.entry_course):
            e.delete(0, tk.END)
        self.selected_id = None
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())
        self.set_status("Form cleared.", "info")

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        rows = self.db.get_all(self.entry_search.get().strip())
        for r in rows:
            self.tree.insert("", "end", values=(
                r["student_id"], r["name"], r["email"],
                f"{r['gpa']:.2f}", r["course"], r["created_at"]
            ))
        self.set_status(f"{len(rows)} record(s) shown.", "info")

    def update_stats(self):
        total, avg, courses = self.db.stats()
        self.card_total.config(text=str(total))
        self.card_avg.config(text=f"{avg:.2f}")
        self.card_courses.config(text=str(courses))

    def on_row_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        v = self.tree.item(sel[0], "values")
        self.selected_id = v[0]
        widgets = [self.entry_id, self.entry_name, self.entry_email,
                   self.entry_gpa, self.entry_course]
        for w, val in zip(widgets, v[:5]):
            w.delete(0, tk.END); w.insert(0, val)
        self.set_status(f"Selected: {v[0]}  —  Edit fields and click UPDATE.", "info")

    # ============ VIEW DETAILS ============
    def view_details(self):
        # Pehle selected row, warna form field se ID
        sel = self.tree.selection()
        if sel:
            sid = self.tree.item(sel[0], "values")[0]
        else:
            sid = self.entry_id.get().strip()

        if not sid:
            messagebox.showwarning("View Details",
                "Please select a student from the table\n"
                "OR enter Student ID in the form.")
            return

        row = self.db.get_one(sid)
        if not row:
            messagebox.showerror("Not Found",
                f"Student ID '{sid}' not found.")
            return

        # Popup
        win = tk.Toplevel(self.root)
        win.title(f"Student Details — {row['student_id']}")
        win.geometry("460x440")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        head = tk.Frame(win, bg=COLORS["purple"], height=70)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="👤", bg=COLORS["purple"], fg="white",
                 font=("Segoe UI", 22)).pack(side="left", padx=(20, 12), pady=15)
        tinfo = tk.Frame(head, bg=COLORS["purple"])
        tinfo.pack(side="left", pady=14)
        tk.Label(tinfo, text=row["name"], bg=COLORS["purple"], fg="white",
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(tinfo, text=f"ID: {row['student_id']}",
                 bg=COLORS["purple"], fg="#e9d5ff",
                 font=("Segoe UI", 9)).pack(anchor="w")

        body = tk.Frame(win, bg="white")
        body.pack(fill="both", expand=True, padx=25, pady=18)

        def info_line(label, value, color=COLORS["text"]):
            f = tk.Frame(body, bg="white")
            f.pack(fill="x", pady=6)
            tk.Label(f, text=label, bg="white", fg=COLORS["text_light"],
                     font=("Segoe UI", 9, "bold"), width=14,
                     anchor="w").pack(side="left")
            tk.Label(f, text=value, bg="white", fg=color,
                     font=("Segoe UI", 10), anchor="w",
                     wraplength=280, justify="left").pack(side="left", fill="x")

        info_line("Student ID:", row["student_id"])
        info_line("Full Name:",  row["name"])
        info_line("Email:",      row["email"])

        gpa = row["gpa"]
        if gpa >= 3.5:
            gpa_color = COLORS["success"]
        elif gpa >= 2.5:
            gpa_color = COLORS["warning"]
        else:
            gpa_color = COLORS["danger"]
        info_line("GPA:", f"{gpa:.2f} / 4.00", gpa_color)

        info_line("Course:",
                  row["course"] if row["course"] else "— Not assigned —")
        info_line("Enrolled On:", row["created_at"])

        btns = tk.Frame(win, bg="white")
        btns.pack(fill="x", padx=25, pady=(5, 18))

        def load_to_form():
            w = [self.entry_id, self.entry_name, self.entry_email,
                 self.entry_gpa, self.entry_course]
            vals = [row["student_id"], row["name"], row["email"],
                    f"{row['gpa']:.2f}", row["course"]]
            for widget, v in zip(w, vals):
                widget.delete(0, tk.END)
                widget.insert(0, v)
            self.selected_id = row["student_id"]
            self.set_status(
                f"Loaded '{row['student_id']}' into form. Edit and click UPDATE.",
                "info")
            win.destroy()

        FlatButton(btns, "✎  LOAD TO FORM", load_to_form,
                   bg=COLORS["primary"], width=14).pack(side="left", padx=(0, 6))
        FlatButton(btns, "Close", win.destroy,
                   bg="#64748b", width=10).pack(side="left")

    # ============ EXPORT CSV ============
    def export_csv(self):
        rows = self.db.get_all()
        if not rows:
            messagebox.showwarning("Export", "No records to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"students_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Student ID", "Name", "Email",
                                 "GPA", "Course", "Created At"])
                for r in rows:
                    writer.writerow([r["student_id"], r["name"], r["email"],
                                     r["gpa"], r["course"], r["created_at"]])
            self.set_status(f"Exported to {os.path.basename(path)}", "ok")
            if messagebox.askyesno("Export Successful",
                                   f"Saved to:\n{path}\n\nOpen file now?"):
                self._open_file(path)
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    # ============ REPORT ============
    def generate_report(self):
        rows = self.db.get_all()
        if not rows:
            messagebox.showwarning("Report", "No records to report.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if not path: return

        total, avg, courses = self.db.stats()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("=" * 65 + "\n")
                f.write("        STUDENT RECORDS REPORT\n")
                f.write("        CodeNova Batch 01 - Python Track\n")
                f.write("=" * 65 + "\n")
                f.write(f"Generated On   : {datetime.now().strftime('%d %b %Y, %H:%M')}\n")
                f.write(f"Generated By   : {self.username}\n")
                f.write(f"Total Students : {total}\n")
                f.write(f"Average GPA    : {avg:.2f}\n")
                f.write(f"Total Courses  : {courses}\n")
                f.write("=" * 65 + "\n\n")
                f.write(f"{'ID':<8}{'Name':<22}{'Email':<28}{'GPA':<6}{'Course':<15}\n")
                f.write("-" * 80 + "\n")
                for r in rows:
                    f.write(f"{r['student_id']:<8}{r['name'][:20]:<22}"
                            f"{r['email'][:26]:<28}{r['gpa']:<6.2f}"
                            f"{r['course'][:14]:<15}\n")
                f.write("-" * 80 + "\n")
                f.write(f"\n— End of Report —\n")
            self.set_status("Report generated.", "ok")
            if messagebox.askyesno("Report Ready",
                                   f"Saved to:\n{path}\n\nOpen now?"):
                self._open_file(path)
        except Exception as e:
            messagebox.showerror("Report Failed", str(e))

    def _open_file(self, path):
        try:
            if sys.platform.startswith("darwin"):
                os.system(f'open "{path}"')
            elif os.name == "nt":
                os.startfile(path)
            else:
                webbrowser.open(f"file://{path}")
        except Exception:
            messagebox.showinfo("Info", f"Open manually:\n{path}")

    # ============ CHARTS ============
    def show_charts(self):
        total, _, _ = self.db.stats()
        if total == 0:
            messagebox.showwarning("Charts", "No data to visualize.")
            return

        win = tk.Toplevel(self.root)
        win.title("Charts — Analytics")
        win.geometry("820x520")
        win.configure(bg=COLORS["bg"])
        win.transient(self.root)

        tk.Label(win, text="📊  Analytics Dashboard", bg=COLORS["bg"],
                 fg=COLORS["text"], font=("Segoe UI", 14, "bold")).pack(pady=(14, 4))
        tk.Label(win, text="Visual overview of student data",
                 bg=COLORS["bg"], fg=COLORS["text_light"],
                 font=("Segoe UI", 9)).pack(pady=(0, 10))

        container = tk.Frame(win, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=15, pady=8)

        c1 = tk.Frame(container, bg="white",
                      highlightthickness=1, highlightbackground=COLORS["border"])
        c1.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(c1, text="GPA Distribution", bg="white",
                 fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))

        canvas = tk.Canvas(c1, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        c1.after(80, lambda: self._draw_gpa_chart(canvas))

        c2 = tk.Frame(container, bg="white",
                      highlightthickness=1, highlightbackground=COLORS["border"])
        c2.pack(side="right", fill="both", expand=True, padx=(8, 0))

        tk.Label(c2, text="Course Distribution", bg="white",
                 fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))

        canvas2 = tk.Canvas(c2, bg="white", highlightthickness=0)
        canvas2.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        c2.after(80, lambda: self._draw_course_chart(canvas2))

        FlatButton(win, "Close", win.destroy, bg="#64748b",
                   width=12).pack(pady=10)

    def _draw_gpa_chart(self, canvas):
        canvas.delete("all")
        data = self.db.gpa_distribution()
        labels = list(data.keys())
        values = list(data.values())
        max_v = max(values) if values else 1
        if max_v == 0: max_v = 1

        w = canvas.winfo_width() or 350
        h = canvas.winfo_height() or 320
        pad_l, pad_b, pad_t, pad_r = 32, 42, 15, 15

        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        n = len(labels)
        bar_w = chart_w / n * 0.55
        gap = chart_w / n

        canvas.create_line(pad_l, pad_t, pad_l, h - pad_b, fill="#cbd5e1")
        canvas.create_line(pad_l, h - pad_b, w - pad_r, h - pad_b, fill="#cbd5e1")

        for i in range(5):
            y = pad_t + chart_h * i / 4
            canvas.create_line(pad_l, y, w - pad_r, y,
                               fill="#f1f5f9", dash=(3, 3))
            val = max_v - (max_v * i / 4)
            canvas.create_text(pad_l - 6, y, text=f"{int(val)}",
                               anchor="e", fill="#94a3b8",
                               font=("Segoe UI", 7))

        colors = ["#ef4444", "#f59e0b", "#facc15", "#10b981", "#2563eb"]

        for i, (label, val) in enumerate(zip(labels, values)):
            x = pad_l + gap * i + (gap - bar_w) / 2
            bar_h = (val / max_v) * chart_h
            y = h - pad_b - bar_h
            color = colors[i % len(colors)]

            canvas.create_rectangle(x, y, x + bar_w, h - pad_b,
                                    fill=color, outline="")
            if val > 0:
                canvas.create_text(x + bar_w / 2, y - 7, text=str(val),
                                   fill=COLORS["text"],
                                   font=("Segoe UI", 8, "bold"))
            canvas.create_text(x + bar_w / 2, h - pad_b + 12,
                               text=label, fill="#64748b",
                               font=("Segoe UI", 7))

    def _draw_course_chart(self, canvas):
        canvas.delete("all")
        data = self.db.course_distribution()
        if not data:
            canvas.create_text(150, 130, text="No course data",
                               fill="#94a3b8", font=("Segoe UI", 9))
            return
        total = sum(v for _, v in data)
        w = canvas.winfo_width() or 350
        h = canvas.winfo_height() or 320
        cx, cy, r = w // 2, h // 2 + 5, min(w, h) // 2 - 45
        colors = ["#2563eb", "#10b981", "#f59e0b", "#ef4444",
                  "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]

        start = 90
        for i, (label, count) in enumerate(data[:8]):
            extent = -360 * (count / total)
            color = colors[i % len(colors)]
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                              start=start, extent=extent,
                              fill=color, outline="white", width=2)
            start += extent

        lx, ly = 10, 10
        for i, (label, count) in enumerate(data[:5]):
            color = colors[i % len(colors)]
            canvas.create_rectangle(lx, ly, lx + 10, ly + 10,
                                    fill=color, outline="")
            canvas.create_text(lx + 15, ly + 5,
                               text=f"{label} ({count})", anchor="w",
                               fill=COLORS["text"], font=("Segoe UI", 7))
            ly += 17

    # ============ CHANGE PASSWORD ============
    def change_password(self):
        win = tk.Toplevel(self.root)
        win.title("Change Password")
        win.geometry("350x300")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="🔒  Change Password", bg="white",
                 fg=COLORS["text"], font=("Segoe UI", 13, "bold")).pack(pady=(18, 4))
        tk.Label(win, text="Enter your current and new password",
                 bg="white", fg=COLORS["text_light"],
                 font=("Segoe UI", 8)).pack(pady=(0, 14))

        tk.Label(win, text="Current Password", bg="white",
                 fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=32, pady=(0, 3))
        e_old = tk.Entry(win, show="•", font=("Segoe UI", 9), bd=0, bg="#f8fafc",
                         highlightthickness=1, highlightbackground=COLORS["border"])
        e_old.pack(fill="x", padx=32, ipady=5)

        tk.Label(win, text="New Password", bg="white",
                 fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=32, pady=(10, 3))
        e_new = tk.Entry(win, show="•", font=("Segoe UI", 9), bd=0, bg="#f8fafc",
                         highlightthickness=1, highlightbackground=COLORS["border"])
        e_new.pack(fill="x", padx=32, ipady=5)

        tk.Label(win, text="Confirm New Password", bg="white",
                 fg=COLORS["text_light"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=32, pady=(10, 3))
        e_cnf = tk.Entry(win, show="•", font=("Segoe UI", 9), bd=0, bg="#f8fafc",
                         highlightthickness=1, highlightbackground=COLORS["border"])
        e_cnf.pack(fill="x", padx=32, ipady=5)

        def save():
            old = e_old.get().strip()
            new = e_new.get().strip()
            cnf = e_cnf.get().strip()
            if not old or not new or not cnf:
                messagebox.showerror("Error", "All fields are required."); return
            if len(new) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters."); return
            if new != cnf:
                messagebox.showerror("Error", "New passwords do not match."); return
            if not self.db.check_login(self.username, old):
                messagebox.showerror("Error", "Current password is incorrect."); return
            self.db.change_password(self.username, new)
            messagebox.showinfo("Success", "Password changed successfully.")
            win.destroy()

        FlatButton(win, "SAVE", save, bg=COLORS["primary"],
                   width=18).pack(pady=16)

    # ============ MISC ============
    def focus_form(self):
        self.entry_id.focus_set()

    def show_all(self):
        self.entry_search.delete(0, tk.END)
        self.refresh_table()

    def show_dashboard(self):
        self.set_status("Dashboard is up to date.", "info")
        self.update_stats()

    def show_about(self):
        messagebox.showinfo(
            "About",
            "Student Record Management System\n"
            "CodeNova Batch 01 — Python Internship\n\n"
            "Features: Login, CRUD, View Details, Search,\n"
            "Export CSV, Reports, Charts, Password Change\n\n"
            "Built with Python + Tkinter + SQLite\n"
            "Version 2.1.0"
        )

    def logout(self):
        if not messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            return
        self.root.destroy()
        start_app()


# ===================== BOOT =====================
def start_app():
    root = tk.Tk()
    db = Database()

    def on_login(username):
        root2 = tk.Tk()
        App(root2, db, username)
        root2.mainloop()

    LoginWindow(root, db, on_login)
    root.mainloop()


if __name__ == "__main__":
    start_app()