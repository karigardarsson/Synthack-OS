from __future__ import annotations
import queue, threading, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from max_builder import build, digest_path
class App(ttk.Frame):
    def __init__(self,root):
        super().__init__(root,padding=18);self.grid(sticky="nsew");root.title("Syntakt MAX 1.0 Builder");root.minsize(650,260)
        self.src=tk.StringVar();self.status=tk.StringVar(value="Choose your official Syntakt OS 1.41 .syx file.")
        ttk.Label(self,text="Syntakt MAX 1.0 Builder",font=("Segoe UI",16,"bold")).grid(row=0,column=0,columnspan=3,sticky="w")
        ttk.Label(self,text="Builds locally. It never sends firmware to a device.").grid(row=1,column=0,columnspan=3,sticky="w",pady=(0,12))
        ttk.Label(self,text="Official OS 1.41 file").grid(row=2,column=0,sticky="w");ttk.Entry(self,textvariable=self.src,width=64).grid(row=3,column=0,columnspan=2,sticky="ew");ttk.Button(self,text="Choose…",command=self.choose).grid(row=3,column=2,padx=(8,0))
        self.hash=ttk.Label(self,text="Expected SHA-256: 8e2488f4…cb9ed19e");self.hash.grid(row=4,column=0,columnspan=3,sticky="w",pady=(5,12))
        self.go=ttk.Button(self,text="Build and Save MAX 1.0",command=self.start);self.go.grid(row=5,column=0,sticky="w");ttk.Label(self,textvariable=self.status,wraplength=600).grid(row=6,column=0,columnspan=3,sticky="w",pady=(15,0))
        self.q=queue.Queue();self.after(120,self.poll)
    def choose(self):
        p=filedialog.askopenfilename(filetypes=[("Syntakt firmware","*.syx"),("All files","*.*")])
        if p:self.src.set(p);self.hash.configure(text="Selected SHA-256: "+digest_path(p))
    def start(self):
        if not self.src.get():return messagebox.showerror("Syntakt MAX","Choose an OS 1.41 .syx file first.")
        out=filedialog.asksaveasfilename(defaultextension=".syx",initialfile="Syntakt_MAX_1.0.syx",filetypes=[("SysEx firmware","*.syx")])
        if not out:return
        self.go.state(["disabled"]);self.status.set("Starting local build…");threading.Thread(target=self.worker,args=(self.src.get(),out),daemon=True).start()
    def worker(self,src,out):
        try:self.q.put(("ok",build(src,out,lambda s:self.q.put(("progress",s)))))
        except Exception as e:self.q.put(("error",str(e)))
    def poll(self):
        try:
            while True:
                kind,val=self.q.get_nowait()
                if kind=="progress":self.status.set(val)
                elif kind=="ok":self.status.set("Complete: "+val["sha256"]);messagebox.showinfo("Syntakt MAX","Build verified and saved.\n\nSHA-256: "+val["sha256"])
                else:self.status.set("No output was saved.");messagebox.showerror("Syntakt MAX","Build failed. No output was saved.\n\n"+val)
                if kind in ("ok","error"):self.go.state(["!disabled"])
        except queue.Empty:pass
        self.after(120,self.poll)
root=tk.Tk();root.columnconfigure(0,weight=1);root.rowconfigure(0,weight=1);App(root);root.mainloop()
