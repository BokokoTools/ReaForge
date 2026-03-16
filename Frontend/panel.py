"""
ReaForge - panel.py
Tkinter UI panel — launched from ai_tools.py as a subprocess
by BokokoTools

Usage: python panel.py <filepath>
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
import threading
import urllib.request
import urllib.error
import json

FLASK_URL = "http://127.0.0.1:5000"

# ─────────────────────────────────────────────
# FLASK COMMUNICATION
# ─────────────────────────────────────────────

def call_flask(endpoint, filepath, on_success, on_error, status_var):
    def run():
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            filename = os.path.basename(filepath)
            body = (
                b'------FormBoundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
                b'Content-Type: audio/wav\r\n\r\n' +
                file_data +
                b'\r\n------FormBoundary--\r\n'
            )

            req = urllib.request.Request(
                f"{FLASK_URL}/{endpoint}", data=body,
                headers={
                    'Content-Type': 'multipart/form-data; boundary=----FormBoundary',
                    'Accept': 'application/json'
                }
            )
            response = urllib.request.urlopen(req, timeout=300)
            result = json.loads(response.read().decode('utf-8', errors='ignore'))
            on_success(result)

        except urllib.error.URLError:
            on_error("Cannot connect to ReaForge backend.\nMake sure Flask is running:\n  python Backend/main.py")
        except Exception as e:
            on_error(f"Error: {str(e)}")

    status_var.set("Processing... please wait")
    thread = threading.Thread(target=run, daemon=True)
    thread.start()


# ─────────────────────────────────────────────
# MAIN PANEL
# ─────────────────────────────────────────────

class ReaForgePanel:
    def __init__(self, filepath):
        self.filepath = filepath
        self.root = tk.Tk()
        self.root.title("ReaForge")
        self.root.geometry("320x480")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a1a")

        self.status_var = tk.StringVar(value="Ready")
        self.result_data = {}

        self._build_ui()

    def _build_ui(self):
        # ── Header ──
        header = tk.Frame(self.root, bg="#111111", pady=12)
        header.pack(fill="x")

        tk.Label(header, text="ReaForge", font=("Courier New", 20, "bold"),
                 fg="#00ff88", bg="#111111").pack()
        tk.Label(header, text="by BokokoTools", font=("Courier New", 9),
                 fg="#555555", bg="#111111").pack()

        # ── File info ──
        filename = os.path.basename(self.filepath)
        file_frame = tk.Frame(self.root, bg="#222222", pady=8, padx=12)
        file_frame.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(file_frame, text="File:", font=("Courier New", 8),
                 fg="#666666", bg="#222222").pack(anchor="w")
        tk.Label(file_frame, text=filename[:40] + ("..." if len(filename) > 40 else ""),
                 font=("Courier New", 9), fg="#aaaaaa", bg="#222222",
                 wraplength=280).pack(anchor="w")

        # ── Buttons ──
        btn_frame = tk.Frame(self.root, bg="#1a1a1a", pady=10)
        btn_frame.pack(fill="both", expand=True, padx=12)

        buttons = [
            ("🎵  Separate Stems", "#00ff88", "#003322", self.separate_stems),
            ("🎹  Extract MIDI",   "#00aaff", "#001133", self.extract_midi),
            ("🎸  ChordMap",       "#ff8800", "#221100", self.chordmap),
            ("🎤  VocalClean",     "#ff44aa", "#220011", self.vocal_clean),
        ]

        for text, fg, bg, cmd in buttons:
            btn = tk.Button(
                btn_frame, text=text,
                font=("Courier New", 11, "bold"),
                fg=fg, bg=bg,
                activeforeground=fg, activebackground="#333333",
                relief="flat", bd=0, pady=12,
                cursor="hand2",
                command=cmd
            )
            btn.pack(fill="x", pady=4)

        # ── Status ──
        status_frame = tk.Frame(self.root, bg="#111111", pady=8)
        status_frame.pack(fill="x", side="bottom")

        tk.Label(status_frame, textvariable=self.status_var,
                 font=("Courier New", 9), fg="#888888",
                 bg="#111111", wraplength=300).pack()

        # ── Cancel ──
        tk.Button(
            self.root, text="Close",
            font=("Courier New", 9),
            fg="#555555", bg="#1a1a1a",
            relief="flat", cursor="hand2",
            command=self.root.destroy
        ).pack(side="bottom", pady=4)

    # ── Actions ──

    def _on_success(self, result, message):
        self.result_data = result
        self.status_var.set(message)
        # Write result to temp file so ai_tools.py can read it
        tmp = os.path.join(os.path.dirname(self.filepath), ".reaforge_result.json")
        with open(tmp, "w") as f:
            json.dump(result, f)

    def _on_error(self, msg):
        self.status_var.set(f"Error: {msg}")

    def separate_stems(self):
        call_flask("separate", self.filepath,
                   lambda r: self._on_success(r, f"Done! {len(r.get('stems',[]))} stems ready. BPM: {r.get('bpm','?')} | Key: {r.get('key','?')}"),
                   self._on_error, self.status_var)

    def extract_midi(self):
        call_flask("extract_midi", self.filepath,
                   lambda r: self._on_success(r, f"MIDI ready. BPM: {r.get('bpm','?')} | Key: {r.get('key','?')}"),
                   self._on_error, self.status_var)

    def chordmap(self):
        call_flask("chordmap", self.filepath,
                   lambda r: self._on_success(r, f"Chords ready. BPM: {r.get('bpm','?')} | Key: {r.get('key','?')}"),
                   self._on_error, self.status_var)

    def vocal_clean(self):
        self.status_var.set("VocalClean coming soon...")

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python panel.py <filepath>")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    panel = ReaForgePanel(filepath)
    panel.run()