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

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "separated"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(__file__), "../Frontend/index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.route("/separate", methods=["POST"])
def separate():
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
    detected_bpm = int(np.round(tempo))

    stem_files = []
    for stem_file in os.listdir(stem_dir):
        old_path = os.path.join(stem_dir, stem_file)
        name, ext = os.path.splitext(stem_file)
        new_name = f"{name}_{detected_bpm}bpm{ext}"
        new_path = os.path.join(stem_dir, new_name)
        os.rename(old_path, new_path)
        stem_files.append(os.path.abspath(new_path))

    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return jsonify({"stems": stem_files, "bpm": detected_bpm})
    else:
        zip_path = os.path.join(OUTPUT_FOLDER, uid + "_stems.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for stem_path in stem_files:
                zf.write(stem_path, os.path.basename(stem_path))
        return send_file(zip_path, as_attachment=True, download_name="stems.zip")


@app.route("/instrumental", methods=["POST"])
def instrumental():
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
    detected_bpm = float(np.round(tempo))

    print(f"Detected BPM: {detected_bpm}\n")

    _, midi_data, _ = predict(input_path, ICASSP_2022_MODEL_PATH)

    tempo_in_microseconds = 60000000 / detected_bpm
    midi_fixed = pretty_midi.PrettyMIDI(resolution=480, initial_tempo=detected_bpm)
    for instrument in midi_data.instruments:
        midi_fixed.instruments.append(instrument)

    midi_path = os.path.join(output_dir, f"output_{int(detected_bpm)}bpm.mid")
    midi_fixed.write(midi_path)

    return jsonify({"midi": os.path.abspath(midi_path), "bpm": detected_bpm})

if __name__ == "__main__":
    app.run(debug=True, port=5000)