
import urllib.request
import json
import os

FLASK_URL = "http://127.0.0.1:5000"

def get_selected_track_file():
    track = RPR_GetSelectedTrack(0, 0)
    if not track:
        RPR_ShowMessageBox("No track selected.", "LyricSheet", 0)
        return None
    item = RPR_GetTrackMediaItem(track, 0)
    take = RPR_GetActiveTake(item)
    source = RPR_GetMediaItemTake_Source(take)
    return RPR_GetMediaSourceFileName(source, "", 512)[1]

def call_flask(filepath):
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
        f"{FLASK_URL}/lyricsheet", data=body,
        headers={
            'Content-Type': 'multipart/form-data; boundary=----FormBoundary',
            'Accept': 'application/json'
        }
    )
    response = urllib.request.urlopen(req, timeout=300)
    return json.loads(response.read().decode('utf-8', errors='ignore'))

def main():
    filepath = get_selected_track_file()
    if not filepath:
        return

    RPR_ShowConsoleMsg("LyricSheet: Transcribing vocals, please wait...\n")

    result = call_flask(filepath)
    if not result or "markers" not in result:
        RPR_ShowMessageBox("Transcription failed.", "LyricSheet", 0)
        return

    # Add each line as a Reaper timeline marker
    for marker in result["markers"]:
        RPR_AddProjectMarker2(0, False, marker["time"], 0, marker["text"], -1, 0)

    RPR_ShowConsoleMsg(f"LyricSheet: Done! {len(result['markers'])} markers added.\n")
    RPR_ShowConsoleMsg(f"\nFull lyrics:\n{result['full_text']}\n")

main()