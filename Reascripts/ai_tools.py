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
    track = RPR_GetSelectedTrack(0, 0)
    if not track:
        RPR.ShowMessageBox("No track selected.\nPlease select a track first.", "ReaForge", 0)
        return None

    item = RPR_GetTrackMediaItem(track, 0)
    if not item:
        RPR_ShowMessageBox("No media item found on selected track.", "ReaForge", 0)
        return None

    take = RPR_GetActiveTake(item)
    if not take:
        RPR_ShowMessageBox("No active take found.", "ReaForge", 0)
        return None

    source = RPR_GetMediaItemTake_Source(take)
    filename = RPR_GetMediaSourceFileName(source, "", 512)[1]
    return filename
def import_files_to_reaper(file_paths):
    for path in file_paths:
        if os.path.exists(path):
            RPR_SetOnlyTrackSelected(RPR_GetSelectedTrack(0, 0))
            RPR_InsertMedia(path, 1)
        else:
            RPR_ShowConsoleMsg(f"ReaForge: File not found: {path}\n")
def check_result():
    tmp_result = RPR_GetExtState("ReaForge", "tmp_result")
    if os.path.exists(tmp_result):
        with open(tmp_result, "r") as f:
            result = json.load(f)
        os.remove(tmp_result)

        if "stems" in result:
            import_files_to_reaper(result["stems"])
        elif "midi" in result:
            import_files_to_reaper([result["midi"]])
        elif "audio" in result:
            import_files_to_reaper([result["audio"]])

        RPR_ShowConsoleMsg("ReaForge: Imported!\n")

    RPR_defer("check_result()")  # keep checking

# ─────────────────────────────────────────────
# FLASK COMMUNICATION
# ─────────────────────────────────────────────

def call_flask(endpoint, filepath):
    import urllib.request
    url = f"{FLASK_URL}/{endpoint}"

    # Read the file and send it as multipart form data
    with open(filepath, 'rb') as f:
        file_data = f.read()

    filename = os.path.basename(filepath)
    boundary = b'----FormBoundary'

    body = (
            b'------FormBoundary\r\n'
            b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
                                                                                             b'Content-Type: audio/wav\r\n\r\n' +
            file_data +
            b'\r\n------FormBoundary--\r\n'
    )

    req = urllib.request.Request(
        url, data=body,
        headers={
            'Content-Type': 'multipart/form-data; boundary=----FormBoundary',
            'Accept': 'application/json'
        }
    )
    response = urllib.request.urlopen(req, timeout=300)
    return json.loads(response.read().decode('utf-8', errors='ignore'))
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
    #RPR_ShowMessageBox("Separating stems...\nThis may take 30–120 seconds.", "ReaForge", 0)
    RPR_ShowConsoleMsg("ReaForge: Separating stems, please wait...\n")
    result = call_flask("separate", filepath)
    RPR_ShowConsoleMsg(f"ReaForge result: {str(result)}\n")  # ADD THIS
    if result and "stems" in result:
        import_files_to_reaper(result["stems"])
        if "bpm" in result:
            RPR_SetCurrentBPM(0, result["bpm"], False)
        RPR_ShowMessageBox(
            f"Done! {len(result['stems'])} stems imported into Reaper.",
            "ReaForge ✓", 0
        )
    else:
        RPR_ShowMessageBox("Stem separation failed. Check the Flask server log.", "ReaForge", 0)
def extract_midi(filepath):
    """Send audio file to Flask for MIDI extraction, then import the .mid file."""
    RPR_ShowMessageBox("Extracting MIDI...\nThis may take a moment.", "ReaForge", 0)

    result = call_flask("extract_midi", filepath)
    if result and "midi" in result:
        import_files_to_reaper([result["midi"]])
        if "bpm" in result:
            RPR_SetCurrentBPM(0, result["bpm"], False)
        RPR_ShowMessageBox("Done! MIDI file imported into Reaper.", "ReaForge ✓", 0)
    else:
        RPR_ShowMessageBox("MIDI extraction failed. Check the Flask server log.", "ReaForge", 0)
def chordmap(filepath):
    RPR_ShowConsoleMsg("ReaForge: Detecting chords, please wait...\n")
    result = call_flask("chordmap", filepath)
    if result and "midi" in result:
        import_files_to_reaper([result["midi"]])
        RPR_ShowMessageBox(
            f"Done! ChordMap imported.\nKey: {result.get('key','?')} | BPM: {result.get('bpm','?')}",
            "ReaForge ✓", 0
        )
    else:
        RPR_ShowMessageBox("ChordMap failed. Check the Flask server log.", "ReaForge", 0)

#--------- Open Dialog For which to execute ---------
def open_panel(filepath):
    panel_script = r"C:\Users\Bokoko\PycharmProjects\ReaForge\Frontend\panel.py"
    tmp_result = r"C:\Users\Bokoko\PycharmProjects\ReaForge\Backend\uploads\.reaforge_result.json"

    # Clean old result
    if os.path.exists(tmp_result):
        os.remove(tmp_result)

    # Launch panel WITHOUT waiting
    subprocess.Popen([
        r"C:\Users\Bokoko\AppData\Local\Programs\Python\Python310\python.exe",
        panel_script, filepath
    ], creationflags=0x08000000)

    import time
    for _ in range(90):
        time.sleep(2)
        RPR_UpdateArrange()  # lets Reaper breathe
        if os.path.exists(tmp_result):
            with open(tmp_result, "r") as f:
                result = json.load(f)
            os.remove(tmp_result)
            if "stems" in result:
                import_files_to_reaper(result["stems"])
            elif "midi" in result:
                import_files_to_reaper([result["midi"]])
            elif "audio" in result:
                import_files_to_reaper([result["audio"]])
            return


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def main():
    filepath = get_selected_track_file()
    if not filepath:
        return

    if not os.path.exists(filepath):
        RPR_ShowMessageBox(
            f"File not found:\n{filepath}\n\nMake sure the audio file exists on disk.",
            "ReaForge", 0
        )
        return

    open_panel(filepath)
main()