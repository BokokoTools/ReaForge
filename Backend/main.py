import uuid
import subprocess
from flask_cors import CORS
import zipfile
from flask import Flask, request, jsonify, send_file
import os
import sys

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

    zip_path = os.path.join(OUTPUT_FOLDER, uid + "_stems.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for stem_file in os.listdir(stem_dir):
            zf.write(os.path.join(stem_dir, stem_file), stem_file)

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)