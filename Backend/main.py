import uuid
import subprocess
from flask_cors import CORS
import zipfile
from flask import Flask, request, jsonify, send_file
import os
import sys
import librosa
import pretty_midi
import numpy as np
import json
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "separated"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
#--------------Help Function ----------------
def detect_key(audio_path):
    y, sr = librosa.load(audio_path)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

    best_key = ""
    best_score = -1
    for i in range(12):
        rotated_major = major_profile[i:] + major_profile[:i]
        rotated_minor = minor_profile[i:] + minor_profile[:i]
        score_major = sum(a * b for a, b in zip(chroma_mean, rotated_major))
        score_minor = sum(a * b for a, b in zip(chroma_mean, rotated_minor))
        if score_major > best_score:
            best_score = score_major
            best_key = f"{keys[i]}_major"
        if score_minor > best_score:
            best_score = score_minor
            best_key = f"{keys[i]}_minor"

    return best_key

def detect_chords(audio_path):
    y, sr = librosa.load(audio_path)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    times = librosa.times_like(chroma, sr=sr)

    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    major_pattern = [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]
    minor_pattern = [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0]

    raw_chords = []
    hop = 172  # 1 bar
    for i in range(0, chroma.shape[1], hop):
        frame = chroma[:, i]
        best, best_score = "C", -1
        for r in range(12):
            maj = sum(frame[(r + j) % 12] * major_pattern[j] for j in range(12))
            min_ = sum(frame[(r + j) % 12] * minor_pattern[j] for j in range(12))
            if maj > best_score:
                best_score, best = maj, f"{keys[r]}maj"
            if min_ > best_score:
                best_score, best = min_, f"{keys[r]}min"
        raw_chords.append((times[i], best))

    # Merge consecutive duplicate chords
    chords = []
    for time, chord in raw_chords:
        if not chords or chords[-1][1] != chord:
            chords.append((time, chord))

    return chords

def chords_to_midi(chords, output_path, bpm, key=""):
    midi = pretty_midi.PrettyMIDI(resolution=480, initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=0, name=f"Chords_{int(bpm)}bpm_{key}")

    note_map = {'C': 60, 'C#': 61, 'D': 62, 'D#': 63, 'E': 64, 'F': 65,
                'F#': 66, 'G': 67, 'G#': 68, 'A': 69, 'A#': 70, 'B': 71}
    major_intervals = [0, 4, 7]
    minor_intervals = [0, 3, 7]

    for i, (time, chord) in enumerate(chords):
        end = chords[i+1][0] if i+1 < len(chords) else time + 2.0
        root = chord[:-3]
        intervals = major_intervals if chord.endswith("maj") else minor_intervals
        root_note = note_map.get(root, 60)
        for interval in intervals:
            note = pretty_midi.Note(velocity=80, pitch=root_note + interval,
                                    start=time, end=end)
            inst.notes.append(note)

    midi.instruments.append(inst)
    midi.write(output_path)

def cleanup_old_files(max_age_minutes=5):
    import time
    now = time.time()
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for root, dirs, files in os.walk(folder, topdown=False):
            for f in files:
                fpath = os.path.join(root, f)
                if f.startswith('.reaforge'):
                    continue
                if os.path.getmtime(fpath) < now - (max_age_minutes * 60):
                    try:
                        os.remove(fpath)
                    except:
                        pass  # skip locked files
            for d in dirs:
                dpath = os.path.join(root, d)
                try:
                    os.rmdir(dpath)
                except:
                    pass

# ---------------Enpoints-------------------
@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(__file__), "../Frontend/index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.route("/separate", methods=["POST"])
def separate():
    cleanup_old_files()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    uid = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, uid + "_" + file.filename)
    file.save(input_path)

    try:
        subprocess.run([
            sys.executable, "-m", "demucs",
            "--out", OUTPUT_FOLDER,
            "-n", "htdemucs",
            "--mp3",
            input_path
        ], check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Separation failed", "details": str(e)}), 500

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    stem_dir = os.path.join(OUTPUT_FOLDER, "htdemucs", base_name)
    if not os.path.exists(stem_dir):
        return jsonify({"error": "Output not found"}), 500

    y, sr = librosa.load(input_path)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    detected_bpm = int(np.round(tempo))  #------ Detect BPM
    detected_key = detect_key(input_path)  #----- Detect Key


    stem_files = []
    for stem_file in os.listdir(stem_dir):
        old_path = os.path.join(stem_dir, stem_file)
        name, ext = os.path.splitext(stem_file)
        new_name = f"{name}_{detected_bpm}bpm_{detected_key}{ext}"
        new_path = os.path.join(stem_dir, new_name)
        os.rename(old_path, new_path)
        stem_files.append(os.path.abspath(new_path))

    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return jsonify({"stems": stem_files, "bpm": detected_bpm, "key": detected_key})
    else:
        zip_path = os.path.join(OUTPUT_FOLDER, uid + "_stems.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for stem_path in stem_files:
                zf.write(stem_path, os.path.basename(stem_path))
        return send_file(zip_path, as_attachment=True, download_name="stems.zip")


@app.route("/instrumental", methods=["POST"])
def instrumental():
    cleanup_old_files()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    uid = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, uid + "_" + file.filename)
    file.save(input_path)

    try:
        subprocess.run([
            sys.executable, "-m", "demucs",
            "--out", OUTPUT_FOLDER,
            "-n", "htdemucs",
            "--mp3",
            input_path
        ], check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Separation failed", "details": str(e)}), 500

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    stem_dir = os.path.join(OUTPUT_FOLDER, "htdemucs", base_name)
    if not os.path.exists(stem_dir):
        return jsonify({"error": "Output not found"}), 500

    # Merge bass + drums + other into instrumental (no vocals)
    from pydub import AudioSegment
    stems_to_merge = ["bass.mp3", "drums.mp3", "other.mp3"]
    combined = None
    for stem_file in stems_to_merge:
        stem_path = os.path.join(stem_dir, stem_file)
        if os.path.exists(stem_path):
            audio = AudioSegment.from_mp3(stem_path)
            combined = audio if combined is None else combined.overlay(audio)

    if combined is None:
        return jsonify({"error": "Could not merge stems"}), 500

    instrumental_path = os.path.join(OUTPUT_FOLDER, uid + "_instrumental.mp3")
    combined.export(instrumental_path, format="mp3")

    return send_file(instrumental_path, as_attachment=True, download_name="instrumental.mp3")


@app.route("/extract_midi", methods=["POST"])
def extract_midi():
    cleanup_old_files()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    uid = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, uid + "_" + file.filename)
    file.save(input_path)

    output_dir = os.path.join(OUTPUT_FOLDER, uid + "_midi")
    os.makedirs(output_dir, exist_ok=True)

    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH


    # Detect BPM automatically
    y, sr = librosa.load(input_path)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    detected_bpm = float(np.round(tempo)) # Detect BPM
    detected_key = detect_key(input_path)  # Detect Key
    print(f"Detected BPM: {detected_bpm}\n")

    _, midi_data, _ = predict(input_path, ICASSP_2022_MODEL_PATH)

    #tempo_in_microseconds = 60000000 / detected_bpm
    midi_fixed = pretty_midi.PrettyMIDI(resolution=480, initial_tempo=detected_bpm)
    for instrument in midi_data.instruments:
        midi_fixed.instruments.append(instrument)

    midi_path = os.path.join(output_dir, f"output_{int(detected_bpm)}bpm_{detected_key}.mid")
    midi_fixed.write(midi_path)

    return jsonify({"midi": os.path.abspath(midi_path), "bpm": detected_bpm, "key": detected_key})  # UPDATE THIS


@app.route("/chordmap", methods=["POST"])
def chordmap():
    cleanup_old_files()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    uid = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, uid + "_" + file.filename)
    file.save(input_path)

    y, sr = librosa.load(input_path)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    detected_bpm = float(np.round(tempo))
    detected_key = detect_key(input_path)

    chords = detect_chords(input_path)

    output_dir = os.path.join(OUTPUT_FOLDER, uid + "_chords")
    os.makedirs(output_dir, exist_ok=True)
    midi_path = os.path.join(output_dir,
                             f"chords_{int(detected_bpm)}bpm_{detected_key}.mid")
    chords_to_midi(chords, midi_path, detected_bpm, detected_key)

    return jsonify({"midi": os.path.abspath(midi_path),
                    "bpm": detected_bpm, "key": detected_key})


@app.route("/vocal_clean", methods=["POST"])
def vocal_clean():
    cleanup_old_files()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    uid = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, uid + "_" + file.filename)
    file.save(input_path)

    # Check mono preference
    options_file = os.path.join(UPLOAD_FOLDER, ".reaforge_result.json")
    force_mono = False
    if os.path.exists(options_file):
        with open(options_file) as f:
            opts = json.load(f)
        force_mono = opts.get("mono", False)
        os.remove(options_file)

    import noisereduce as nr
    import soundfile as sf
    import librosa

    y, sr = librosa.load(input_path, sr=None, mono=False)

    # For noise reduction, use mono version
    y_mono = librosa.to_mono(y) if len(y.shape) > 1 else y
    noise_sample = y_mono[:int(sr * 0.5)]
    cleaned_mono = nr.reduce_noise(y=y_mono, sr=sr, y_noise=noise_sample, prop_decrease=0.8)

    output_dir = os.path.join(OUTPUT_FOLDER, uid + "_vocalclean")
    os.makedirs(output_dir, exist_ok=True)

    # After cleaning, apply mono if checked
    # Apply to original channels
    if force_mono or len(y.shape) == 1:
        cleaned = cleaned_mono
    else:
        # Apply noise reduction to each channel separately
        cleaned_ch1 = nr.reduce_noise(y=y[0], sr=sr, y_noise=y[0][:int(sr * 0.5)], prop_decrease=0.8)
        cleaned_ch2 = nr.reduce_noise(y=y[1], sr=sr, y_noise=y[1][:int(sr * 0.5)], prop_decrease=0.8)
        cleaned = np.array([cleaned_ch1, cleaned_ch2])

    detected_key = detect_key(input_path)
    tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
    detected_bpm = int(np.round(tempo))

    output_path = os.path.join(output_dir, f"vocals_clean_{detected_bpm}bpm_{detected_key}.wav")
    sf.write(output_path, cleaned.T if len(cleaned.shape) > 1 else cleaned, int(sr), format='WAV', subtype='PCM_16')

    return jsonify({
        "audio": os.path.abspath(output_path),
        "bpm": detected_bpm,
        "key": detected_key
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)