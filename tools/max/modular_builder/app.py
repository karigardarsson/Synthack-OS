"""Windows interface for the offline Syntakt OS 1.41 modular builder."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from modular_builder import FEATURES, PRESETS, BuildError, build, digest_path, resolve

STOCK_HASH = "8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e"


class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=18)
        self.grid(sticky="nsew")
        root.title("Syntakt MAX Modular Builder")
        root.minsize(720, 570)
        root.columnconfigure(0, weight=1)
        self.source = tk.StringVar()
        self.status = tk.StringVar(value="Choose your official Syntakt OS 1.41 file.")
        self.compatibility = tk.StringVar()
        self.preset = tk.StringVar(value="MAX FULL + FM4")
        self.enabled = {key: tk.BooleanVar(value=key in PRESETS["MAX FULL + FM4"])
                        for key, _, _ in FEATURES}
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        ttk.Label(self, text="Syntakt MAX Modular Builder", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self, text="Builds locally from your official OS 1.41 file. No device connection.").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(self, text="Official OS 1.41 .syx").grid(row=2, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.source, width=72).grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(self, text="Choose…", command=self.choose).grid(row=3, column=2, padx=(8, 0))
        self.hash = ttk.Label(self, text="Required SHA-256: " + STOCK_HASH)
        self.hash.grid(row=4, column=0, columnspan=3, sticky="w", pady=(5, 13))

        ttk.Label(self, text="Preset").grid(row=5, column=0, sticky="w")
        self.preset_box = ttk.Combobox(self, textvariable=self.preset, state="readonly",
                                      values=[*PRESETS, "CUSTOM"], width=26)
        self.preset_box.grid(row=6, column=0, sticky="w", pady=(3, 10))
        self.preset_box.bind("<<ComboboxSelected>>", self.choose_preset)

        grid = ttk.LabelFrame(self, text="Feature groups", padding=10)
        grid.grid(row=7, column=0, columnspan=3, sticky="ew")
        for index, (key, label, _) in enumerate(FEATURES):
            ttk.Checkbutton(grid, text=label, variable=self.enabled[key],
                            command=self.feature_changed).grid(row=index // 2, column=index % 2,
                                                               sticky="w", padx=(0, 35), pady=3)
        ttk.Label(self, textvariable=self.compatibility, wraplength=670).grid(row=8, column=0, columnspan=3,
                                                                              sticky="w", pady=(12, 10))
        self.go = ttk.Button(self, text="Build and Save Firmware", command=self.start)
        self.go.grid(row=9, column=0, sticky="w")
        ttk.Label(self, textvariable=self.status, wraplength=670).grid(row=10, column=0, columnspan=3,
                                                                       sticky="w", pady=(14, 0))
        self.refresh()
        self.after(120, self.poll)

    def selection(self) -> frozenset[str]:
        return frozenset(key for key, flag in self.enabled.items() if flag.get())

    def choose_preset(self, _event=None) -> None:
        selected = PRESETS.get(self.preset.get())
        if selected is not None:
            for key, flag in self.enabled.items():
                flag.set(key in selected)
        self.refresh()

    def feature_changed(self) -> None:
        self.preset.set("CUSTOM")
        self.refresh()

    def refresh(self) -> None:
        try:
            mods = resolve(self.selection())
            dependencies = [mod["name"] for mod in mods if mod["name"] in ("modarea", "vparams", "splash")]
            note = "Automatic support: " + (", ".join(dependencies) if dependencies else "none needed")
            if "fm4" in self.selection():
                note += ". FM4 uses the heap-reserved loader."
            self.compatibility.set(note)
            self.go.state(["!disabled"])
        except (BuildError, OSError, ValueError) as error:
            self.compatibility.set(str(error))
            self.go.state(["disabled"])

    def choose(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Syntakt firmware", "*.syx"), ("All files", "*.*")])
        if path:
            self.source.set(path)
            try:
                got = digest_path(path)
                self.hash.configure(text="Selected SHA-256: " + got +
                                    ("  ✓" if got == STOCK_HASH else "  — incorrect input"))
            except OSError as error:
                self.hash.configure(text="Cannot read selected file: " + str(error))

    def start(self) -> None:
        if not self.source.get():
            messagebox.showerror("Syntakt MAX", "Choose your official OS 1.41 .syx file first.")
            return
        selected = self.selection()
        try:
            resolve(selected)
        except BuildError as error:
            messagebox.showerror("Syntakt MAX", str(error))
            return
        name = "Syntakt_OS1.41_" + ("MAX_FM4" if selected == PRESETS["MAX FULL + FM4"] else
                                             "MAX_1.0" if selected == PRESETS["Original MAX 1.0"] else
                                             "FM4" if selected == PRESETS["FM4 ONLY"] else "CUSTOM") + ".syx"
        output = filedialog.asksaveasfilename(defaultextension=".syx", initialfile=name,
                                              filetypes=[("SysEx firmware", "*.syx")])
        if not output:
            return
        self.go.state(["disabled"])
        self.status.set("Starting local build…")
        threading.Thread(target=self.worker, args=(self.source.get(), output, selected), daemon=True).start()

    def worker(self, source: str, output: str, selected: frozenset[str]) -> None:
        try:
            self.events.put(("ok", build(source, output, selected,
                                         lambda value: self.events.put(("progress", value)))))
        except Exception as error:
            self.events.put(("error", str(error)))

    def poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(str(value))
                elif kind == "ok":
                    report = value
                    self.status.set("Complete: " + report["output_sha256"])
                    messagebox.showinfo("Syntakt MAX", "Firmware and selected-mod manifest saved.\n\n"
                                        + report["output"] + "\nSHA-256: " + report["output_sha256"])
                else:
                    self.status.set("Build failed; no firmware was saved.")
                    messagebox.showerror("Syntakt MAX", "Build failed.\n\n" + str(value))
                if kind in ("ok", "error"):
                    self.refresh()
        except queue.Empty:
            pass
        self.after(120, self.poll)


if __name__ == "__main__":
    root = tk.Tk()
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    App(root)
    root.mainloop()
