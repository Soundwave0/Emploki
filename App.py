"""Desktop interface for configuring and generating Emploki documents."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yaml

from Backend.PDFInjector import DEFAULT_PAYLOAD, inject_pdf
from Backend.PromptHandler import PromptHandler

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "Configs"
OUTPUT_DIR = ROOT / "out"
INJECTIONS_FILE = CONFIG_DIR / "Injections.yaml"


class EmplokiApp(ctk.CTk):
    """Window that exposes the project's resume and PDF options."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Emploki · Document Studio")
        self.geometry("1020x760")
        self.minsize(880, 650)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._task_results = queue.Queue()
        self.job_listing_text = ""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=26, pady=(18, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Emploki", font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Configure, generate, and export your documents", text_color="gray70").grid(row=1, column=0, sticky="w")
        ctk.CTkOptionMenu(header, values=["System", "Light", "Dark"], command=ctk.set_appearance_mode, width=110).grid(row=0, column=1, rowspan=2, sticky="e")

        self.tabs = ctk.CTkTabview(self, corner_radius=14)
        self.tabs.grid(row=1, column=0, padx=22, pady=(0, 14), sticky="nsew")
        self.tabs.add("Generate resume")
        self.tabs.add("Inject into PDF")
        self.injection_presets = self._load_injection_presets()
        self._build_resume_tab()
        self._build_injection_tab()
        self.status = ctk.CTkLabel(self, text="Ready", anchor="w", text_color="gray75")
        self.status.grid(row=2, column=0, padx=26, pady=(0, 14), sticky="ew")
        self.after(100, self._process_task_results)

    def _entry(self, parent, value="", **kwargs):
        entry = ctk.CTkEntry(parent, **kwargs)
        entry.insert(0, value)
        return entry

    def _path_row(self, parent, row, label, default, filetypes, attr):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=(18, 8), pady=8, sticky="w")
        entry = self._entry(parent, str(default))
        entry.grid(row=row, column=1, padx=8, pady=8, sticky="ew")
        setattr(self, attr, entry)
        ctk.CTkButton(parent, text="Browse", width=82, command=lambda: self._choose_file(entry, filetypes)).grid(row=row, column=2, padx=(8, 18), pady=8)

    def _load_injection_presets(self):
        """Read selectable prompt presets from Configs/Injections.yaml."""
        try:
            with INJECTIONS_FILE.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
            presets = data.get("prompts", [])
            return [preset for preset in presets if isinstance(preset, dict) and preset.get("prompt_text")]
        except (OSError, yaml.YAMLError):
            return []

    def _build_resume_tab(self):
        tab = self.tabs.tab("Generate resume")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        fields = ctk.CTkFrame(tab)
        fields.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        fields.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fields, text="Resume generation", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, padx=18, pady=(14, 8), sticky="w")
        ctk.CTkLabel(fields, text="Job offer URL").grid(row=1, column=0, padx=(18, 8), pady=8, sticky="w")
        self.job_url = self._entry(fields, placeholder_text="https://example.com/job-posting")
        self.job_url.grid(row=1, column=1, padx=(8, 8), pady=8, sticky="ew")
        self.paste_listing_button = ctk.CTkButton(fields, text="Paste listing", width=110, command=self._open_listing_paste_dialog)
        self.paste_listing_button.grid(row=1, column=2, padx=(0, 18), pady=8)
        ctk.CTkLabel(fields, text="Ollama model").grid(row=2, column=0, padx=(18, 8), pady=8, sticky="w")
        self.model = self._entry(fields, "codellama:7b-instruct")
        self.model.grid(row=2, column=1, columnspan=2, padx=(8, 18), pady=8, sticky="ew")
        self._path_row(fields, 3, "Resume data", CONFIG_DIR / "resume_data.json", [("JSON files", "*.json")], "resume_data")
        self._path_row(fields, 4, "LaTeX template", CONFIG_DIR / "resume_template.tex", [("TeX files", "*.tex"), ("All files", "*.*")], "resume_template")

        export = ctk.CTkFrame(tab)
        export.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        export.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(export, text="Export settings", font=ctk.CTkFont(size=17, weight="bold")).grid(row=0, column=0, columnspan=3, padx=18, pady=(14, 8), sticky="w")
        ctk.CTkLabel(export, text="LaTeX output").grid(row=1, column=0, padx=(18, 8), pady=8, sticky="w")
        self.tex_output = self._entry(export, str(OUTPUT_DIR / "recently_generated.tex"))
        self.tex_output.grid(row=1, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(export, text="Save as", width=82, command=lambda: self._save_as(self.tex_output, ".tex")).grid(row=1, column=2, padx=(8, 18), pady=8)
        self.compile_pdf = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(export, text="Also compile a PDF (requires Pandoc and a TeX engine)", variable=self.compile_pdf).grid(row=2, column=0, columnspan=3, padx=18, pady=(5, 8), sticky="w")
        ctk.CTkLabel(export, text="PDF engine").grid(row=3, column=0, padx=(18, 8), pady=(4, 14), sticky="w")
        self.pdf_engine = ctk.CTkOptionMenu(export, values=["xelatex", "pdflatex", "lualatex"])
        self.pdf_engine.grid(row=3, column=1, padx=8, pady=(4, 14), sticky="w")
        self.resume_button = ctk.CTkButton(export, text="Generate resume", height=38, command=self._generate_resume)
        self.resume_button.grid(row=3, column=2, padx=(8, 18), pady=(4, 14))
        self.resume_log = ctk.CTkTextbox(tab, height=120, state="disabled")
        self.resume_log.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="nsew")

    def _build_injection_tab(self):
        tab = self.tabs.tab("Inject into PDF")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)
        top = ctk.CTkFrame(tab)
        top.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="PDF injection", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, padx=18, pady=(14, 8), sticky="w")
        self._path_row(top, 1, "Source PDF", "", [("PDF files", "*.pdf")], "source_pdf")
        ctk.CTkLabel(top, text="Output PDF").grid(row=2, column=0, padx=(18, 8), pady=(8, 14), sticky="w")
        self.inject_output = self._entry(top, str(OUTPUT_DIR / "document_injected.pdf"))
        self.inject_output.grid(row=2, column=1, padx=8, pady=(8, 14), sticky="ew")
        ctk.CTkButton(top, text="Save as", width=82, command=lambda: self._save_as(self.inject_output, ".pdf")).grid(row=2, column=2, padx=(8, 18), pady=(8, 14))
        options = ctk.CTkFrame(tab)
        options.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(options, text="Injection content and techniques", font=ctk.CTkFont(size=17, weight="bold")).grid(row=0, column=0, columnspan=3, padx=18, pady=(14, 8), sticky="w")
        ctk.CTkLabel(options, text="YAML preset").grid(row=1, column=0, padx=(18, 8), pady=(0, 8), sticky="w")
        preset_values = [self._preset_label(preset) for preset in self.injection_presets]
        if preset_values:
            self.preset_selector = ctk.CTkOptionMenu(options, values=preset_values, command=self._select_preset)
            self.preset_selector.grid(row=1, column=1, padx=8, pady=(0, 8), sticky="w")
        else:
            self.preset_selector = ctk.CTkOptionMenu(options, values=["No presets found"])
            self.preset_selector.configure(state="disabled")
            self.preset_selector.grid(row=1, column=1, padx=8, pady=(0, 8), sticky="w")
            ctk.CTkLabel(options, text="Add prompts to Configs/Injections.yaml to enable presets.", text_color="gray65").grid(row=1, column=2, padx=6, pady=(0, 8), sticky="w")
        self.payload = ctk.CTkTextbox(options, height=92)
        self.payload.grid(row=2, column=0, columnspan=3, padx=18, pady=(0, 10), sticky="ew")
        self.payload.insert("1.0", self.injection_presets[0]["prompt_text"].strip() if self.injection_presets else DEFAULT_PAYLOAD)
        self.technique_vars = {}
        techniques = [("white_text", "White text", "1pt white text at page bottom"), ("micro_font", "Micro font", "0.5pt near-white text"), ("metadata", "Metadata", "Document properties and XMP"), ("offpage_text", "Off-page text", "Text outside visible page area"), ("zero_width_chars", "Zero-width characters", "Unicode zero-width encoding"), ("hidden_ocg_layer", "Hidden layer", "Optional content layer disabled by default")]
        for index, (key, title, description) in enumerate(techniques):
            var = ctk.BooleanVar(value=key == "metadata")
            self.technique_vars[key] = var
            ctk.CTkCheckBox(options, text=title, variable=var).grid(row=3 + index // 2, column=index % 2, padx=18, pady=7, sticky="w")
            ctk.CTkLabel(options, text=description, text_color="gray65", font=ctk.CTkFont(size=11)).grid(row=3 + index // 2, column=2, padx=6, pady=7, sticky="w")
        self.inject_button = ctk.CTkButton(tab, text="Generate injected PDF", height=40, command=self._inject_pdf)
        self.inject_button.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="e")
        self.inject_log = ctk.CTkTextbox(tab, height=120, state="disabled")
        self.inject_log.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")

    def _choose_file(self, entry, filetypes):
        path = filedialog.askopenfilename(initialdir=ROOT, filetypes=filetypes)
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _open_listing_paste_dialog(self):
        """Open a text editor for a job description supplied without a URL."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Paste job listing")
        dialog.geometry("680x460")
        dialog.minsize(520, 360)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(dialog, text="Paste the full job description", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")
        listing_box = ctk.CTkTextbox(dialog, wrap="word")
        listing_box.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        listing_box.insert("1.0", self.job_listing_text)
        controls = ctk.CTkFrame(dialog, fg_color="transparent")
        controls.grid(row=2, column=0, padx=20, pady=(0, 18), sticky="e")

        def clear_listing():
            self.job_listing_text = ""
            self.paste_listing_button.configure(text="Paste listing")
            dialog.destroy()

        def save_listing():
            text = listing_box.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning("No job listing", "Paste a job listing or use Clear to return to the URL.", parent=dialog)
                return
            self.job_listing_text = text
            self.paste_listing_button.configure(text="Pasted listing")
            dialog.destroy()

        ctk.CTkButton(controls, text="Clear", fg_color="gray35", hover_color="gray28", command=clear_listing).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(controls, text="Use pasted listing", command=save_listing).grid(row=0, column=1)

    @staticmethod
    def _preset_label(preset):
        level = preset.get("bullshit_level", "?")
        return f"Level {level} (preset {preset.get('id', '?')})"

    def _select_preset(self, label):
        preset = next((item for item in self.injection_presets if self._preset_label(item) == label), None)
        if preset:
            self.payload.delete("1.0", "end")
            self.payload.insert("1.0", preset["prompt_text"].strip())

    def _save_as(self, entry, extension):
        path = filedialog.asksaveasfilename(initialdir=OUTPUT_DIR, defaultextension=extension, filetypes=[(f"{extension.upper()[1:]} files", f"*{extension}")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _log(self, box, message):
        box.configure(state="normal")
        box.insert("end", message.rstrip() + "\n")
        box.see("end")
        box.configure(state="disabled")

    def _run_background(self, button, log, task):
        button.configure(state="disabled")
        self.status.configure(text="Working...")
        def worker():
            try:
                self._task_results.put((button, log, task(), False))
            except Exception as exc:
                self._task_results.put((button, log, str(exc), True))
        threading.Thread(target=worker, daemon=True).start()

    def _process_task_results(self):
        """Apply worker results from Tk's main thread only."""
        try:
            while True:
                self._complete(*self._task_results.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._process_task_results)

    def _complete(self, button, log, message, error):
        self._log(log, ("Error: " if error else "Done: ") + message)
        self.status.configure(text="Finished with an error" if error else "Ready")
        button.configure(state="normal")
        if error:
            messagebox.showerror("Emploki", message)

    def _generate_resume(self):
        url, data, template, output = self.job_url.get().strip(), self.resume_data.get().strip(), self.resume_template.get().strip(), self.tex_output.get().strip()
        pasted_listing = self.job_listing_text.strip()
        if not (url or pasted_listing) or not data or not template or not output:
            messagebox.showwarning("Missing information", "Provide a job URL or pasted listing, data file, template, and output path.")
            return
        if not pasted_listing and not url.startswith(("https://", "http://")):
            messagebox.showwarning("Invalid job URL", "Enter a full URL beginning with https:// or http://.")
            return
        self._log(self.resume_log, "Using pasted job listing and asking Ollama to generate the resume..." if pasted_listing else "Fetching the job posting, then asking Ollama to generate the resume...")
        def task():
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            handler = PromptHandler(url, model=self.model.get().strip(), resume_data_path=data, resume_template_path=template, job_offer_text=pasted_listing or None)
            tex, pdf = handler.generate_resume_latex(output, pdf_engine=self.pdf_engine.get(), compile_pdf=self.compile_pdf.get())
            return f"LaTeX saved to {tex}" + (f"\nPDF saved to {pdf}" if pdf else "")
        self._run_background(self.resume_button, self.resume_log, task)

    def _inject_pdf(self):
        source, output, payload = self.source_pdf.get().strip(), self.inject_output.get().strip(), self.payload.get("1.0", "end-1c").strip()
        if not source or not output or not payload:
            messagebox.showwarning("Missing information", "Provide a source PDF, payload text, and output path.")
            return
        options = {name: variable.get() for name, variable in self.technique_vars.items()}
        if not any(options.values()):
            messagebox.showwarning("Choose a technique", "Enable at least one injection technique.")
            return
        def task():
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            return f"Injected PDF saved to {inject_pdf(source, payload, output_pdf=output, **options)}"
        self._run_background(self.inject_button, self.inject_log, task)


if __name__ == "__main__":
    EmplokiApp().mainloop()
