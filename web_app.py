import os
import sys
import time
import json
import csv
import io
import threading
import cv2
import numpy as np
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, Response, jsonify, request, send_file

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YOLOV5_PATH = os.path.join(CURRENT_DIR, "yolov5_repo")
if YOLOV5_PATH not in sys.path:
    sys.path.insert(0, YOLOV5_PATH)

from tvdr.core import PipelineConfig, Pipeline
from tvdr.utils.path import create_folder

app = Flask(
    __name__,
    template_folder=os.path.join(CURRENT_DIR, "web_ui", "templates"),
    static_folder=os.path.join(CURRENT_DIR, "web_ui", "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB max upload

UPLOADS_DIR = os.path.join(CURRENT_DIR, "uploads")
SESSIONS_DIR = os.path.join(UPLOADS_DIR, "sessions")
SNAPSHOTS_DIR = os.path.join(UPLOADS_DIR, "snapshots")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


class VideoEngine:
    """Thread-safe multi-model video detection & forensic streaming manager."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pipeline_cfg = PipelineConfig()
        self.pipeline = Pipeline(self.pipeline_cfg)

        self.vid = None
        self.video_path = self.pipeline_cfg.video_path
        self.frame_total = 0
        self.current_frame_idx = 0
        self.fps = 30.0

        self.is_playing = False
        self.current_annotated_frame = None
        self.current_raw_frame = None
        self.current_fps = 0.0

        self.recorded_events = []
        self.seen_violations = set()
        self.counts = {
            "red_light": 0,
            "no_helmet": 0,
            "triple_riding": 0,
            "wrong_way": 0,
            "total_vehicles": 0,
        }

        # Multi-session upload history for the Stats & Evidence Vault
        self.sessions = []
        self.current_session = None

        self.markup = {
            "stop_lines": [],
            "signal_roi": {
                "id": "signal_roi_1",
                "name": "Traffic Signal ROI",
                "points": [],
                "visible": True,
                "locked": False,
                "color": "#10B981",
            },
            "detection_area": {
                "id": "detection_area_1",
                "name": "Detection Zone",
                "points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
                "visible": True,
                "locked": False,
                "color": "#10B981",
            },
            "direction_arrow": {
                "id": "direction_1",
                "name": "Allowed Traffic Flow",
                "start": [],
                "end": [],
                "visible": True,
                "locked": False,
                "color": "#A855F7",
            },
        }

        # Clear pipeline configs - no markup until user draws
        self.pipeline_cfg.rrl_config.stop_line = []
        self.pipeline.rrl.config.stop_line = []
        self.pipeline.annotator.rrl_config.stop_line = []
        self.pipeline_cfg.rrl_config.traffic_light_area = []
        self.pipeline.rrl.config.traffic_light_area = []
        self.pipeline.annotator.rrl_config.traffic_light_area = []

        # Full-frame detection zone by default
        self.pipeline_cfg.vd_config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        self.pipeline.vd.config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        self.pipeline.annotator.vd_config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        self.pipeline_cfg.vd_config.sort_min_hits = 1
        self.pipeline.vd.config.sort_min_hits = 1
        self.pipeline.ww.is_active = False

        # Do NOT auto-play or auto-load any video on startup.
        # User explicitly requested app to open cleanly without playing random video.
        self.video_path = None
        self.vid = None
        self.is_playing = False
        self.current_raw_frame = None
        self.current_annotated_frame = None

        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def _start_new_session(self, path):
        video_name = os.path.basename(path)
        session_id = f"session_{len(self.sessions) + 1}_{int(time.time())}"

        # Create per-upload snapshot folder
        safe_name = video_name.rsplit(".", 1)[0] if "." in video_name else video_name
        safe_name = safe_name.replace(" ", "_")[:60]
        snapshot_folder = f"{safe_name}_{session_id}"
        session_snapshot_dir = os.path.join(UPLOADS_DIR, "sessions", snapshot_folder)
        os.makedirs(session_snapshot_dir, exist_ok=True)

        session_record = {
            "id": session_id,
            "video_name": video_name,
            "video_path": path,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": "00:00",
            "total_frames": self.frame_total,
            "fps": round(self.fps, 1),
            "counts": self.counts.copy(),
            "events": [],
            "snapshot_folder": snapshot_folder,
            "snapshot_dir": session_snapshot_dir,
        }
        self.current_session = session_record
        self.sessions.append(session_record)

    def _load_video(self, path):
        with self.lock:
            if not path or not os.path.exists(path):
                candidates = [
                    os.path.join(UPLOADS_DIR, "real_traffic_cctv.mp4"),
                    "/Users/gellaavinash/Downloads/YTDown.com_YouTube_Media__5nGL47gNzo_Indian-Traffic-CCTV-Red-Light-Jump-Vehicle-Detection-Testing-QA-POV_004_720p.mp4",
                    "result/YTDown.com_YouTube_Media__5nGL47gNzo_Indian-Traffic-CCTV-Red-Light-Jump-Vehicle-Detection-Testing-QA-POV_004_720p_2.mp4",
                    "sample_video.mp4",
                ]
                for c in candidates:
                    if os.path.exists(c):
                        path = c
                        break

            if not path or not os.path.exists(path):
                return False

            self.video_path = path
            self.pipeline_cfg.video_path = path

            if self.vid is not None:
                self.vid.release()

            self.vid = cv2.VideoCapture(path)
            if not self.vid.isOpened():
                return False

            self.frame_total = int(self.vid.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.vid.get(cv2.CAP_PROP_FPS) or 30.0
            self.current_frame_idx = 0
            self.is_playing = False  # Start paused so marking menu can pop up

            # Reset counts for this video session
            self.recorded_events = []
            self.seen_violations = set()
            self.counts = {
                "red_light": 0,
                "no_helmet": 0,
                "triple_riding": 0,
                "wrong_way": 0,
                "total_vehicles": 0,
            }
            if hasattr(self.pipeline, "vd"):
                self.pipeline.vd.id_tracker = {}
                self.pipeline.vd.persisted_vehicles = set()
            if hasattr(self.pipeline, "rrl"):
                self.pipeline.rrl.id_tracker = {}
                self.pipeline.rrl.persisted_violations = set()
            if hasattr(self.pipeline, "hv"):
                self.pipeline.hv.id_tracker = {}
                self.pipeline.hv.persisted_helmet_violations = set()
                self.pipeline.hv.persisted_triple_riding = set()
                self.pipeline.hv.rider_counts = {}

            # Reset markup so old markers/spots from previous video don't bleed in
            self.markup = {
                "stop_lines": [],
                "signal_roi": {"id": "signal_roi_1", "name": "Traffic Signal ROI", "points": [], "visible": True, "locked": False, "color": "#F59E0B"},
                "detection_area": {"id": "detection_area_1", "name": "Detection Zone", "points": [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0]], "visible": True, "locked": False, "color": "#10B981"},
                "direction_arrow": {"id": "direction_1", "name": "Allowed Traffic Flow", "start": [], "end": [], "visible": True, "locked": False, "color": "#A855F7"},
            }
            # Clear pipeline configs
            self.pipeline_cfg.rrl_config.stop_line = []
            self.pipeline.rrl.config.stop_line = []
            self.pipeline_cfg.rrl_config.traffic_light_area = []
            self.pipeline.rrl.config.traffic_light_area = []

            self._start_new_session(path)

            # Process first frame for preview
            ret, frame = self.vid.read()
            if ret and frame is not None:
                self.current_raw_frame = frame
                self.current_annotated_frame = frame.copy()
                # Rewind back to frame 0 so playback begins cleanly
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_frame_idx = 0

            tot_sec = self.frame_total / max(1.0, self.fps)
            if self.current_session:
                self.current_session["duration"] = f"{int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}"
                self.current_session["total_frames"] = self.frame_total

            return True

    def _process_frame_events(self, frame, frame_idx, timestamp):
        for ev in getattr(self.pipeline, "latest_events", []):
            vkey = (ev["vehicle_id"], ev["type"])
            if vkey not in self.seen_violations:
                self.seen_violations.add(vkey)
                ev_id = len(self.recorded_events) + 1
                ev["id"] = ev_id
                ev["video_name"] = os.path.basename(self.video_path) if self.video_path else "stream"
                ev["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Save persistent snapshot to per-session folder
                snap_filename = f"snapshot_{ev_id}_{int(time.time())}.jpg"
                session_dir = SNAPSHOTS_DIR
                if self.current_session and "snapshot_dir" in self.current_session:
                    session_dir = self.current_session["snapshot_dir"]
                snap_path = os.path.join(session_dir, snap_filename)
                try:
                    cv2.imwrite(snap_path, frame)
                except Exception:
                    pass
                ev["snapshot_url"] = f"/api/snapshot/{ev_id}"
                ev["snapshot_file"] = snap_path

                self.recorded_events.append(ev)
                if self.current_session:
                    self.current_session["events"].append(ev)

                vtype = ev["type"]
                if "Red" in vtype:
                    self.counts["red_light"] += 1
                elif "Helmet" in vtype:
                    self.counts["no_helmet"] += 1
                elif "Triple" in vtype:
                    self.counts["triple_riding"] += 1
                elif "Wrong" in vtype:
                    self.counts["wrong_way"] += 1

        vd_cnt = len(getattr(self.pipeline, "latest_vd_result", []))
        self.counts["total_vehicles"] = max(self.counts["total_vehicles"], vd_cnt)
        if self.current_session:
            self.current_session["counts"] = self.counts.copy()

    def _worker_loop(self):
        fail_count = 0
        while True:
            if not self.is_playing:
                time.sleep(0.04)
                continue

            t0 = time.time()
            with self.lock:
                if self.vid is None or not self.vid.isOpened():
                    self.is_playing = False
                    time.sleep(0.05)
                    continue

                ret, frame = self.vid.read()
                if not ret or frame is None:
                    # Video reached end of stream! Stop playback cleanly - do NOT auto-loop
                    self.is_playing = False
                    self.current_frame_idx = self.frame_total
                    time.sleep(0.08)
                    continue

                self.current_frame_idx = int(self.vid.get(cv2.CAP_PROP_POS_FRAMES))
                sec = self.current_frame_idx / max(1.0, self.fps)
                ts_str = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"

                self.current_raw_frame = frame
                try:
                    annotated = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=ts_str)
                    self.current_annotated_frame = annotated
                except Exception as exc:
                    logging.exception(f"Pipeline update error at frame {self.current_frame_idx}: {exc}")
                    self.current_annotated_frame = frame.copy()

                # Record violation events with high-res evidentiary snapshot
                self._process_frame_events(frame, self.current_frame_idx, ts_str)

            dt = time.time() - t0
            self.current_fps = 1.0 / max(0.001, dt)
            target_dt = 1.0 / self.fps
            sleep_time = max(0.008, target_dt - dt)
            time.sleep(sleep_time)

    def play(self):
        with self.lock:
            self.is_playing = True

    def pause(self):
        with self.lock:
            self.is_playing = False

    def toggle_play(self):
        with self.lock:
            self.is_playing = not self.is_playing
            return self.is_playing

    def seek(self, frame_num):
        with self.lock:
            if self.vid and self.vid.isOpened():
                frame_num = max(0, min(self.frame_total - 1, frame_num))
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                self.current_frame_idx = frame_num
                if frame_num == 0:
                    self.seen_violations.clear()
                    self.counts = {"red_light": 0, "no_helmet": 0, "triple_riding": 0, "wrong_way": 0, "total_vehicles": 0}
                    if hasattr(self.pipeline, "vd"):
                        self.pipeline.vd.id_tracker = {}
                        self.pipeline.vd.persisted_vehicles = set()
                    if hasattr(self.pipeline, "rrl"):
                        self.pipeline.rrl.id_tracker = {}
                        self.pipeline.rrl.persisted_violations = set()
                    if hasattr(self.pipeline, "hv"):
                        self.pipeline.hv.id_tracker = {}
                        self.pipeline.hv.persisted_helmet_violations = set()
                        self.pipeline.hv.persisted_triple_riding = set()
                        self.pipeline.hv.rider_counts = {}
                ret, frame = self.vid.read()
                if ret and frame is not None:
                    self.current_raw_frame = frame
                    sec = self.current_frame_idx / max(1.0, self.fps)
                    ts_str = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"
                    self.current_annotated_frame = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=ts_str)
                    self._process_frame_events(frame, self.current_frame_idx, ts_str)

    def step(self, delta):
        with self.lock:
            if self.vid and self.vid.isOpened():
                target = self.current_frame_idx + delta
                self.seek(target)

    def remove_video(self):
        with self.lock:
            self.is_playing = False
            if self.vid is not None:
                try:
                    self.vid.release()
                except Exception:
                    pass
                self.vid = None
            self.video_path = None
            self.pipeline_cfg.video_path = None
            self.current_frame_idx = 0
            self.frame_total = 0
            self.current_raw_frame = None
            self.current_annotated_frame = None
            self.recorded_events.clear()
            self.seen_violations.clear()
            self.current_session = None
            self.counts = {"red_light": 0, "no_helmet": 0, "triple_riding": 0, "wrong_way": 0, "total_vehicles": 0}
            if hasattr(self.pipeline, "vd"):
                self.pipeline.vd.id_tracker = {}
                self.pipeline.vd.persisted_vehicles = set()
            if hasattr(self.pipeline, "rrl"):
                self.pipeline.rrl.id_tracker = {}
                self.pipeline.rrl.persisted_violations = set()
            if hasattr(self.pipeline, "hvd"):
                self.pipeline.hvd.id_tracker = {}
                self.pipeline.hvd.persisted_helmet_violations = set()
                self.pipeline.hvd.persisted_triple_riding = set()
            return True

    def update_markup(self, new_markup):
        with self.lock:
            self.markup.update(new_markup)
            if "stop_lines" in self.markup:
                pts = self.markup["stop_lines"][0].get("points", []) if len(self.markup["stop_lines"]) > 0 else []
                self.pipeline_cfg.rrl_config.stop_line = pts
                self.pipeline.rrl.config.stop_line = pts
                self.pipeline.annotator.rrl_config.stop_line = pts

            if "signal_roi" in self.markup:
                pts = self.markup["signal_roi"].get("points", [])
                if len(pts) >= 3:
                    self.pipeline_cfg.rrl_config.traffic_light_area = pts
                    self.pipeline.rrl.config.traffic_light_area = pts
                    self.pipeline.annotator.rrl_config.traffic_light_area = pts
                else:
                    self.pipeline_cfg.rrl_config.traffic_light_area = []
                    self.pipeline.rrl.config.traffic_light_area = []
                    self.pipeline.annotator.rrl_config.traffic_light_area = []

            if "detection_area" in self.markup:
                pts = self.markup["detection_area"].get("points", [])
                if len(pts) >= 3:
                    self.pipeline_cfg.vd_config.detection_area = pts
                    self.pipeline.vd.config.detection_area = pts
                    self.pipeline.annotator.vd_config.detection_area = pts
                else:
                    self.pipeline_cfg.vd_config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
                    self.pipeline.vd.config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
                    self.pipeline.annotator.vd_config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

            if "direction_arrow" in self.markup:
                arrow = self.markup["direction_arrow"]
                st = arrow.get("start", [])
                en = arrow.get("end", [])
                if len(st) == 2 and len(en) == 2:
                    dx = en[0] - st[0]
                    dy = en[1] - st[1]
                    if abs(dx) > 0.02 or abs(dy) > 0.02:
                        phi = np.arctan2(-dy, dx)
                        deg = int(np.degrees(phi))
                        if deg < 0:
                            deg += 360
                        opp = (deg + 180) % 360
                        self.pipeline.ww.config.direction_violation = opp
                        self.pipeline.ww.is_active = True
                    else:
                        self.pipeline.ww.is_active = False
                else:
                    self.pipeline.ww.is_active = False

    def get_status(self):
        with self.lock:
            sec = self.current_frame_idx / max(1.0, self.fps)
            tot_sec = self.frame_total / max(1.0, self.fps)
            sig_state = getattr(self.pipeline.rrl, "state", "green")
            vd_cnt = len(getattr(self.pipeline, "latest_vd_result", []))

            # Threat index based on active violations
            active_events = getattr(self.pipeline, "latest_events", [])
            has_crit = any("Red" in e["type"] or "Helmet" in e["type"] or "Triple" in e["type"] for e in active_events)
            threat_level = "CRITICAL" if has_crit else ("CAUTION" if sig_state == "yellow" else "SAFE")
            risk_score = 98.5 if has_crit else (45.0 if sig_state == "yellow" else 98.2)

            return {
                "is_playing": self.is_playing,
                "current_frame": self.current_frame_idx,
                "total_frames": self.frame_total,
                "fps": round(self.current_fps, 1),
                "target_fps": round(self.fps, 1),
                "timestamp": f"{int(sec // 60):02d}:{int(sec % 60):02d}",
                "total_time": f"{int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}",
                "signal_state": sig_state,
                "video_path": os.path.basename(self.video_path or ""),
                "counts": self.counts,
                "current_vehicles_in_frame": vd_cnt,
                "threat_level": threat_level,
                "risk_score": risk_score,
                "latest_event": self.recorded_events[-1] if self.recorded_events else None,
                "session": {
                    "id": self.current_session["id"] if self.current_session else None,
                    "folder": self.current_session["snapshot_folder"] if self.current_session else None,
                    "dir": self.current_session["snapshot_dir"] if self.current_session else None,
                    "video_name": self.current_session["video_name"] if self.current_session else None,
                    "snapshot_count": len(self.current_session["events"]) if self.current_session else 0,
                } if (self.current_session and self.video_path) else None,
                "ready_status": getattr(self.pipeline, "vd_ready_status", True) and getattr(self.pipeline, "hv_ready_status", True),
                "models": {
                    "vehicle": {"name": "Vehicle Detector", "status": "Ready", "weights": "best.pt"},
                    "helmet": {"name": "Helmet Violation", "status": "Ready", "weights": "best.pt"},
                    "triple": {"name": "Triple Riding", "status": "Ready", "threshold": 3},
                    "signal": {"name": "Signal & StopLine", "status": "Ready", "state": sig_state},
                },
            }


engine = VideoEngine()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    def generate():
        placeholder_bytes = None
        while True:
            frame_to_send = None
            with engine.lock:
                if engine.current_annotated_frame is not None:
                    frame_to_send = engine.current_annotated_frame.copy()

            if frame_to_send is not None:
                ret, jpeg = cv2.imencode(".jpg", frame_to_send, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
                    )
            else:
                if placeholder_bytes is None:
                    h, w = 720, 1280
                    blank = np.zeros((h, w, 3), dtype=np.uint8)
                    blank[:] = (20, 14, 11)  # Obsidian dark background #0B0E14
                    cv2.putText(blank, "TRAFFIC VIOLATION DETECTION", (w // 2 - 320, h // 2 - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (248, 250, 252), 2, cv2.LINE_AA)
                    cv2.putText(blank, "Upload a video file to begin automated surveillance analysis",
                                (w // 2 - 360, h // 2 + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (130, 145, 165), 1, cv2.LINE_AA)
                    ret_p, jpeg_p = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret_p:
                        placeholder_bytes = jpeg_p.tobytes()
                if placeholder_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + placeholder_bytes + b"\r\n"
                    )
                time.sleep(0.5)
                continue
            time.sleep(0.033)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def api_status():
    return jsonify(engine.get_status())


@app.route("/api/playback/play", methods=["POST"])
def api_play():
    engine.play()
    return jsonify({"success": True, "playing": True})


@app.route("/api/playback/pause", methods=["POST"])
def api_pause():
    engine.pause()
    return jsonify({"success": True, "playing": False})


@app.route("/api/playback/toggle", methods=["POST"])
def api_toggle():
    is_playing = engine.toggle_play()
    return jsonify({"success": True, "playing": is_playing})


@app.route("/api/playback/seek", methods=["POST"])
def api_seek():
    data = request.get_json() or {}
    frame = data.get("frame", 0)
    engine.seek(int(frame))
    return jsonify({"success": True, "frame": engine.current_frame_idx})


@app.route("/api/playback/step", methods=["POST"])
def api_step():
    data = request.get_json() or {}
    delta = data.get("delta", 1)
    engine.step(int(delta))
    return jsonify({"success": True, "frame": engine.current_frame_idx})


@app.route("/api/videos")
def api_videos():
    videos = []
    seen = set()

    # Search uploads/, root, result/, and user's Downloads
    search_dirs = [
        UPLOADS_DIR,
        ".",
        "result",
        "/Users/gellaavinash/Downloads",
    ]

    for folder in search_dirs:
        if os.path.exists(folder):
            try:
                for f in os.listdir(folder):
                    if f.endswith((".mp4", ".avi", ".mov", ".mkv")):
                        full = os.path.join(folder, f)
                        if os.path.isfile(full) and full not in seen:
                            seen.add(full)
                            videos.append({
                                "name": f,
                                "path": full,
                                "size": os.path.getsize(full),
                                "is_real_yt": "YTDown" in f or "real_traffic" in f,
                            })
            except Exception:
                pass

    # Sort real YouTube traffic videos first
    videos.sort(key=lambda x: (not x.get("is_real_yt", False), x["name"]))
    return jsonify({"videos": videos, "current": engine.video_path})


@app.route("/api/videos/select", methods=["POST"])
def api_select_video():
    data = request.get_json() or {}
    path = data.get("path")
    engine.pause()
    success = engine._load_video(path)
    return jsonify({"success": success, "current": engine.video_path})


@app.route("/api/videos/upload", methods=["POST"])
def api_upload_video():
    try:
        engine.pause()  # Stop processing old video immediately

        if "video" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded in form"}), 400
        file = request.files["video"]
        if not file or file.filename == "":
            return jsonify({"success": False, "error": "Empty filename selected"}), 400

        orig_filename = file.filename
        name_part, ext_part = os.path.splitext(orig_filename)
        ext = ext_part.lower() if ext_part else ".mp4"
        if ext not in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]:
            ext = ".mp4"

        clean_base = secure_filename(name_part)
        if not clean_base:
            clean_base = f"upload_{int(time.time())}"

        saved_name = f"{clean_base}_{int(time.time())}{ext}"
        dest_path = os.path.join(UPLOADS_DIR, saved_name)

        # Save uploaded file
        file.save(dest_path)

        if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
            return jsonify({"success": False, "error": "Uploaded file is empty"}), 400

        # Load into engine with fresh session and reset markup
        success = engine._load_video(dest_path)
        if not success:
            return jsonify({"success": False, "error": f"Failed to open video codec for: {orig_filename}"}), 400

        # Leave paused so user can set markup in modal
        engine.pause()

        return jsonify({
            "success": True,
            "path": dest_path,
            "name": orig_filename,
            "size": os.path.getsize(dest_path),
            "session_id": engine.current_session["id"] if engine.current_session else None,
            "snapshot_folder": engine.current_session["snapshot_folder"] if engine.current_session else None,
            "total_frames": engine.frame_total,
            "fps": round(engine.fps, 1),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/videos/remove", methods=["POST"])
def api_videos_remove():
    try:
        engine.remove_video()
        return jsonify({"success": True, "message": "Video removed successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/markup", methods=["GET", "POST"])
def api_markup():
    if request.method == "POST":
        data = request.get_json() or {}
        engine.update_markup(data)
        return jsonify({"success": True, "markup": engine.markup})
    return jsonify({"markup": engine.markup})


@app.route("/api/models/recheck", methods=["POST"])
def api_recheck():
    status = engine.pipeline.ready_check()
    return jsonify({"success": True, "ready": status})


@app.route("/api/violations")
def api_violations():
    return jsonify({"events": engine.recorded_events, "counts": engine.counts})


@app.route("/api/stats/sessions")
def api_stats_sessions():
    """Returns list-format statistics for every upload session for the Stats Page."""
    sessions_out = []
    for s in engine.sessions:
        s_copy = s.copy()
        folder_dir = s.get("snapshot_dir")
        folder_name = s.get("snapshot_folder")
        disk_images = []
        if folder_dir and os.path.exists(folder_dir):
            try:
                for fn in sorted(os.listdir(folder_dir)):
                    if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                        disk_images.append({
                            "filename": fn,
                            "url": f"/api/snapshot_file/{folder_name}/{fn}",
                            "path": os.path.join(folder_dir, fn)
                        })
            except Exception:
                pass
        s_copy["disk_images"] = disk_images
        s_copy["total_snapshots"] = max(len(s.get("events", [])), len(disk_images))
        sessions_out.append(s_copy)

    return jsonify({
        "sessions": sessions_out,
        "current_session_id": engine.current_session["id"] if engine.current_session else None,
        "total_violations_all": sum(len(s.get("events", [])) for s in engine.sessions),
        "total_uploads": len(engine.sessions),
    })


@app.route("/api/snapshot_file/<folder>/<filename>")
def api_snapshot_file(folder, filename):
    safe_folder = secure_filename(folder)
    safe_filename = secure_filename(filename)
    path = os.path.join(UPLOADS_DIR, "sessions", safe_folder, safe_filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return jsonify({"error": "Snapshot file not found"}), 404


@app.route("/api/stats/clear", methods=["POST"])
def api_stats_clear():
    with engine.lock:
        engine.recorded_events = []
        engine.seen_violations = set()
        engine.counts = {
            "red_light": 0,
            "no_helmet": 0,
            "triple_riding": 0,
            "wrong_way": 0,
            "total_vehicles": 0,
        }
        if engine.current_session:
            engine.current_session["events"] = []
            engine.current_session["counts"] = engine.counts.copy()
    return jsonify({"success": True})


@app.route("/api/violations/export")
def api_export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Frame", "Vehicle ID", "Vehicle Type", "Violation Type", "Details", "Severity", "Video Name", "Recorded At"])
    for ev in engine.recorded_events:
        writer.writerow([
            ev.get("id", ""),
            ev.get("timestamp", ""),
            ev.get("frame", ""),
            ev.get("vehicle_id", ""),
            ev.get("vehicle_type", ""),
            ev.get("type", ""),
            ev.get("details", ""),
            ev.get("severity", ""),
            ev.get("video_name", ""),
            ev.get("created_at", ""),
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=violations_incident_report.csv"},
    )


@app.route("/api/snapshot/<int:event_id>")
def api_snapshot(event_id):
    # 1. Search in current recorded events
    for ev in engine.recorded_events:
        if ev.get("id") == event_id and "snapshot_file" in ev and os.path.exists(ev["snapshot_file"]):
            return send_file(ev["snapshot_file"], mimetype="image/jpeg")

    # 2. Search across all session events
    for sess in engine.sessions:
        for ev in sess.get("events", []):
            if ev.get("id") == event_id and "snapshot_file" in ev and os.path.exists(ev["snapshot_file"]):
                return send_file(ev["snapshot_file"], mimetype="image/jpeg")

    # 3. Fallback to current raw frame
    if engine.current_raw_frame is not None:
        ret, jpeg = cv2.imencode(".jpg", engine.current_raw_frame)
        if ret:
            return Response(jpeg.tobytes(), mimetype="image/jpeg")

    # 4. Return clean placeholder
    black = np.zeros((180, 320, 3), dtype=np.uint8)
    cv2.putText(black, "Evidentiary Snapshot", (40, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    ret, jpeg = cv2.imencode(".jpg", black)
    return Response(jpeg.tobytes(), mimetype="image/jpeg")


def main():
    port = int(os.environ.get("PORT", 5001))
    print(f"\n==================================================================")
    print(f"🚦 Sentinel Vanguard / TVDR Command Center Web Server")
    print(f"🌐 Access the application at: http://localhost:{port}")
    print(f"==================================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
