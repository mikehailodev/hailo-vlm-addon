"""
Hailo-10H VLM Chat — Flask Web Server

Provides:
  /              — Web UI (served via HA ingress)
  /video_feed    — MJPEG camera stream
  /api/capture   — Freeze the current frame
  /api/ask       — Send a prompt, get a VLM response
  /api/resume    — Resume live video
  /api/status    — Health / device info
"""

import os
import json
import time
import base64
import logging
import threading
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, request, jsonify, send_from_directory

from vlm_backend import VLMBackend, HAILO_AVAILABLE

# ── Configuration (from environment, set by run.sh) ─────────────────────────
CAMERA_DEVICE = os.environ.get("CAMERA_DEVICE", "/dev/video0")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "200"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.1"))
DEFAULT_PROMPT = os.environ.get("DEFAULT_PROMPT", "Describe the image")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful assistant that analyzes images and answers questions about them.",
)
PORT = 8099

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("hailo_vlm")

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")

# ── Globals ──────────────────────────────────────────────────────────────────
camera_lock = threading.Lock()
state_lock = threading.Lock()
cap = None               # cv2.VideoCapture
backend = None            # VLMBackend
current_frame = None      # Latest BGR frame from camera
frozen_frame = None       # Captured frame (BGR) for VLM
is_frozen = False         # Whether we're in freeze/capture mode
camera_ok = False


# ── Camera helpers ───────────────────────────────────────────────────────────
def open_camera():
    global cap, camera_ok
    try:
        # Try device string first, then numeric index
        dev = CAMERA_DEVICE
        if dev.startswith("/dev/video"):
            idx = int(dev.replace("/dev/video", ""))
        else:
            idx = int(dev) if dev.isdigit() else 0
        cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)
        camera_ok = cap.isOpened()
        if camera_ok:
            logger.info(f"Camera opened: index {idx}")
        else:
            logger.warning("Camera device could not be opened")
    except Exception as e:
        logger.error(f"Camera error: {e}")
        camera_ok = False


def read_frame():
    """Read a frame from the camera, return BGR numpy array or None."""
    global current_frame
    if not camera_ok or cap is None:
        return None
    with camera_lock:
        ret, frame = cap.read()
    if ret:
        current_frame = frame
        return frame
    return None


def generate_placeholder():
    """Generate a placeholder frame when no camera is available."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "No Camera", (180, 230),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 100), 3)
    cv2.putText(img, f"Looking for {CAMERA_DEVICE}", (120, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
    return img


# ── MJPEG generator ─────────────────────────────────────────────────────────
def mjpeg_stream():
    """Yield MJPEG frames continuously."""
    while True:
        with state_lock:
            frozen = is_frozen
            ff = frozen_frame

        if frozen and ff is not None:
            frame = ff
        else:
            frame = read_frame()
            if frame is None:
                frame = generate_placeholder()

        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(0.066)  # ~15 fps


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/video_feed")
def video_feed():
    return Response(mjpeg_stream(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/capture", methods=["POST"])
def api_capture():
    global frozen_frame, is_frozen
    frame = current_frame
    if frame is None:
        frame = read_frame()
    if frame is None:
        return jsonify({"ok": False, "error": "No frame available"}), 500

    with state_lock:
        frozen_frame = frame.copy()
        is_frozen = True

    # Return base64 JPEG of the captured frame
    _, jpeg = cv2.imencode(".jpg", frozen_frame)
    b64 = base64.b64encode(jpeg.tobytes()).decode("utf-8")
    return jsonify({"ok": True, "image": b64})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip() or DEFAULT_PROMPT

    with state_lock:
        frame = frozen_frame

    if frame is None:
        return jsonify({"ok": False, "error": "No captured frame. Press Capture first."}), 400

    if backend is None:
        return jsonify({"ok": False, "error": "VLM backend not initialised"}), 500

    logger.info(f"VLM prompt: {prompt}")
    result = backend.infer(frame, prompt, timeout=90)
    logger.info(f"VLM response ({result.get('time', '?')}): {result.get('answer', '')[:80]}...")
    return jsonify({"ok": True, "answer": result["answer"], "time": result["time"]})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    global is_frozen, frozen_frame
    with state_lock:
        is_frozen = False
        frozen_frame = None
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    return jsonify({
        "hailo_available": HAILO_AVAILABLE,
        "hailo_device": os.path.exists("/dev/hailo0"),
        "camera_ok": camera_ok,
        "camera_device": CAMERA_DEVICE,
        "frozen": is_frozen,
    })


# ── Main ─────────────────────────────────────────────────────────────────────
def find_hef_path():
    """Look for a VLM HEF model in common locations."""
    search_dirs = [
        Path("/data"),
        Path("/media"),
        Path("/share"),
        Path.home(),
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for hef in d.rglob("*.hef"):
            if "vlm" in hef.name.lower() or "qwen" in hef.name.lower():
                logger.info(f"Found VLM HEF: {hef}")
                return str(hef)
    return None


if __name__ == "__main__":
    open_camera()

    # Initialise VLM backend
    hef_path = find_hef_path()
    if hef_path:
        logger.info(f"Using VLM model: {hef_path}")
    elif HAILO_AVAILABLE:
        logger.warning("No VLM HEF file found — place a .hef model in /media or /share")
    else:
        logger.info("Running in demo mode (hailo_platform not installed)")

    backend = VLMBackend(
        hef_path=hef_path,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system_prompt=SYSTEM_PROMPT,
    )

    logger.info(f"Server starting on 0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
