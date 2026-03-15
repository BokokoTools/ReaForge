# ReaForge
**by BokokoTools**

AI-powered audio tools for Reaper — stem separation, MIDI extraction, and more. Built for producers who want to work faster without leaving their DAW.

---

## What it does

- 🎵 **Stem Separation** — Split any track into vocals, drums, bass, and other using Demucs
- 🎹 **MIDI Extraction** — Convert audio to MIDI using Spotify's basic-pitch (runs locally, no internet needed)
- 🔁 **Auto-import** — Stems and MIDI files are automatically added back into your Reaper session
- 🖥️ **Panel UI** — Simple checkbox interface launched directly from a Reaper shortcut

---

## Project Structure

```
ReaForge/
├── reascripts/
│   └── ai_tools.py        # Reaper ReaScript — runs inside Reaper
├── Backend/
│   ├── main.py            # Flask server — handles all AI processing
│   ├── requirements.txt
│   └── uploads/
│       └── separated/     # Output folder for stems
├── Frontend/
│   └── index.html         # Optional web UI
└── README.md
```

---

## Requirements

- Python 3.10+
- Reaper (with ReaScript Python enabled)
- Dependencies:

```bash
pip install flask demucs basic-pitch
```

---

## Setup

### 1. Enable Python in Reaper
Go to **Preferences → ReaScript → Enable Python** and point it to your Python installation.

### 2. Start the Flask backend
```bash
cd Backend
python main.py
```
The server runs on `http://127.0.0.1:5000`

### 3. Load the ReaScript in Reaper
Go to **Actions → ReaScript → Load** and select `reascripts/ai_tools.py`.
Assign it a keyboard shortcut (e.g. `Alt+A`).

### 4. Run it
Select a track in Reaper, press your shortcut, choose what you want to do, and ReaForge handles the rest.

---

## How it works

```
Reaper (ReaScript)
      ↓
Flask Backend (localhost:5000)
      ↓
Demucs / basic-pitch
      ↓
Output files → auto-imported back into Reaper
```

---

## Roadmap

- [ ] Tkinter panel with checkboxes for all tools
- [ ] GPT layer for MIDI cleanup and quantization
- [ ] Key and BPM detection
- [ ] Chord recognition
- [ ] Reaper extension packaging (.ext)

---

## Made by

**Bokoko / Tshutshe** — producer and developer  
GitHub: [BokokoTools](https://github.com/BokokoTools)

---

> ReaForge is free and open source. If it helps your workflow, share it with other Reaper producers.