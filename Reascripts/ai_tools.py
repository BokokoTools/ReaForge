"""
ReaForge - ai_tools.py
ReaScript for Reaper — connects to Flask backend for stem separation and MIDI extraction
by BokokoTools

HOW TO USE:
1. Start your Flask backend: python Backend/main.py
2. In Reaper: Actions > ReaScript > Load > select this file
3. Assign a keyboard shortcut (e.g. Alt+A)
4. Select a track in Reaper and press your shortcut
"""

import reaper_python as RPR
import urllib.request
import urllib.error
import json
import os
import subprocess
import sys

FLASK_URL = "http://127.0.0.1:5000"


# ─────────────────────────────────────────────
# REAPER HELPERS
# ─────────────────────────────────────────────

def get_selected_track_file():
    """Get the audio file path from the first selected track in Reaper."""
    track = RPR.GetSelectedTrack(0, 0)
    if not track:
        RPR.ShowMessageBox("No track selected.\nPlease select a track first.", "ReaForge", 0)
        return None

    item = RPR.GetTrackMediaItem(track, 0)
    if not item:
        RPR.ShowMessageBox("No media item found on selected track.", "ReaForge", 0)
        return None

    take = RPR.GetActiveTake(item)
    if not take:
        RPR.ShowMessageBox("No active take found.", "ReaForge", 0)
        return None

    source = RPR.GetMediaItemTake_Source(take)
    filename = RPR.GetMediaSourceFileName(source, "", 512)[1]
    return filename


def import_files_to_reaper(file_paths):
    """Import a list of audio/MIDI files as new tracks in Reaper."""
    for path in file_paths:
        if os.path.exists(path):
            RPR.InsertMedia(path, 0)


# ─────────────────────────────────────────────
# FLASK COMMUNICATION
# ─────────────────────────────────────────────

def call_flask(endpoint, payload):
    """Send a POST request to the Flask backend and return the JSON response."""
    url = f"{FLASK_URL}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        response = urllib.request.urlopen(req, timeout=120)
        return json.loads(response.read())
    except urllib.error.URLError:
        RPR.ShowMessageBox(
            "Cannot connect to ReaForge backend.\n\n"
            "Make sure your Flask server is running:\n"
            "  cd Backend\n"
            "  python main.py",
            "ReaForge — Connection Error", 0
        )
        return None
    except Exception as e:
        RPR.ShowMessageBox(f"Error: {str(e)}", "ReaForge", 0)
        return None


def check_backend_running():
    """Check if Flask backend is reachable."""
    try:
        urllib.request.urlopen(f"{FLASK_URL}/ping", timeout=3)
        return True
    except:
        return False


# ─────────────────────────────────────────────
# ACTIONS
# ─────────────────────────────────────────────

def separate_stems(filepath):
    """Send audio file to Flask for stem separation, then import stems into Reaper."""
    RPR.ShowMessageBox("Separating stems...\nThis may take 30–120 seconds.", "ReaForge", 0)

    result = call_flask("separate", {"file": filepath})
    if result and "stems" in result:
        import_files_to_reaper(result["stems"])
        RPR.ShowMessageBox(
            f"Done! {len(result['stems'])} stems imported into Reaper.",
            "ReaForge ✓", 0
        )
    else:
        RPR.ShowMessageBox("Stem separation failed. Check the Flask server log.", "ReaForge", 0)


def extract_midi(filepath):
    """Send audio file to Flask for MIDI extraction, then import the .mid file."""
    RPR.ShowMessageBox("Extracting MIDI...\nThis may take a moment.", "ReaForge", 0)

    result = call_flask("extract_midi", {"file": filepath})
    if result and "midi" in result:
        import_files_to_reaper([result["midi"]])
        RPR.ShowMessageBox("Done! MIDI file imported into Reaper.", "ReaForge ✓", 0)
    else:
        RPR.ShowMessageBox("MIDI extraction failed. Check the Flask server log.", "ReaForge", 0)


def open_panel(filepath):
    """
    Launch the tkinter UI panel as a subprocess.
    The panel lets the user pick which tools to run with checkboxes.
    Falls back to a simple message box if the panel script is not found.
    """
    panel_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "Frontend", "panel.py"
    )

    if os.path.exists(panel_script):
        subprocess.Popen([sys.executable, panel_script, filepath])
    else:
        # Fallback: simple dialog if panel.py doesn't exist yet
        choice = RPR.ShowMessageBox(
            "Choose an action:\n\n"
            "OK  → Separate Stems\n"
            "Cancel → Extract MIDI",
            "ReaForge", 1
        )
        if choice == 1:
            separate_stems(filepath)
        else:
            extract_midi(filepath)


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def main():
    filepath = get_selected_track_file()
    if not filepath:
        return

    if not os.path.exists(filepath):
        RPR.ShowMessageBox(
            f"File not found:\n{filepath}\n\nMake sure the audio file exists on disk.",
            "ReaForge", 0
        )
        return

    open_panel(filepath)


main()