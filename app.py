import json
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import config, pattern_store, pattern_extractor
from core import handwriting_ocr, question_fitter, ai_provider, pdf_generator, docx_generator, printing, gemini_llm

CLASSES = ["Pre-NC A", "Pre-NC", "NC", "KG"] + [str(i) for i in range(1, 9)]
EXAM_TYPES = ["Unit Test 1", "Unit Test 2", "Half Yearly Exam", "Annual Exam"]
SUBJECTS = ["Hindi", "English", "Mathematics", "Science", "Social Studies", "Sanskrit", "EVS", "Other"]

# Fallback used whenever a pattern comes back with no header_fields -- this
# happens legitimately whenever the photo(s) given don't include the header
# box itself (e.g. photos starting straight from Section A), so there's
# genuinely nothing there to read. Rather than leaving it empty (which would
# print a paper with no header line at all), default to the standard set
# every one of this school's papers has used so far.
DEFAULT_HEADER_FIELDS = ["School Name", "Class", "Subject", "Roll No", "Date"]

# ---------------------------------------------------------------------------
# Color palette -- a modern indigo/slate theme. Every screen pulls colors
# only from these names, so the whole app's look can be re-tuned from one
# place. "_LIGHT" tints are for badges/hover backgrounds; "_HOVER" is the
# pressed/hovered shade of a solid-colored button.
# ---------------------------------------------------------------------------
BG = "#eef1f8"
CARD_BG = "#ffffff"
BORDER = "#dbe2f0"
TEXT_DARK = "#1e2433"
MUTED = "#64748b"

ACCENT = "#4f46e5"
ACCENT_HOVER = "#4338ca"
ACCENT_LIGHT = "#e9e7fb"

GOOD = "#15803d"
GOOD_LIGHT = "#dcfce7"

WARN = "#b91c1c"
WARN_LIGHT = "#fee2e2"

INFO = "#0369a1"
INFO_LIGHT = "#e0f2fe"

# Consistent spacing scale used throughout the GUI instead of ad-hoc numbers.
PAD_XL = 28
PAD_L = 18
PAD_M = 12
PAD_S = 6

# Small icon touches so screens don't read as plain black-and-white forms.
CLASS_ICONS = {"Pre-NC A": "🧸", "Pre-NC": "🎈", "NC": "🧩", "KG": "✏️"}
EXAM_ICONS = {
    "Unit Test 1": "📝", "Unit Test 2": "🗒️",
    "Half Yearly Exam": "📅", "Annual Exam": "🏆",
}


def _shade(hex_color: str, amount: float) -> str:
    """Lighten (amount > 0) or darken (amount < 0) a '#rrggbb' color by a
    fraction. Used to auto-derive a hover color from whatever background a
    button already has, so buttons get a real hover reaction without each
    one needing its own hand-picked hover color."""
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) != 6:
        return hex_color or CARD_BG
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def adjust(c):
        c = c + (255 - c) * amount if amount >= 0 else c * (1 + amount)
        return max(0, min(255, int(c)))

    r, g, b = adjust(r), adjust(g), adjust(b)
    return f"#{r:02x}{g:02x}{b:02x}"


_LIGHT_BGS = {"white", "#ffffff", CARD_BG.lower(), BG.lower()}


def _polish_buttons(root):
    """Recursively give every tk.Button under `root` a real hover reaction
    and a consistent flat look, WITHOUT touching each individual
    Button(...) call site -- called once, right after each screen (or
    dialog) finishes building its widget tree. Colored buttons darken
    slightly on hover; near-white buttons pick up a light accent tint
    instead (darkening white is barely visible)."""
    for child in root.winfo_children():
        if isinstance(child, tk.Button):
            try:
                base = child.cget("bg")
            except tk.TclError:
                base = None
            if base:
                is_light = base.lower() in _LIGHT_BGS
                hover = ACCENT_LIGHT if is_light else _shade(base, -0.12)
                child.configure(relief="flat", bd=0,
                                 highlightthickness=1 if is_light else 0,
                                 highlightbackground=BORDER, highlightcolor=BORDER)

                def _enter(_e, w=child, h=hover):
                    if str(w["state"]) != "disabled":
                        w.config(bg=h)

                def _leave(_e, w=child, n=base):
                    if str(w["state"]) != "disabled":
                        w.config(bg=n)

                child.bind("<Enter>", _enter)
                child.bind("<Leave>", _leave)
        if child.winfo_children():
            _polish_buttons(child)


def class_label(c: str) -> str:
    """'Class 5' for numeric classes, but the pre-primary names (Pre-NC A,
    Pre-NC, NC, KG) are shown as-is -- "Class KG" would read oddly."""
    return f"Class {c}" if c.isdigit() else c


def all_known_subjects():
    """SUBJECTS plus any subject a pattern has already been saved under --
    e.g. a school-specific subject like "COMPUTER" that was never in the
    base list. Used as suggestions in a combobox that stays freely typable,
    so a subject outside the base list is never unreachable once it's been
    used at least once (locking these to a fixed dropdown was a real bug:
    it made already-in-use subjects like "COMPUTER" impossible to select
    when managing/overwriting their pattern)."""
    extra = sorted({t["subject"] for t in pattern_store.list_all_templates()
                     if t["subject"] not in SUBJECTS})
    return SUBJECTS + extra


def apply_pattern_defaults(pattern: dict) -> dict:
    """Fill in sensible defaults for fields that came back empty -- most
    commonly header_fields, which legitimately can't be read if the photo(s)
    given don't include the header box itself (e.g. photos starting
    straight from Section A rather than the top of page 1). Leaving it
    empty would print a paper with no header line at all, which is worse
    than falling back to the standard set every one of this school's
    patterns has used so far."""
    if not pattern.get("header_fields"):
        pattern["header_fields"] = list(DEFAULT_HEADER_FIELDS)
    return pattern


class QPApp(tk.Tk):
    def __init__(self):
        super().__init__()
        config.apply_tesseract_path()
        self.title("School Question Paper Generator (Offline)")
        self.geometry("980x720")
        self.minsize(880, 640)
        self.configure(bg=BG)

        # "clam" is the one built-in ttk theme that actually honors color
        # overrides cross-platform -- the default Windows theme ("vista")
        # renders comboboxes/scrollbars natively and mostly ignores style
        # colors, which is why they'd otherwise look untouched no matter
        # what's configured below.
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=CARD_BG, background=CARD_BG,
                         foreground=TEXT_DARK, arrowcolor=ACCENT, bordercolor=BORDER,
                         lightcolor=CARD_BG, darkcolor=CARD_BG, padding=4)
        style.map("TCombobox",
                  fieldbackground=[("readonly", CARD_BG)],
                  bordercolor=[("focus", ACCENT)])
        style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=BG,
                         arrowcolor=MUTED, bordercolor=BG, lightcolor=BORDER, darkcolor=BORDER)
        style.configure("TScrollbar", gripcount=0)

        self.sel_class = None
        self.sel_exam_type = None
        self.sel_subject = None

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.show_frame(HomeScreen)

    def show_frame(self, frame_cls, **kwargs):
        for widget in self.container.winfo_children():
            widget.destroy()
        frame = frame_cls(self.container, self, **kwargs)
        frame.pack(fill="both", expand=True)
        _polish_buttons(frame)  # give every button on this screen a hover reaction, in one pass


class BaseScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

    def header(self, title, show_back=None):
        # Thin colored strip along the very top of every screen -- a small
        # touch that keeps the app from reading as an all-white/grey form,
        # and doubles as a subtle "brand" accent across every screen.
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x", side="top")

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", pady=(PAD_L, PAD_M), padx=PAD_XL)
        if show_back:
            tk.Button(top, text="←  Back", command=show_back, relief="flat", bg=BG, fg=MUTED,
                      font=("Segoe UI", 10), padx=10, pady=6, cursor="hand2").pack(side="left", padx=(0, PAD_M))
        tk.Label(top, text=title, font=("Segoe UI", 17, "bold"), bg=BG, fg=TEXT_DARK).pack(
            side="left", expand=True, fill="x")
        tk.Button(top, text="⚙  Settings", command=lambda: self.app.show_frame(SettingsScreen),
                  relief="flat", bg=BG, fg=MUTED, font=("Segoe UI", 10), padx=10, pady=6,
                  cursor="hand2").pack(side="right", padx=(PAD_S, 0))
        tk.Button(top, text="📚 Manage Patterns", command=lambda: self.app.show_frame(PatternsHubScreen),
                  relief="flat", bg=ACCENT_LIGHT, fg=ACCENT, font=("Segoe UI", 10, "bold"), padx=12, pady=6,
                  cursor="hand2").pack(side="right")
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", padx=PAD_XL, pady=(0, PAD_M))


class HomeScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("📄  Select a Class")

        n_learned = len(pattern_store.list_all_templates())
        hub_card = tk.Frame(self, bg=ACCENT_LIGHT, highlightbackground=BORDER, highlightthickness=1)
        hub_card.pack(fill="x", padx=PAD_XL, pady=(0, PAD_L))
        inner = tk.Frame(hub_card, bg=ACCENT_LIGHT)
        inner.pack(fill="x", padx=PAD_L, pady=PAD_M)
        tk.Label(inner, text="📚 Manage Patterns", font=("Segoe UI", 12, "bold"),
                 bg=ACCENT_LIGHT, fg=ACCENT).pack(side="left")
        subtitle = (f"{n_learned} pattern(s) already learned -- reuse them instantly"
                     if n_learned else "Learn a pattern once per class + exam + subject, reuse it forever")
        tk.Label(inner, text=subtitle, font=("Segoe UI", 9), bg=ACCENT_LIGHT, fg=MUTED).pack(
            side="left", padx=(PAD_M, 0))
        tk.Button(inner, text="Open →", bg=ACCENT, fg="white", font=("Segoe UI", 10, "bold"),
                  padx=14, pady=6, relief="flat", cursor="hand2",
                  command=lambda: app.show_frame(PatternsHubScreen)).pack(side="right")

        tk.Label(self, text="Choose a class to begin:", bg=BG, font=("Segoe UI", 10), fg=MUTED).pack(
            anchor="w", padx=PAD_XL, pady=(PAD_S, 0))

        grid = tk.Frame(self, bg=BG)
        grid.pack(pady=PAD_L, padx=PAD_L)
        for i, c in enumerate(CLASSES):
            icon = CLASS_ICONS.get(c, "📘")
            tile = tk.Button(grid, text=f"{icon}\n{class_label(c)}", width=12, height=3,
                              font=("Segoe UI", 11), bg=CARD_BG, fg=TEXT_DARK, relief="flat",
                              cursor="hand2", justify="center",
                              command=lambda c=c: self.pick_class(c))
            tile.grid(row=i // 4, column=i % 4, padx=10, pady=10)

    def pick_class(self, c):
        self.app.sel_class = c
        self.app.show_frame(ExamTypeScreen)


class ExamTypeScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header(f"{class_label(app.sel_class)} — Select Exam Type", show_back=lambda: app.show_frame(HomeScreen))
        grid = tk.Frame(self, bg=BG)
        grid.pack(pady=PAD_XL)
        for i, et in enumerate(EXAM_TYPES):
            icon = EXAM_ICONS.get(et, "📝")
            tile = tk.Button(grid, text=f"{icon}   {et}", width=24, height=3, font=("Segoe UI", 11),
                              bg=CARD_BG, fg=TEXT_DARK, relief="flat", cursor="hand2",
                              command=lambda et=et: self.pick_exam(et))
            tile.grid(row=i // 2, column=i % 2, padx=14, pady=14)

    def pick_exam(self, et):
        self.app.sel_exam_type = et
        self.app.show_frame(SubjectScreen)


class SubjectScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header(f"{class_label(app.sel_class)} — {app.sel_exam_type} — Subject",
                     show_back=lambda: app.show_frame(ExamTypeScreen))
        body = tk.Frame(self, bg=BG)
        body.pack(pady=PAD_XL * 2)
        tk.Label(body, text="Choose a subject:", bg=BG, font=("Segoe UI", 11)).pack(pady=(0, PAD_M))
        self.subject_var = tk.StringVar(value=SUBJECTS[0])
        ttk.Combobox(body, textvariable=self.subject_var, values=all_known_subjects(), width=30).pack(pady=PAD_S)
        tk.Button(body, text="Continue", bg=ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
                  padx=16, pady=6, relief="flat", cursor="hand2",
                  command=self.cont).pack(pady=PAD_XL)

    def cont(self):
        subject = self.subject_var.get().strip()
        if not subject:
            messagebox.showwarning("Subject needed", "Please choose or type a subject.")
            return
        self.app.sel_subject = subject
        self.app.show_frame(ActionScreen)


class ActionScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        c, et, s = app.sel_class, app.sel_exam_type, app.sel_subject
        self.header(f"{class_label(c)} — {et} — {s}", show_back=lambda: app.show_frame(SubjectScreen))

        has_pattern = pattern_store.has_template(c, et, s)
        status = "✓ Pattern already learned for this combination" if has_pattern \
            else "No pattern learned yet — set one up first"
        tk.Label(self, text=status, bg=BG, font=("Segoe UI", 10, "italic"),
                 fg=GOOD if has_pattern else WARN).pack(pady=(0, PAD_XL))

        body = tk.Frame(self, bg=BG)
        body.pack(pady=PAD_M)
        tk.Button(body, text="Set / Update Pattern\n(upload sample paper photos)", width=34, height=3,
                  bg="white", relief="groove", cursor="hand2",
                  command=lambda: app.show_frame(PatternSetupScreen)).pack(pady=PAD_M)
        gen_btn = tk.Button(body, text="Generate New Question Paper", width=34, height=3, bg="white",
                             relief="groove", state="normal" if has_pattern else "disabled",
                             cursor="hand2" if has_pattern else "arrow",
                             command=lambda: app.show_frame(GenerateScreen))
        gen_btn.pack(pady=PAD_M)
        if not has_pattern:
            tk.Label(body, text="(set up the pattern first)", bg=BG, font=("Segoe UI", 9), fg=MUTED).pack()


class PatternSetupScreen(BaseScreen):
    """Reads sample paper photos offline (Tesseract), guesses a pattern with
    simple rules, then lets the teacher review/correct it as editable JSON
    before saving -- offline rule-based extraction is not as reliable as an
    AI reading it, so this review step matters."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        c, et, s = app.sel_class, app.sel_exam_type, app.sel_subject
        self.header(f"Learn Pattern — {class_label(c)} — {et} — {s}", show_back=lambda: app.show_frame(ActionScreen))
        tk.Label(self, text="Upload photo(s) of a SAMPLE question paper for this exam type.\n"
                             "This is a one-time setup per class + exam type.",
                 bg=BG, font=("Segoe UI", 10)).pack(pady=8)

        self.files = []
        self.files_label = tk.Label(self, text="No files selected", bg=BG, fg="#555",
                                     wraplength=700, justify="center")
        self.files_label.pack(pady=4)
        choose_row = tk.Frame(self, bg=BG)
        choose_row.pack(pady=4)
        tk.Button(choose_row, text="Choose Photo(s)...", command=self.choose_files).pack(side="left")
        tk.Button(choose_row, text="Clear", bg="white", relief="groove", cursor="hand2",
                  command=self.clear_files).pack(side="left", padx=(6, 0))
        tk.Label(self, text="Tip: click 'Choose Photo(s)...' once per photo if Ctrl/Shift-selecting "
                             "multiple at once doesn't work on your PC -- each pick adds to the list.",
                 bg=BG, font=("Segoe UI", 8), fg=MUTED, wraplength=600, justify="left").pack(pady=(0, 2))

        self.status_label = tk.Label(self, text="", bg=BG, font=("Segoe UI", 10, "italic"))
        self.status_label.pack(pady=6)

        read_row = tk.Frame(self, bg=BG)
        read_row.pack(pady=6)
        self.read_btn = tk.Button(read_row, text="Read Sample Paper(s) (local, offline)", bg=ACCENT, fg="white",
                                   font=("Segoe UI", 11, "bold"), command=self.read_samples)
        self.read_btn.pack(side="left")
        self.gemini_read_btn = tk.Button(read_row, text="📷 Read with Gemini (direct to JSON)", bg="white",
                                          relief="groove", cursor="hand2", command=self.read_samples_gemini)
        self.gemini_read_btn.pack(side="left", padx=(8, 0))
        tk.Label(self, text="Gemini reads the photo(s) straight into the pattern JSON below in one step -- "
                             "usually more accurate than the local reader, and not limited by any chat "
                             "upload/message limits, only your own Gemini API quota (needs an API key set "
                             "in Settings).",
                 bg=BG, font=("Segoe UI", 8), fg=MUTED, wraplength=650, justify="left").pack(pady=(2, 0))

        # Same-class + same-exam-type patterns are almost always identical
        # in structure across subjects (only the subject name differs) --
        # let the teacher copy an already-learned one straight in, instead
        # of re-photographing a sample paper and calling the AI again.
        existing = [t for t in pattern_store.list_all_templates()
                    if t["class_name"] == c and t["exam_type"] == et and t["subject"] != s]
        if existing:
            copy_wrap = tk.Frame(self, bg=BG)
            copy_wrap.pack(pady=(2, 10))
            tk.Label(copy_wrap, text="Or copy an already-learned pattern for this class + exam type "
                                      "(no photo or AI needed):",
                     bg=BG, font=("Segoe UI", 9), fg=MUTED).pack()
            copy_row = tk.Frame(copy_wrap, bg=BG)
            copy_row.pack(pady=4)
            self.copy_source_var = tk.StringVar(value=existing[0]["subject"])
            ttk.Combobox(copy_row, textvariable=self.copy_source_var,
                         values=[t["subject"] for t in existing], width=20, state="readonly").pack(
                side="left", padx=(0, 8))
            tk.Button(copy_row, text="Copy This Pattern", bg="white", relief="groove", cursor="hand2",
                      command=self.copy_existing_pattern).pack(side="left")

        school_row = tk.Frame(self, bg=BG)
        school_row.pack(pady=(4, 0))
        tk.Label(school_row, text="School:", bg=BG, font=("Segoe UI", 9, "bold")).pack(side="left")
        profiles = config.get("school_profiles") or []
        self.school_var = tk.StringVar(value=profiles[0]["name"] if profiles else "")
        ttk.Combobox(school_row, textvariable=self.school_var, values=[p["name"] for p in profiles],
                     width=24, state="readonly" if profiles else "normal").pack(side="left", padx=(6, 0))
        tk.Button(school_row, text="Apply to pattern below", bg="white", relief="groove", cursor="hand2",
                  command=self.apply_school_profile).pack(side="left", padx=(6, 0))
        if not profiles:
            tk.Label(school_row, text="(add school profiles in Settings)", bg=BG, font=("Segoe UI", 8),
                     fg=MUTED).pack(side="left", padx=(6, 0))

        tk.Label(self, text="Review / correct the detected pattern below, then save:",
                 bg=BG, font=("Segoe UI", 9)).pack(pady=(10, 2))
        self.text = tk.Text(self, height=16, width=90, wrap="word")
        self.text.pack(padx=16, pady=4, fill="both", expand=True)

        self.save_btn = tk.Button(self, text="Save Pattern", bg=ACCENT, fg="white",
                                   font=("Segoe UI", 11, "bold"), command=self.save_pattern, state="disabled")
        self.save_btn.pack(pady=10)

    def apply_school_profile(self):
        name = self.school_var.get().strip()
        if not name:
            messagebox.showwarning("No school selected",
                                    "Choose a school profile first (add one in Settings if none exist yet).")
            return
        match = next((p for p in (config.get("school_profiles") or []) if p.get("name") == name), None)
        if not match:
            messagebox.showwarning("Not found", "That school profile wasn't found -- check Settings.")
            return
        raw = self.text.get("1.0", "end").strip()
        if raw:
            try:
                pattern = json.loads(raw)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON",
                                      f"Please fix the JSON before applying a school profile:\n{e}")
                return
        else:
            pattern = {}
        pattern["school_name"] = match["name"]
        pattern["school_address"] = match.get("address", "")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", json.dumps(pattern, indent=2, ensure_ascii=False))
        self.save_btn.config(state="normal")

    def copy_existing_pattern(self):
        source_subject = self.copy_source_var.get()
        source_pattern = pattern_store.load_template(self.app.sel_class, self.app.sel_exam_type, source_subject)
        if not source_pattern:
            messagebox.showerror("Not found", "Couldn't load that pattern.")
            return
        cleaned = dict(source_pattern)
        # Drop instruction lines that just restate the OLD subject/class --
        # the header already shows the correct (new) subject/class
        # dynamically at generation time, so copying these verbatim would
        # print the wrong subject name on the new paper.
        old_instr = cleaned.get("general_instructions") or []
        new_instr = [line for line in old_instr
                     if not re.match(r"^\s*(subject|class)\s*[:\-]", str(line), re.IGNORECASE)]
        cleaned["general_instructions"] = new_instr
        self.text.delete("1.0", "end")
        self.text.insert("1.0", json.dumps(cleaned, indent=2, ensure_ascii=False))
        self.save_btn.config(state="normal")
        self.status_label.config(
            text=f"Copied the pattern from '{source_subject}'. Review below, then save "
                 f"-- no photo or AI was used.")

    def choose_files(self):
        files = filedialog.askopenfilenames(title="Select sample paper photos -- click again to "
                                                     "add more one at a time if needed",
                                             filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if isinstance(files, str):
            files = (files,) if files else ()
        added = 0
        for f in files:
            if f not in self.files:
                self.files.append(f)
                added += 1
        self._refresh_files_label(added, len(files))

    def _refresh_files_label(self, added, picked_this_time):
        if not self.files:
            self.files_label.config(text="No files selected")
            return
        names = [os.path.basename(p) for p in self.files]
        shown = ", ".join(names) if len(names) <= 4 else ", ".join(names[:4]) + f", +{len(names) - 4} more"
        note = ""
        if picked_this_time and added == 0:
            note = "  (that file's already in the list -- pick a different one to add more)"
        self.files_label.config(text=f"{len(self.files)} file(s) selected: {shown}{note}")

    def clear_files(self):
        self.files = []
        self.files_label.config(text="No files selected")

    def read_samples(self):
        if not self.files:
            messagebox.showwarning("No photos", "Please choose at least one sample paper photo.")
            return
        self.read_btn.config(state="disabled")
        self.gemini_read_btn.config(state="disabled")
        self.status_label.config(text="Reading sample paper(s) with local vision model...")

        def worker():
            try:
                model = config.get("ollama_vision_model") or handwriting_ocr.DEFAULT_MODEL
                raw_text = handwriting_ocr.read_printed_text_multi(self.files, model=model)
                pattern = pattern_extractor.extract_pattern(raw_text, self.app.sel_class, self.app.sel_exam_type)
                self.after(0, lambda: self.on_read_done(pattern))
            except Exception as e:
                self.after(0, lambda e=e: self.on_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def read_samples_gemini(self):
        if not self.files:
            messagebox.showwarning("No photos", "Please choose at least one sample paper photo.")
            return
        api_key = config.get("gemini_api_key")
        if not api_key:
            messagebox.showwarning(
                "No Gemini API key set",
                "Open Settings, paste in an API key from "
                "https://aistudio.google.com/app/apikey, and try again.")
            return
        self.read_btn.config(state="disabled")
        self.gemini_read_btn.config(state="disabled")
        self.status_label.config(text="Reading sample paper(s) with Gemini (needs internet)...")

        def worker():
            try:
                model = config.get("gemini_model") or gemini_llm.DEFAULT_MODEL
                pattern = gemini_llm.read_pattern_from_photos(
                    self.files, self.app.sel_class, self.app.sel_exam_type,
                    api_key=api_key, model=model)
                self.after(0, lambda: self.on_read_done(pattern))
            except Exception as e:
                self.after(0, lambda e=e: self.on_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_read_done(self, pattern):
        if not self.winfo_exists():
            return
        self.read_btn.config(state="normal")
        self.gemini_read_btn.config(state="normal")
        pattern = apply_pattern_defaults(pattern)
        self.status_label.config(text="Done. Please review and correct the pattern below.")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", json.dumps(pattern, indent=2, ensure_ascii=False))
        self.save_btn.config(state="normal")

    def on_error(self, e):
        if not self.winfo_exists():
            return
        self.read_btn.config(state="normal")
        self.gemini_read_btn.config(state="normal")
        self.status_label.config(text="")
        messagebox.showerror("Failed to read sample paper(s)", str(e))

    def save_pattern(self):
        try:
            pattern = json.loads(self.text.get("1.0", "end"))
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Please fix the JSON before saving:\n{e}")
            return
        pattern = apply_pattern_defaults(pattern)

        c, et, s = self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject
        existing = pattern_store.load_template(c, et, s)
        if existing:
            old_count = len(existing.get("sections") or [])
            new_count = len(pattern.get("sections") or [])
            # A pattern that's already been learned is meant to be
            # permanent/reusable -- re-running "Learn Pattern" from a
            # partial batch of photos (e.g. missing a page) can silently
            # overwrite a correct, complete pattern with a narrower one.
            # Flag it clearly rather than letting that happen quietly.
            if old_count and new_count < old_count:
                if not messagebox.askyesno(
                        "This pattern has fewer sections than before",
                        f"The pattern currently saved for {class_label(c)} - {et} - {s} has "
                        f"{old_count} section(s). The one you're about to save only has "
                        f"{new_count} -- likely because the photo(s) used this time didn't "
                        f"cover the whole paper.\n\n"
                        f"Overwrite the existing (more complete) pattern anyway?"):
                    return

        pattern_store.save_template(c, et, s, pattern)
        messagebox.showinfo("Pattern saved", "The paper pattern was saved successfully.")
        self.app.show_frame(ActionScreen)


class ManualPatternDialog(tk.Toplevel):
    """Lets a teacher paste a pattern JSON they already have (copied earlier
    from this app, a backup, or another machine) straight into the store --
    no photo, OCR, or AI call needed. Works whether a pattern already exists
    for this class+exam+subject (it's just overwritten after confirming) or
    whether nothing has been learned yet (it's created fresh).

    Two save paths are offered because a pattern's structure is usually
    identical across every subject for a given class+exam type -- so besides
    saving it for the one subject picked on the hub screen, it can also be
    stamped onto every subject in SUBJECTS in one click."""

    def __init__(self, parent, app, class_name, exam_type, subject, on_saved):
        super().__init__(parent)
        self.app = app
        self.class_name = class_name
        self.exam_type = exam_type
        self.on_saved = on_saved

        self.title("Add Pattern Manually")
        self.geometry("640x540")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=f"{class_label(class_name)} — {exam_type}",
                 bg=BG, font=("Segoe UI", 11, "bold"), fg=ACCENT).pack(pady=(PAD_M, 2))
        tk.Label(self, text="Paste the pattern JSON you copied earlier below, then save it either "
                             "just for the subject picked here, or for every subject in the list.",
                 bg=BG, font=("Segoe UI", 9), fg=MUTED, wraplength=600, justify="left").pack(
            padx=PAD_L, pady=(0, PAD_S))

        top_row = tk.Frame(self, bg=BG)
        top_row.pack(fill="x", padx=PAD_L)
        tk.Label(top_row, text="Subject:", bg=BG, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.subject_var = tk.StringVar(value=subject)
        # Editable (not readonly) with a dynamic suggestion list -- a fixed
        # readonly list would make an already-in-use custom subject (like
        # "COMPUTER") impossible to pick when overwriting its pattern here.
        ttk.Combobox(top_row, textvariable=self.subject_var, values=all_known_subjects(),
                     width=20).pack(side="left", padx=(PAD_S, 0))
        tk.Button(top_row, text="Paste from Clipboard", bg="white", relief="groove", cursor="hand2",
                  command=self.paste_clipboard).pack(side="right")

        school_row = tk.Frame(self, bg=BG)
        school_row.pack(fill="x", padx=PAD_L, pady=(PAD_S, 0))
        tk.Label(school_row, text="School:", bg=BG, font=("Segoe UI", 9, "bold")).pack(side="left")
        profiles = config.get("school_profiles") or []
        self.school_var = tk.StringVar(value=profiles[0]["name"] if profiles else "")
        ttk.Combobox(school_row, textvariable=self.school_var, values=[p["name"] for p in profiles],
                     width=24, state="readonly" if profiles else "normal").pack(side="left", padx=(6, 0))
        tk.Button(school_row, text="Apply to pattern above", bg="white", relief="groove", cursor="hand2",
                  command=self.apply_school_profile).pack(side="left", padx=(6, 0))

        self.text = tk.Text(self, height=18, width=76, wrap="word")
        self.text.pack(padx=PAD_L, pady=PAD_M, fill="both", expand=True)

        self.status_label = tk.Label(self, text="", bg=BG, font=("Segoe UI", 9, "italic"), fg=MUTED,
                                      wraplength=600, justify="left")
        self.status_label.pack(padx=PAD_L)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(PAD_S, PAD_L))
        tk.Button(btn_row, text="Save for This Subject", bg=ACCENT, fg="white", relief="flat",
                  padx=10, pady=6, cursor="hand2", command=self.save_for_subject).pack(side="left", padx=(0, PAD_M))
        tk.Button(btn_row, text="Save for All Subjects", bg="white", relief="groove",
                  padx=10, pady=6, cursor="hand2", command=self.save_for_all_subjects).pack(side="left")

    def paste_clipboard(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("Clipboard empty", "Nothing to paste from the clipboard.")
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", clip)
        self.status_label.config(text="Pasted from clipboard. Review it, then save.")

    def apply_school_profile(self):
        name = self.school_var.get().strip()
        if not name:
            messagebox.showwarning("No school selected",
                                    "Choose a school profile first (add one in Settings if none exist yet).")
            return
        match = next((p for p in (config.get("school_profiles") or []) if p.get("name") == name), None)
        if not match:
            messagebox.showwarning("Not found", "That school profile wasn't found -- check Settings.")
            return
        raw = self.text.get("1.0", "end").strip()
        if raw:
            try:
                pattern = json.loads(raw)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON",
                                      f"Please fix the JSON before applying a school profile:\n{e}")
                return
        else:
            pattern = {}
        pattern["school_name"] = match["name"]
        pattern["school_address"] = match.get("address", "")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", json.dumps(pattern, indent=2, ensure_ascii=False))
        self.status_label.config(text=f"Applied '{match['name']}' to the pattern above.")

    def _parse_pattern(self):
        raw = self.text.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Nothing to save", "Paste a pattern JSON first "
                                                        "(use the button above, or Ctrl+V into the box).")
            return None
        try:
            return apply_pattern_defaults(json.loads(raw))
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Please fix the JSON before saving:\n{e}")
            return None

    def _clean_for_subject(self, pattern):
        # Drop any general_instructions line that just restates a subject or
        # class (leftover raw text from whatever sample paper this JSON was
        # originally OCR'd from) -- the header's "Subject:" line is always
        # injected fresh from the dropdown at generation time, but a stray
        # instruction line like "Subject - English" is plain text and would
        # otherwise print verbatim on every subject's paper unchanged.
        cleaned = dict(pattern)
        old_instr = cleaned.get("general_instructions") or []
        new_instr = [line for line in old_instr
                     if not re.match(r"^\s*(subject|class)\s*[:\-]", str(line), re.IGNORECASE)]
        cleaned["general_instructions"] = new_instr
        return cleaned

    def save_for_subject(self):
        pattern = self._parse_pattern()
        if pattern is None:
            return
        subject = self.subject_var.get().strip()
        if not subject:
            messagebox.showwarning("Missing subject", "Please choose a subject.")
            return
        pattern = self._clean_for_subject(pattern)
        if pattern_store.has_template(self.class_name, self.exam_type, subject):
            if not messagebox.askyesno(
                    "Overwrite pattern",
                    f"A pattern already exists for {class_label(self.class_name)} - "
                    f"{self.exam_type} - {subject}. Overwrite it with the pasted one?"):
                return
        pattern_store.save_template(self.class_name, self.exam_type, subject, pattern)
        messagebox.showinfo("Pattern saved", f"Saved the pattern for {subject}.")
        self.on_saved()
        self.destroy()

    def save_for_all_subjects(self):
        pattern = self._parse_pattern()
        if pattern is None:
            return
        subjects = all_known_subjects()
        existing = [s for s in subjects if pattern_store.has_template(self.class_name, self.exam_type, s)]
        if existing:
            if not messagebox.askyesno(
                    "Overwrite patterns",
                    f"{len(existing)} of {len(subjects)} subjects already have a pattern learned for "
                    f"{class_label(self.class_name)} - {self.exam_type} ({', '.join(existing)}). "
                    f"Overwrite those and save the pasted pattern for every subject?"):
                return
        for subject in subjects:
            pattern_store.save_template(self.class_name, self.exam_type, subject, self._clean_for_subject(pattern))
        messagebox.showinfo("Patterns saved", f"Saved this pattern for all {len(subjects)} subjects.")
        self.on_saved()
        self.destroy()


class PatternsHubScreen(BaseScreen):
    """Central place for every class + exam type + subject pattern that's
    ever been learned. The whole point of pattern_store is that a pattern
    only needs to be taught once per combination and is then reused forever
    -- this screen is where that reuse actually happens, instead of
    re-walking Class -> Exam Type -> Subject -> Action every single time."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Manage Patterns", show_back=lambda: app.show_frame(HomeScreen))

        tk.Label(self, text="Quick jump: learn a new pattern or generate from an existing one "
                             "without clicking through every screen.",
                 bg=BG, font=("Segoe UI", 9), fg=MUTED, wraplength=800, justify="left"
                 ).pack(anchor="w", padx=PAD_XL, pady=(0, PAD_S))

        picker_card = tk.Frame(self, bg=CARD_BG, highlightbackground="#dfe4e8", highlightthickness=1)
        picker_card.pack(fill="x", padx=PAD_XL, pady=(0, PAD_L))
        picker = tk.Frame(picker_card, bg=CARD_BG)
        picker.pack(fill="x", padx=PAD_L, pady=PAD_M)

        tk.Label(picker, text="Class", bg=CARD_BG, font=("Segoe UI", 9, "bold"), fg=MUTED).grid(
            row=0, column=0, sticky="w")
        tk.Label(picker, text="Exam Type", bg=CARD_BG, font=("Segoe UI", 9, "bold"), fg=MUTED).grid(
            row=0, column=1, sticky="w", padx=(PAD_M, 0))
        tk.Label(picker, text="Subject", bg=CARD_BG, font=("Segoe UI", 9, "bold"), fg=MUTED).grid(
            row=0, column=2, sticky="w", padx=(PAD_M, 0))

        self.class_var = tk.StringVar(value=class_label(app.sel_class or CLASSES[0]))
        self.exam_var = tk.StringVar(value=app.sel_exam_type or EXAM_TYPES[0])
        self.subject_var = tk.StringVar(value=app.sel_subject or SUBJECTS[0])

        class_labels = [class_label(c) for c in CLASSES]
        cls_box = ttk.Combobox(picker, textvariable=self.class_var, values=class_labels, width=14,
                                state="readonly")
        cls_box.grid(row=1, column=0, pady=(2, PAD_S))

        ttk.Combobox(picker, textvariable=self.exam_var, values=EXAM_TYPES, width=20, state="readonly").grid(
            row=1, column=1, padx=(PAD_M, 0), pady=(2, PAD_S))
        # Editable (not readonly) with a dynamic suggestion list -- a fixed
        # readonly list previously made an already-in-use custom subject
        # (e.g. "COMPUTER") impossible to select here at all, which is worse
        # than the typo risk it was meant to prevent.
        ttk.Combobox(picker, textvariable=self.subject_var, values=all_known_subjects(),
                     width=20).grid(row=1, column=2, padx=(PAD_M, 0), pady=(2, PAD_S))

        btn_row = tk.Frame(picker, bg=CARD_BG)
        btn_row.grid(row=1, column=3, padx=(PAD_L, 0))
        tk.Button(btn_row, text="Learn / Update Pattern", bg=ACCENT, fg="white", relief="flat",
                  padx=10, pady=5, cursor="hand2", command=self.go_learn).pack(side="left", padx=(0, PAD_S))
        tk.Button(btn_row, text="Generate Paper", bg="white", relief="groove",
                  padx=10, pady=5, cursor="hand2", command=self.go_generate).pack(side="left")

        btn_row2 = tk.Frame(picker, bg=CARD_BG)
        btn_row2.grid(row=2, column=0, columnspan=4, sticky="w", pady=(PAD_S, 0))
        # Manual add works regardless of whether a pattern already exists for
        # this combination -- it's a straight paste-and-overwrite (or
        # paste-and-create) path that skips photos/OCR/AI entirely.
        tk.Button(btn_row2, text="📋 Add Pattern Manually (Paste JSON)", bg="white", relief="groove",
                  padx=10, pady=5, cursor="hand2", command=self.open_manual_add).pack(side="left")

        list_header = tk.Frame(self, bg=BG)
        list_header.pack(fill="x", padx=PAD_XL)
        self.templates = pattern_store.list_all_templates()
        tk.Label(list_header, text=f"Already learned ({len(self.templates)})", bg=BG,
                 font=("Segoe UI", 11, "bold"), fg=ACCENT).pack(side="left")

        if not self.templates:
            tk.Label(self, text="No patterns learned yet. Use the quick-setup above, or pick a class "
                                 "from Home to learn your first one.",
                     bg=BG, font=("Segoe UI", 10), fg=MUTED, wraplength=800, justify="left"
                     ).pack(anchor="w", padx=PAD_XL, pady=PAD_L)
            return

        # Scrollable list -- a plain pack of rows would overflow the window
        # once several classes/subjects have been learned.
        list_wrap = tk.Frame(self, bg=BG)
        list_wrap.pack(fill="both", expand=True, padx=PAD_XL, pady=(PAD_S, PAD_L))
        canvas = tk.Canvas(list_wrap, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_wrap, orient="vertical", command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg=BG)
        rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_wheel(_event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        # Bind/unbind only while the mouse is actually over this canvas --
        # binding globally for the app's whole lifetime would keep trying to
        # scroll this canvas (eventually a destroyed widget) even after the
        # user has navigated to a completely different screen.
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        for i, item in enumerate(self.templates):
            row = tk.Frame(rows_frame, bg=CARD_BG, highlightbackground="#dfe4e8", highlightthickness=1)
            row.pack(fill="x", pady=(0, PAD_S), padx=2)
            info = tk.Frame(row, bg=CARD_BG)
            info.pack(side="left", fill="x", expand=True, padx=PAD_M, pady=PAD_M)
            tk.Label(info, text=f"{class_label(item['class_name'])} · {item['exam_type']} · {item['subject']}",
                     bg=CARD_BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(info, text=f"{item['sections']} section(s) learned", bg=CARD_BG,
                     font=("Segoe UI", 8), fg=MUTED).pack(anchor="w")

            actions = tk.Frame(row, bg=CARD_BG)
            actions.pack(side="right", padx=PAD_M, pady=PAD_M)
            tk.Button(actions, text="Generate", bg=ACCENT, fg="white", relief="flat", padx=10, pady=4,
                      cursor="hand2", command=lambda it=item: self.use_existing(it, GenerateScreen)
                      ).pack(side="left", padx=(0, PAD_S))
            tk.Button(actions, text="Update", bg="white", relief="groove", padx=10, pady=4, cursor="hand2",
                      command=lambda it=item: self.use_existing(it, PatternSetupScreen)
                      ).pack(side="left", padx=(0, PAD_S))
            tk.Button(actions, text="Delete", bg="white", fg=WARN, relief="groove", padx=10, pady=4,
                      cursor="hand2", command=lambda it=item: self.delete(it)).pack(side="left")

    def _selected_raw_class(self):
        # Map the displayed "Class 5" back to the raw "5" that CLASSES/
        # pattern_store use as the key.
        shown = self.class_var.get()
        for c in CLASSES:
            if class_label(c) == shown:
                return c
        return shown

    def go_learn(self):
        c, et, s = self._selected_raw_class(), self.exam_var.get().strip(), self.subject_var.get().strip()
        if not et or not s:
            messagebox.showwarning("Missing info", "Please choose an exam type and subject.")
            return
        self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject = c, et, s
        self.app.show_frame(PatternSetupScreen)

    def go_generate(self):
        c, et, s = self._selected_raw_class(), self.exam_var.get().strip(), self.subject_var.get().strip()
        if not pattern_store.has_template(c, et, s):
            messagebox.showwarning("No pattern yet", "No pattern has been learned for that combination yet. "
                                                        "Use 'Learn / Update Pattern' first.")
            return
        self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject = c, et, s
        self.app.show_frame(GenerateScreen)

    def open_manual_add(self):
        c, et, s = self._selected_raw_class(), self.exam_var.get().strip(), self.subject_var.get().strip()
        if not et or not s:
            messagebox.showwarning("Missing info", "Please choose an exam type and subject.")
            return
        ManualPatternDialog(self, self.app, c, et, s,
                             on_saved=lambda: self.app.show_frame(PatternsHubScreen))

    def use_existing(self, item, target_screen):
        self.app.sel_class = item["class_name"]
        self.app.sel_exam_type = item["exam_type"]
        self.app.sel_subject = item["subject"]
        self.app.show_frame(target_screen)

    def delete(self, item):
        if not messagebox.askyesno(
                "Delete pattern",
                f"Delete the learned pattern for {class_label(item['class_name'])} - "
                f"{item['exam_type']} - {item['subject']}?\nYou'll need to re-upload a sample "
                f"paper to set it up again."):
            return
        pattern_store.delete_template(item["class_name"], item["exam_type"], item["subject"])
        self.app.show_frame(PatternsHubScreen)


class GenerateScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        c, et, s = app.sel_class, app.sel_exam_type, app.sel_subject
        self.header(f"Generate Paper — {class_label(c)} — {et} — {s}", show_back=lambda: app.show_frame(ActionScreen))

        self.mode = tk.StringVar(value="photo")
        body = tk.Frame(self, bg=BG)
        body.pack(pady=8)
        tk.Radiobutton(body, text="Upload a photo of handwritten questions", variable=self.mode,
                        value="photo", bg=BG, command=self.refresh).pack(anchor="w")
        tk.Radiobutton(body, text="No photo — let the AI write questions from the syllabus",
                        variable=self.mode, value="syllabus", bg=BG, command=self.refresh).pack(anchor="w")

        self.file_frame = tk.Frame(self, bg=BG)
        self.file_frame.pack(pady=6)
        self.photo_paths = []
        self.file_label = tk.Label(self.file_frame, text="No photos selected", bg=BG, fg="#555",
                                    wraplength=700, justify="center")
        self.file_label.pack()
        choose_row = tk.Frame(self.file_frame, bg=BG)
        choose_row.pack(pady=4)
        tk.Button(choose_row, text="Choose Photo(s)...", command=self.choose_file).pack(side="left")
        tk.Button(choose_row, text="Clear", bg="white", relief="groove", cursor="hand2",
                  command=self.clear_files).pack(side="left", padx=(6, 0))
        tk.Label(self.file_frame, text="Tip: click 'Choose Photo(s)...' once per photo if Ctrl/Shift-"
                                        "selecting multiple at once doesn't work on your PC -- each "
                                        "pick adds to the list instead of replacing it.",
                 bg=BG, font=("Segoe UI", 8), fg=MUTED, wraplength=600, justify="left").pack(pady=(2, 0))
        read_row = tk.Frame(self.file_frame, bg=BG)
        read_row.pack(pady=4)
        self.read_btn = tk.Button(read_row, text="Read Handwriting (local, offline)", bg=ACCENT, fg="white",
                                   command=self.read_handwriting)
        self.read_btn.pack(side="left")
        self.gemini_read_btn = tk.Button(read_row, text="📷 Read with Gemini", bg="white", relief="groove",
                                          cursor="hand2", command=self.read_handwriting_gemini)
        self.gemini_read_btn.pack(side="left", padx=(8, 0))
        tk.Label(self.file_frame, text="Gemini usually reads messy handwriting more accurately than the "
                                        "local model, and isn't limited by any chat upload/message limits "
                                        "-- only your own Gemini API quota (needs an API key set in Settings).",
                 bg=BG, font=("Segoe UI", 8), fg=MUTED, wraplength=650, justify="left").pack(pady=(2, 0))

        tk.Label(self, text="Review / correct extracted or generated text (only used for photo mode\n"
                             "before fitting; for syllabus mode this is filled in automatically):",
                 bg=BG, font=("Segoe UI", 9)).pack(pady=(8, 2))
        self.text = tk.Text(self, height=10, width=90, wrap="word")
        self.text.pack(padx=16, pady=4, fill="both", expand=True)

        self.gap_mode_var = tk.StringVar(value="none")
        self.gap_mode_frame = tk.LabelFrame(
            self, bg=BG, text="If a section's pattern wants more questions than you wrote:")
        tk.Radiobutton(self.gap_mode_frame, variable=self.gap_mode_var, value="none", bg=BG,
                       text="Print exactly what I wrote -- nothing added, even if a section ends up "
                            "with fewer questions than the pattern (recommended default)"
                       ).pack(anchor="w")
        tk.Radiobutton(self.gap_mode_frame, variable=self.gap_mode_var, value="blank", bg=BG,
                       text="Leave a visible blank placeholder for me to fill in by hand"
                       ).pack(anchor="w")
        tk.Radiobutton(self.gap_mode_frame, variable=self.gap_mode_var, value="ai", bg=BG,
                       text="Let the AI write the missing questions"
                       ).pack(anchor="w")

        self.status_label = tk.Label(self, text="", bg=BG, font=("Segoe UI", 10, "italic"))
        self.status_label.pack(pady=4)

        self.gen_btn = tk.Button(self, text="Generate Paper (PDF)", bg=ACCENT, fg="white",
                                  font=("Segoe UI", 11, "bold"), command=self.generate)
        self.gen_btn.pack(pady=8)

        self.result_label = tk.Label(self, text="", bg=BG, font=("Segoe UI", 10))
        self.result_label.pack(pady=4)

        self.refresh()

    def refresh(self):
        if self.mode.get() == "photo":
            self.file_frame.pack(pady=6)
            self.gap_mode_frame.pack(padx=16, pady=(0, 6), anchor="w", fill="x")
        else:
            self.file_frame.pack_forget()
            self.gap_mode_frame.pack_forget()
            self.text.delete("1.0", "end")

    def choose_file(self):
        files = filedialog.askopenfilenames(title="Select handwritten question photo(s) -- "
                                                     "click again to add more one at a time if needed",
                                             filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        # askopenfilenames is documented to return a tuple, but on some
        # Windows/Tcl-Tk combinations a single-file pick can come back as a
        # plain string instead -- iterating a string directly would silently
        # add one "file" per CHARACTER, so normalize defensively here.
        if isinstance(files, str):
            files = (files,) if files else ()
        added = 0
        for f in files:
            if f not in self.photo_paths:
                self.photo_paths.append(f)
                added += 1
        self._refresh_file_label(added, len(files))

    def _refresh_file_label(self, added, picked_this_time):
        if not self.photo_paths:
            self.file_label.config(text="No photos selected")
            return
        names = [os.path.basename(p) for p in self.photo_paths]
        shown = ", ".join(names) if len(names) <= 4 else ", ".join(names[:4]) + f", +{len(names) - 4} more"
        note = ""
        if picked_this_time and added == 0:
            note = "  (that file's already in the list -- pick a different one to add more)"
        self.file_label.config(text=f"{len(self.photo_paths)} photo(s) selected: {shown}{note}")

    def clear_files(self):
        self.photo_paths = []
        self.file_label.config(text="No photos selected")

    def read_handwriting(self):
        if not self.photo_paths:
            messagebox.showwarning("No photos", "Please choose at least one photo first.")
            return
        self.read_btn.config(state="disabled")
        self.gemini_read_btn.config(state="disabled")
        self.status_label.config(text="Reading handwriting with the local Ollama vision model "
                                       "(this can take a while on a slower computer, and longer "
                                       "still with more than one photo)...")

        def worker():
            try:
                model = config.get("ollama_vision_model") or handwriting_ocr.DEFAULT_MODEL
                text = handwriting_ocr.read_handwriting_multi(self.photo_paths, model=model)
                self.after(0, lambda: self.on_read_done(text))
            except Exception as e:
                self.after(0, lambda e=e: self.on_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def read_handwriting_gemini(self):
        if not self.photo_paths:
            messagebox.showwarning("No photos", "Please choose at least one photo first.")
            return
        api_key = config.get("gemini_api_key")
        if not api_key:
            messagebox.showwarning(
                "No Gemini API key set",
                "Open Settings, paste in an API key from "
                "https://aistudio.google.com/app/apikey, and try again.")
            return
        self.read_btn.config(state="disabled")
        self.gemini_read_btn.config(state="disabled")
        self.status_label.config(text="Reading handwriting with Gemini (needs internet)...")

        def worker():
            try:
                model = config.get("gemini_model") or gemini_llm.DEFAULT_MODEL
                c, et, s = self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject
                pattern = pattern_store.load_template(c, et, s)
                text = gemini_llm.read_handwriting_from_photos(
                    self.photo_paths, api_key=api_key, model=model, pattern=pattern)
                self.after(0, lambda: self.on_read_done(text))
            except Exception as e:
                self.after(0, lambda e=e: self.on_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_read_done(self, text):
        if not self.winfo_exists():
            return
        self.read_btn.config(state="normal")
        self.gemini_read_btn.config(state="normal")
        self.status_label.config(text="Done. Please check the text below carefully before generating the PDF -- "
                                       "automated handwriting reading can still make mistakes.")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def on_error(self, e):
        if not self.winfo_exists():
            return
        self.read_btn.config(state="normal")
        self.gemini_read_btn.config(state="normal")
        self.gen_btn.config(state="normal")
        self.status_label.config(text="")
        messagebox.showerror("Failed", str(e))

    def generate(self):
        c, et, s = self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject
        pattern = pattern_store.load_template(c, et, s)

        if self.mode.get() == "photo":
            extracted_text = self.text.get("1.0", "end").strip()
            if not extracted_text:
                messagebox.showwarning("Nothing to fit", "Please choose a photo and click 'Read Handwriting' "
                                                            "(and review the text) first.")
                return

        self.gen_btn.config(state="disabled")
        self.status_label.config(text="Generating paper...")
        self.result_label.config(text="")

        def worker():
            try:
                if self.mode.get() == "photo":
                    text = self.text.get("1.0", "end").strip()
                    paper = question_fitter.fit_to_pattern(
                        pattern, text, c, et, s,
                        gap_mode=self.gap_mode_var.get(),
                    )
                else:
                    paper = ai_provider.generate_paper_from_syllabus(pattern, c, et, s)
                self.after(0, lambda: self.app.show_frame(PaperEditScreen, paper=paper))
            except Exception as e:
                self.after(0, lambda e=e: self.on_error(e))

        threading.Thread(target=worker, daemon=True).start()


class PaperEditScreen(BaseScreen):
    """Final review/edit step: shows the generated paper as editable JSON
    (questions, header, marks, instructions -- everything) before export, and
    lets the teacher choose PDF, Word, or both."""

    def __init__(self, parent, app, paper):
        super().__init__(parent, app)
        c, et, s = app.sel_class, app.sel_exam_type, app.sel_subject
        self.header(f"Review & Edit Paper — {class_label(c)} — {et} — {s}",
                     show_back=lambda: app.show_frame(GenerateScreen))

        tk.Label(self, text="Edit anything below -- question text, marks, instructions, header -- "
                             "then export.", bg=BG, font=("Segoe UI", 9)).pack(pady=(4, 2))

        counts = {"handwritten": 0, "ai_filled": 0, "blank": 0}
        for section in paper.get("sections", []):
            for q in section.get("questions", []):
                src = q.get("source")
                if src in counts:
                    counts[src] += 1
        summary_bits = [f"From your handwriting: {counts['handwritten']}"]
        if counts["ai_filled"]:
            summary_bits.append(f"Filled in by AI: {counts['ai_filled']}")
        if counts["blank"]:
            summary_bits.append(f"Left blank for you to write: {counts['blank']}")
        leftover = paper.get("unplaced_handwritten_questions") or []
        if leftover:
            summary_bits.append(f"⚠ {len(leftover)} handwritten question(s) didn't fit any "
                                 f"section slot -- see 'unplaced_handwritten_questions' below")
        if counts["ai_filled"] or counts["blank"] or leftover:
            tk.Label(
                self, text="   |   ".join(summary_bits),
                bg=BG, fg="#a05a00", font=("Segoe UI", 9, "bold"), wraplength=850, justify="left",
            ).pack(pady=(0, 4))

        self.text = tk.Text(self, height=20, width=95, wrap="word")
        self.text.pack(padx=16, pady=4, fill="both", expand=True)
        self.text.insert("1.0", json.dumps(paper, indent=2, ensure_ascii=False))

        opts = tk.Frame(self, bg=BG)
        opts.pack(pady=8)
        self.want_pdf = tk.BooleanVar(value=True)
        self.want_docx = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="Export as PDF", variable=self.want_pdf, bg=BG).pack(side="left", padx=10)
        tk.Checkbutton(opts, text="Export as Word (.docx)", variable=self.want_docx, bg=BG).pack(side="left", padx=10)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=8)
        self.export_btn = tk.Button(btn_row, text="Export", bg=ACCENT, fg="white",
                                     font=("Segoe UI", 11, "bold"), command=self.export)
        self.export_btn.pack(side="left", padx=6)
        self.print_btn = tk.Button(btn_row, text="Print", bg=ACCENT, fg="white",
                                    font=("Segoe UI", 11, "bold"), command=self.print_paper)
        self.print_btn.pack(side="left", padx=6)

        self.result_label = tk.Label(self, text="", bg=BG, font=("Segoe UI", 10), justify="left")
        self.result_label.pack(pady=6)

        # Filled in after a successful export -- separate "Open PDF" / "Open
        # Word" buttons so each saved file can be opened directly from the
        # app, instead of just showing a file path the teacher has to go
        # find manually in File Explorer.
        self.saved_files_frame = tk.Frame(self, bg=BG)
        self.saved_files_frame.pack(pady=(0, 6))

    def _show_saved_file_buttons(self, pdf_path=None, docx_path=None):
        for widget in self.saved_files_frame.winfo_children():
            widget.destroy()
        if pdf_path:
            row = tk.Frame(self.saved_files_frame, bg=BG)
            row.pack(pady=2)
            tk.Label(row, text=f"PDF saved: {pdf_path}", bg=BG, font=("Segoe UI", 9), fg=MUTED).pack(side="left")
            tk.Button(row, text="Open PDF", bg="white", relief="groove", cursor="hand2",
                      command=lambda: self._open_saved(pdf_path)).pack(side="left", padx=(8, 0))
        if docx_path:
            row = tk.Frame(self.saved_files_frame, bg=BG)
            row.pack(pady=2)
            tk.Label(row, text=f"Word saved: {docx_path}", bg=BG, font=("Segoe UI", 9), fg=MUTED).pack(side="left")
            tk.Button(row, text="Open Word", bg="white", relief="groove", cursor="hand2",
                      command=lambda: self._open_saved(docx_path)).pack(side="left", padx=(8, 0))

    def _open_saved(self, path):
        try:
            printing.open_file(path)
        except RuntimeError as e:
            messagebox.showerror("Couldn't open file", str(e))

    def export(self):
        if not self.want_pdf.get() and not self.want_docx.get():
            messagebox.showwarning("Choose a format", "Please select PDF, Word, or both.")
            return
        try:
            paper = json.loads(self.text.get("1.0", "end"))
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Please fix the JSON before exporting:\n{e}")
            return

        c, et, s = self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject
        pdf_path = None
        docx_path = None
        try:
            if self.want_pdf.get():
                pdf_path = pdf_generator.build_pdf(paper, c, et, s)
            if self.want_docx.get():
                docx_path = docx_generator.build_docx(paper, c, et, s)
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
            return

        self.result_label.config(text="Export complete.")
        self._show_saved_file_buttons(pdf_path=pdf_path, docx_path=docx_path)

    def print_paper(self):
        try:
            paper = json.loads(self.text.get("1.0", "end"))
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Please fix the JSON before printing:\n{e}")
            return

        c, et, s = self.app.sel_class, self.app.sel_exam_type, self.app.sel_subject
        self.print_btn.config(state="disabled")
        self.result_label.config(text="Preparing to print...")

        def worker():
            try:
                pdf_path = pdf_generator.build_pdf(paper, c, et, s)
                printing.print_file(pdf_path)
                self.after(0, lambda: self.on_print_done(pdf_path))
            except Exception as e:
                self.after(0, lambda e=e: self.on_print_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_print_done(self, pdf_path):
        self.print_btn.config(state="normal")
        self.result_label.config(text=f"Sent to printer: {pdf_path}")

    def on_print_error(self, e):
        self.print_btn.config(state="normal")
        self.result_label.config(text="")
        messagebox.showerror("Print failed", str(e))


class SettingsScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Settings", show_back=lambda: app.show_frame(HomeScreen))

        body = tk.Frame(self, bg=BG)
        body.pack(pady=20, padx=40, fill="x")

        tk.Label(body, text="Tesseract path (leave blank if already on PATH)", bg=BG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(body, text="Only needed on Windows if 'tesseract' isn't found automatically.",
                 bg=BG, fg="#555", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self.tess_var = tk.StringVar(value=config.get("tesseract_cmd"))
        tk.Entry(body, textvariable=self.tess_var, width=60).pack(anchor="w", pady=4)

        tk.Label(body, text="AI provider (writes questions from the syllabus, fills gaps)", bg=BG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Ollama = free, local, fully offline. Gemini = Google's cloud AI, "
                             "usually more accurate, needs internet + an API key (free tier, "
                             "then pay-as-you-go).",
                 bg=BG, fg="#555", font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))
        self.provider_var = tk.StringVar(value=config.get("ai_provider") or "ollama")
        provider_row = tk.Frame(body, bg=BG)
        provider_row.pack(anchor="w", pady=2)
        tk.Radiobutton(provider_row, text="Ollama (local, free)", variable=self.provider_var,
                        value="ollama", bg=BG).pack(side="left", padx=(0, 16))
        tk.Radiobutton(provider_row, text="Gemini (cloud API)", variable=self.provider_var,
                        value="gemini", bg=BG).pack(side="left")

        tk.Label(body, text="Ollama model name", bg=BG, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Must match a model you've pulled, e.g. 'ollama pull llama3.2'.",
                 bg=BG, fg="#555", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self.ollama_var = tk.StringVar(value=config.get("ollama_model"))
        tk.Entry(body, textvariable=self.ollama_var, width=30).pack(anchor="w", pady=4)

        tk.Label(body, text="Ollama vision model name (for reading handwriting)", bg=BG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Must be a vision-capable model you've pulled, e.g. "
                             "'ollama pull qwen2.5vl'. A text-only model will not work here.",
                 bg=BG, fg="#555", font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))
        self.ollama_vision_var = tk.StringVar(value=config.get("ollama_vision_model"))
        tk.Entry(body, textvariable=self.ollama_vision_var, width=30).pack(anchor="w", pady=4)

        tk.Label(body, text="Gemini API key", bg=BG, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Get a free key at https://aistudio.google.com/app/apikey. "
                             "Stored only on this computer.",
                 bg=BG, fg="#555", font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))
        self.gemini_key_var = tk.StringVar(value=config.get("gemini_api_key"))
        tk.Entry(body, textvariable=self.gemini_key_var, width=50, show="*").pack(anchor="w", pady=4)

        tk.Label(body, text="Gemini model name", bg=BG, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Default 'gemini-flash-latest' is fine for most cases -- it's Google's "
                             "own alias for their current recommended fast model.",
                 bg=BG, fg="#555", font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))
        self.gemini_model_var = tk.StringVar(value=config.get("gemini_model"))
        tk.Entry(body, textvariable=self.gemini_model_var, width=30).pack(anchor="w", pady=4)

        tk.Label(body, text="School profiles", bg=BG, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 0))
        tk.Label(body, text="Saved name/address pairs -- pick one from a dropdown wherever a pattern's "
                             "school info gets set, instead of retyping it every time (handy if this app "
                             "is used for more than one school).",
                 bg=BG, fg="#555", font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))
        self.school_rows_frame = tk.Frame(body, bg=BG)
        self.school_rows_frame.pack(anchor="w", fill="x")
        self.school_rows = []  # list of {"frame", "name_var", "addr_var"}
        for profile in (config.get("school_profiles") or []):
            self._add_school_row(profile.get("name", ""), profile.get("address", ""))
        tk.Button(body, text="+ Add another school", bg="white", relief="groove", cursor="hand2",
                  command=lambda: self._add_school_row()).pack(anchor="w", pady=(4, 0))

        tk.Button(body, text="Save", bg=ACCENT, fg="white", command=self.save).pack(anchor="w", pady=16)

    def _add_school_row(self, name="", address=""):
        row = tk.Frame(self.school_rows_frame, bg=BG)
        row.pack(anchor="w", pady=2, fill="x")
        name_var = tk.StringVar(value=name)
        addr_var = tk.StringVar(value=address)
        tk.Entry(row, textvariable=name_var, width=24).pack(side="left")
        tk.Entry(row, textvariable=addr_var, width=34).pack(side="left", padx=(6, 0))
        entry = {"frame": row, "name_var": name_var, "addr_var": addr_var}
        remove_btn = tk.Button(row, text="Remove", bg="white", fg=WARN, relief="groove", cursor="hand2",
                                command=lambda: self._remove_school_row(entry))
        remove_btn.pack(side="left", padx=(6, 0))
        self.school_rows.append(entry)

    def _remove_school_row(self, entry):
        entry["frame"].destroy()
        self.school_rows.remove(entry)

    def save(self):
        config.set_value("tesseract_cmd", self.tess_var.get().strip())
        config.set_value("ai_provider", self.provider_var.get().strip() or "ollama")
        config.set_value("ollama_model", self.ollama_var.get().strip() or "llama3.2")
        config.set_value("ollama_vision_model", self.ollama_vision_var.get().strip() or "qwen2.5vl")
        config.set_value("gemini_api_key", self.gemini_key_var.get().strip())
        config.set_value("gemini_model", self.gemini_model_var.get().strip() or "gemini-flash-latest")
        profiles = [
            {"name": r["name_var"].get().strip(), "address": r["addr_var"].get().strip()}
            for r in self.school_rows if r["name_var"].get().strip()
        ]
        config.set_value("school_profiles", profiles)
        config.apply_tesseract_path()
        messagebox.showinfo("Saved", "Settings saved.")


def run():
    app = QPApp()
    app.mainloop()