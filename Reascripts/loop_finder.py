
import urllib.request
import json
import os

FLASK_URL = "http://127.0.0.1:5000"

def get_selected_track_file():
    track = RPR_GetSelectedTrack(0, 0)
    if not track:
        RPR_ShowMessageBox("No track selected.", "LoopFinder", 0)
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
        f"{FLASK_URL}/loopfinder", data=body,
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

    RPR_ShowConsoleMsg("LoopFinder: Analyzing track, please wait...\n")

    result = call_flask(filepath)
    if not result or "loop_start" not in result:
        RPR_ShowMessageBox("LoopFinder failed.", "LoopFinder", 0)
        return

    loop_start = result["loop_start"]
    loop_end = result["loop_end"]
    bpm = result["bpm"]

    # Set Reaper loop points
    RPR_GetSet_LoopTimeRange2(0, True, True, loop_start, loop_end, False)

    RPR_ShowConsoleMsg(f"LoopFinder: Loop set!\n")
    RPR_ShowConsoleMsg(f"Start: {loop_start:.2f}s | End: {loop_end:.2f}s\n")
    RPR_ShowConsoleMsg(f"BPM: {bpm} | {result['bars']} bars\n")

main()