"""Модуль «Пользовательский интерфейс» (Tkinter/ttk).

GUI не знает, как устроена база знаний: он собирает данные формы в Observation,
вызывает engine.run_diagnosis() и отображает полученный DiagnosticResult.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from .explanation import explain, full_report
from .inference import HIGH, LOW, MEDIUM, InferenceEngine
from .models import DiagnosticResult, InputError, Observation, parse_number

FEEDING = ["регулярные", "редкие", "отсутствуют", "избыточные"]
APP_TITLE = "ЭС «Мониторинг состояния почвы и растений»"
GREEN, GREEN_DARK, BG = "#2e7d32", "#1b5e20", "#f4f7f2"


class MainWindow:
    def __init__(self, root: tk.Tk, engine: InferenceEngine):
        self.root, self.engine, self.kb = root, engine, engine.kb
        self.result: DiagnosticResult | None = None
        self._setup_style()
        root.title(APP_TITLE)
        root.geometry("1340x800")
        root.minsize(1100, 680)
        root.configure(bg=BG)
        self._build_menu()
        self._build_header()
        body = ttk.Frame(root, padding=(10, 6, 10, 4))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_input(body)
        self._build_output(body)
        self._build_statusbar()
        self.clear()

    # ------------------------------------------------------------------ оформление
    def _setup_style(self):
        families = set(tkfont.families(self.root))
        family = next((f for f in ("Segoe UI", "DejaVu Sans", "Arial") if f in families), "TkDefaultFont")
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=family, size=10)
        self.family = family
        st = ttk.Style(self.root)
        if "clam" in st.theme_names():
            st.theme_use("clam")
        st.configure(".", background=BG)
        st.configure("TLabelframe.Label", font=(family, 10, "bold"), foreground=GREEN_DARK)
        st.configure("TCheckbutton", background=BG)
        st.configure("Accent.TButton", font=(family, 10, "bold"), foreground="white",
                     background=GREEN, padding=(14, 6))
        st.map("Accent.TButton", background=[("active", GREEN_DARK)])
        st.configure("TButton", padding=(10, 6))
        st.configure("Treeview", rowheight=24)
        st.configure("Treeview.Heading", font=(family, 10, "bold"))
        st.configure("Hint.TLabel", foreground="#666666", font=(family, 9))

    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="Сохранить заключение…", command=self.save_dialog, accelerator="Ctrl+S")
        f.add_separator()
        f.add_command(label="Выход", command=self.root.destroy)
        m.add_cascade(label="Файл", menu=f)
        k = tk.Menu(m, tearoff=False)
        k.add_command(label="Просмотр базы знаний", command=self.open_kb_window)
        m.add_cascade(label="База знаний", menu=k)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label="Как пользоваться", command=self.show_help)
        h.add_command(label="О программе", command=self.show_about)
        m.add_cascade(label="Справка", menu=h)
        self.root.config(menu=m)
        self.root.bind("<Control-s>", lambda e: self.save_dialog())
        self.root.bind("<F5>", lambda e: self.diagnose())

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=GREEN, height=52)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Мониторинг состояния почвы и растений", bg=GREEN, fg="white",
                 font=(self.family, 15, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text="экспертная система диагностики причин отклонения состояния растений",
                 bg=GREEN, fg="#dcedc8", font=(self.family, 10)).pack(side="left", pady=14)

    # ------------------------------------------------------------------ ввод
    def _build_input(self, parent):
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))

        sp = ttk.LabelFrame(left, text="1. Вид растения", padding=8)
        sp.pack(fill="x")
        self.species_names = {s.name: s.id for s in self.kb.species.values()}
        self.species_var = tk.StringVar()
        self.species_cb = ttk.Combobox(sp, textvariable=self.species_var, state="readonly",
                                       values=list(self.species_names), width=44)
        self.species_cb.pack(fill="x")
        self.species_cb.bind("<<ComboboxSelected>>", lambda e: self._update_norms())
        self.norm_lbl = ttk.Label(sp, text="", style="Hint.TLabel")
        self.norm_lbl.pack(anchor="w", pady=(4, 0))

        sy = ttk.LabelFrame(left, text="2. Внешние признаки растения", padding=8)
        sy.pack(fill="x", pady=8)
        self.symptom_vars: dict[str, tk.BooleanVar] = {}
        items = list(self.kb.symptoms.values())
        half = (len(items) + 1) // 2
        for i, s in enumerate(items):
            v = tk.BooleanVar()
            self.symptom_vars[s.id] = v
            ttk.Checkbutton(sy, text=s.name, variable=v).grid(row=i % half, column=i // half,
                                                              sticky="w", padx=(0, 10), pady=1)

        so = ttk.LabelFrame(left, text="3. Показатели почвы и условия (необязательно)", padding=8)
        so.pack(fill="x")
        self.hum_var, self.ph_var, self.temp_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.feed_var, self.days_var = tk.StringVar(), tk.StringVar()
        rows = [("Влажность почвы, %", ttk.Entry(so, textvariable=self.hum_var, width=12)),
                ("Кислотность почвы, pH", ttk.Entry(so, textvariable=self.ph_var, width=12)),
                ("Температура, °C", ttk.Entry(so, textvariable=self.temp_var, width=12)),
                ("Подкормки", ttk.Combobox(so, textvariable=self.feed_var, values=[""] + FEEDING,
                                          state="readonly", width=14)),
                ("Давность признаков, дней", ttk.Spinbox(so, textvariable=self.days_var, from_=0,
                                                        to=365, width=10))]
        for r, (label, widget) in enumerate(rows):
            ttk.Label(so, text=label).grid(row=r, column=0, sticky="w", pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=8, pady=3)
        self.entries = {"hum": rows[0][1], "ph": rows[1][1], "temp": rows[2][1]}

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Диагностировать (F5)", style="Accent.TButton",
                   command=self.diagnose).pack(side="left")
        ttk.Button(btns, text="Очистить", command=self.clear).pack(side="left", padx=6)
        ttk.Button(btns, text="Пример", command=self.fill_example).pack(side="left")

    # ------------------------------------------------------------------ вывод
    def _build_output(self, parent):
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(2, weight=4)
        right.columnconfigure(0, weight=1)

        res = ttk.LabelFrame(right, text="Результаты диагностики (ранжированный список причин)", padding=6)
        res.grid(row=0, column=0, sticky="nsew")
        res.rowconfigure(0, weight=1)
        res.columnconfigure(0, weight=1)
        cols = ("n", "cause", "score", "verdict")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=10, selectmode="browse")
        for c, title, w, anchor in [("n", "№", 34, "center"), ("cause", "Причина отклонения", 250, "w"),
                                    ("score", "Оценка", 80, "center"),
                                    ("verdict", "Вердикт", 165, "w")]:
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "cause"))
        self.tree.tag_configure("high", background="#c8e6c9", font=(self.family, 10, "bold"))
        self.tree.tag_configure("medium", background="#fff3c4")
        self.tree.tag_configure("low", background="#ffffff")
        self.tree.tag_configure("unlikely", foreground="#9e9e9e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_selected())

        self.warn_lbl = tk.Label(right, text="", bg="#fff8e1", fg="#8d4b00", justify="left",
                                 anchor="w", wraplength=560, font=(self.family, 10), padx=8, pady=6)
        self.warn_lbl.grid(row=1, column=0, sticky="ew", pady=6)

        ex = ttk.LabelFrame(right, text="Объяснение и рекомендации", padding=6)
        ex.grid(row=2, column=0, sticky="nsew")
        ex.rowconfigure(0, weight=1)
        ex.columnconfigure(0, weight=1)
        self.text = tk.Text(ex, wrap="word", font=(self.family, 10), relief="flat", padx=8, pady=6,
                            bg="white", height=12)
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.tag_configure("title", font=(self.family, 12, "bold"), foreground=GREEN_DARK)
        self.text.tag_configure("error", font=(self.family, 11, "bold"), foreground="#c62828")
        self.text.tag_configure("rec", font=(self.family, 10, "bold"))
        ts = ttk.Scrollbar(ex, orient="vertical", command=self.text.yview)
        ts.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=ts.set)

    def _build_statusbar(self):
        self.status = tk.Label(self.root, anchor="w", bg="#e0e6dc", fg="#333333", padx=10, pady=3,
                               font=(self.family, 9))
        self.status.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------ обработчики
    def collect_observation(self) -> Observation:
        """Собирает данные формы. Ошибки формата чисел — InputError."""
        species_id = self.species_names.get(self.species_var.get(), "")
        symptoms = {sid for sid, v in self.symptom_vars.items() if v.get()}
        humidity = parse_number(self.hum_var.get(), "Влажность почвы", 0, 100)
        ph = parse_number(self.ph_var.get(), "Кислотность почвы, pH", 0, 14)
        temp = parse_number(self.temp_var.get(), "Температура", -30, 60)
        days = parse_number(self.days_var.get(), "Давность признаков", 0, 365)
        if days is not None and days != int(days):
            raise InputError("Ошибка: поле «Давность признаков» должно быть целым числом дней.")
        return Observation(species_id, symptoms, humidity, ph, temp,
                           self.feed_var.get() or None, int(days or 0))

    def diagnose(self):
        """Обработчик кнопки «Диагностировать»: форма → мост (машина вывода) → экран."""
        try:
            obs = self.collect_observation()
            result = self.engine.run_diagnosis(obs)          # единственный вызов «моста»
        except InputError as err:
            self._show_error(str(err))
            return
        self.result = result
        self._render(result)

    def _render(self, result: DiagnosticResult):
        self.tree.delete(*self.tree.get_children())
        tags = {HIGH: "high", MEDIUM: "medium", LOW: "low"}
        for i, a in enumerate(result.assessments, 1):
            self.tree.insert("", "end", iid=a.cause.id, tags=(tags.get(a.verdict, "unlikely"),),
                             values=(i, a.cause.name, f"{a.score:.0f} %", a.verdict))
        self.warn_lbl.configure(text="\n".join("⚠ " + w for w in result.warnings) or "Предупреждений нет.")
        first = result.assessments[0].cause.id
        self.tree.selection_set(first)
        self.tree.focus(first)
        self._show_selected()
        best = result.best
        self.status.configure(fg="#333333", text=(
            f"Диагностика выполнена за {result.elapsed_ms:.0f} мс. "
            f"Наиболее вероятная причина: {best.cause.name} ({best.score:.0f} %)." if best else
            f"Диагностика выполнена за {result.elapsed_ms:.0f} мс. Причина не установлена."))

    def _show_selected(self):
        if not self.result or not self.tree.selection():
            return
        cid = self.tree.selection()[0]
        a = next(x for x in self.result.assessments if x.cause.id == cid)
        body = explain(a)
        title, rest = body.split("\n", 1)
        rest, rec = rest.rsplit("Рекомендация:", 1)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", title + "\n", "title")
        self.text.insert("end", rest)
        self.text.insert("end", "Рекомендация:" + rec, "rec")
        self.text.configure(state="disabled")

    def _show_error(self, msg: str):
        self.result = None
        self.tree.delete(*self.tree.get_children())
        self.warn_lbl.configure(text="")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", msg, "error")
        self.text.configure(state="disabled")
        self.status.configure(text=msg, fg="#c62828")

    def clear(self):
        """Обработчик кнопки «Очистить»: сброс формы и результатов."""
        self.species_var.set(next(iter(self.species_names)))
        for v in self.symptom_vars.values():
            v.set(False)
        for v in (self.hum_var, self.ph_var, self.temp_var, self.feed_var):
            v.set("")
        self.days_var.set("0")
        self.result = None
        self.tree.delete(*self.tree.get_children())
        self.warn_lbl.configure(text="Заполните форму и нажмите «Диагностировать».")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._update_norms()
        self.status.configure(fg="#333333", text=f"Готово. База знаний загружена: {self.kb.stats()}.")

    def fill_example(self):
        self.clear()
        self.species_var.set(self.kb.species["Вид_Фиалка"].name)
        for s in ("Увядание", "Пожелтение_листьев", "Сухие_кончики_листьев"):
            self.symptom_vars[s].set(True)
        self.hum_var.set("25"); self.ph_var.set("6.2"); self.temp_var.set("23")
        self.feed_var.set("регулярные"); self.days_var.set("3")
        self._update_norms()

    def _update_norms(self):
        sid = self.species_names.get(self.species_var.get())
        if not sid:
            return
        s = self.kb.species[sid]
        self.norm_lbl.configure(text=f"Нормы вида: влажность {s.humidity_min:g}–{s.humidity_max:g} %, "
                                     f"pH {s.ph_min:g}–{s.ph_max:g}, t {s.temp_min:g}–{s.temp_max:g} °C")

    # ------------------------------------------------------------------ прочее
    def save_report(self, path: str):
        if not self.result:
            raise InputError("Сначала выполните диагностику.")
        o = self.result.observation
        names = [self.kb.symptoms[s].name for s in sorted(o.symptoms)]
        with open(path, "w", encoding="utf-8") as f:
            f.write(full_report(self.result, self.kb.species[o.species_id].name, names))

    def save_dialog(self):
        if not self.result:
            messagebox.showinfo(APP_TITLE, "Сначала выполните диагностику.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Текст", "*.txt")],
                                            initialfile="заключение.txt")
        if path:
            self.save_report(path)
            self.status.configure(text=f"Заключение сохранено: {path}", fg="#333333")

    def open_kb_window(self):
        return KnowledgeBaseWindow(self.root, self.kb, self.family)

    def show_help(self):
        messagebox.showinfo("Как пользоваться", (
            "1. Выберите вид растения.\n2. Отметьте наблюдаемые внешние признаки.\n"
            "3. По возможности введите показатели почвы (влажность, pH, температура), "
            "сведения о подкормках и давность признаков.\n4. Нажмите «Диагностировать» (F5).\n"
            "5. Выберите строку в таблице, чтобы увидеть объяснение и рекомендации.\n"
            "6. «Файл → Сохранить заключение» сохраняет отчёт в текстовый файл."))

    def show_about(self):
        messagebox.showinfo("О программе", (
            f"{APP_TITLE}\nПрототип экспертной системы, версия 1.0\n\n"
            "БрГТУ, кафедра ИИТ, 2026\nБаза знаний: OWL-онтология (Protégé), rdflib + SPARQL\n"
            f"{self.kb.stats()}"))


class KnowledgeBaseWindow(tk.Toplevel):
    """Окно просмотра базы знаний (данные берутся из онтологии)."""

    def __init__(self, master, kb, family):
        super().__init__(master)
        self.kb = kb
        self.title("База знаний — " + kb.path.name)
        self.geometry("1320x600")
        self.configure(bg=BG)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # причины
        f1 = ttk.Frame(nb, padding=6)
        nb.add(f1, text=f"Причины отклонения ({len(kb.causes)})")
        f1.columnconfigure(0, weight=1); f1.rowconfigure(0, weight=1)
        t1 = ttk.Treeview(f1, columns=("name", "key", "other", "cond"), show="headings")
        for c, title, w in [("name", "Причина", 250), ("key", "Ключевые признаки", 240),
                            ("other", "Прочие характерные признаки", 450), ("cond", "Условия почвы", 340)]:
            t1.heading(c, text=title); t1.column(c, width=w, anchor="w")
        for c in kb.causes.values():
            nm = lambda ids: ", ".join(kb.symptoms[i].name for i in sorted(ids))
            t1.insert("", "end", iid=c.id, values=(c.name, nm(c.key_symptoms), nm(c.symptoms - c.key_symptoms),
                                                   "; ".join(x.description for x in c.conditions) or "—"))
        t1.grid(row=0, column=0, sticky="nsew")
        self.rec = tk.Label(f1, text="Выберите причину, чтобы увидеть рекомендацию.", anchor="w",
                            justify="left", bg="white", wraplength=1260, padx=8, pady=6, font=(family, 10))
        self.rec.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        t1.bind("<<TreeviewSelect>>", lambda e: self.rec.configure(
            text="Рекомендация: " + kb.causes[t1.selection()[0]].recommendation))
        self.causes_tree = t1

        # признаки
        f2 = ttk.Frame(nb, padding=6)
        nb.add(f2, text=f"Признаки ({len(kb.symptoms)})")
        t2 = ttk.Treeview(f2, columns=("name", "sev", "causes"), show="headings")
        for c, title, w in [("name", "Признак", 300), ("sev", "Выраженность", 120), ("causes", "Характерен для причин", 600)]:
            t2.heading(c, text=title); t2.column(c, width=w, anchor="w")
        for s in kb.symptoms.values():
            t2.insert("", "end", values=(s.name, s.severity, ", ".join(
                c.name for c in kb.causes.values() if s.id in c.symptoms)))
        t2.pack(fill="both", expand=True)

        # виды
        f3 = ttk.Frame(nb, padding=6)
        nb.add(f3, text=f"Виды растений ({len(kb.species)})")
        t3 = ttk.Treeview(f3, columns=("name", "h", "ph", "t"), show="headings")
        for c, title, w in [("name", "Вид растения", 300), ("h", "Влажность почвы, %", 180),
                            ("ph", "pH", 120), ("t", "Температура, °C", 160)]:
            t3.heading(c, text=title); t3.column(c, width=w, anchor="w")
        for s in kb.species.values():
            t3.insert("", "end", values=(s.name, f"{s.humidity_min:g}–{s.humidity_max:g}",
                                         f"{s.ph_min:g}–{s.ph_max:g}", f"{s.temp_min:g}–{s.temp_max:g}"))
        t3.pack(fill="both", expand=True)
        self.notebook = nb
