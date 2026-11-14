import cv2
import os

from pathlib import Path
from ..vehicle_detection.main_vehicle_detection import VehicleDetection
from ..running_red_light.main_running_redlight import RunningRedLight
from ..helmet_violation.main_helmet_violation import HelmetViolation
from ..wrongway_detection.main_wrongway_detection import WrongWayDetection
from .configuration_pipeline import PipelineConfig
from ..plate_detection import PlateDetector
from ...utils.annotator import Annotator


class Pipeline:
    def __init__(self, config: PipelineConfig = None):
        self.config = config if config is not None else PipelineConfig()
        self.vd = VehicleDetection(self.config.vd_config)
        self.rrl = RunningRedLight(self.config.rrl_config)
        self.hv = HelmetViolation(self.config.hv_config)
        self.ww = WrongWayDetection(self.config.ww_config)
        self.plate_detector = PlateDetector()
        self.latest_plates = {}
        self.annotator = Annotator(self.config)

    
    def video_recorder_init(self, video_path):
        if os.path.isdir("result")== False:
            os.mkdir("result")

        vid = cv2.VideoCapture(video_path)
        _, frame = vid.read()
        fps = vid.get(cv2.CAP_PROP_FPS)
        height, width, _ = frame.shape
        fourcc = cv2.VideoWriter_fourcc("m", "p", "4", "v")

        filename = os.path.basename(video_path).rsplit('.', 1)[0]
        index = 0
        
        while(1):
            current_output_path = os.path.join("result", f"{filename}_{index}.mp4")
            if os.path.exists(current_output_path) == False:
                break
            index +=1

        self.video_output = current_output_path
        self.video_writer = cv2.VideoWriter(
            self.video_output,
            fourcc=fourcc,
            fps=fps,
            frameSize=(width, height),
        )
    
    def video_recorder_update(self, frame):
        self.video_writer.write(frame)

    def video_recorder_close(self):
        self.video_writer.release()
        return self.video_output
    
    def reload_config(self):
        self.vd.config = self.config.vd_config
        self.rrl.config = self.config.rrl_config
        self.hv.config = self.config.hv_config
        self.ww.config = self.config.ww_config
        self.annotator.config = self.config
        self.annotator.vd_config = self.config.vd_config
        self.annotator.rrl_config = self.config.rrl_config


    def update(self, img, frame_idx=0, timestamp="00:00.0"):
        if img is None or not hasattr(img, "shape") or img.size == 0:
            return img

        vd_result = self.vd.update(img)
        rrl_result = self.rrl.update(img, vd_result) if getattr(self.config, "detect_rrl", True) else []
        hv_result = self.hv.update(img, vd_result) if getattr(self.config, "detect_hvd", True) else []
        tr_result = getattr(self.hv, "triple_riding_violations", []) if getattr(self.config, "detect_triple_riding", True) else []
        ww_active = getattr(self.config, "detect_wr", True) and getattr(self.ww, "is_active", False)
        direction, ww_result = self.ww.update(vd_result) if ww_active else ({}, [])

        # Store latest violations and state
        self.latest_vd_result = vd_result
        self.latest_rrl_result = rrl_result
        self.latest_hv_result = hv_result
        self.latest_tr_result = tr_result
        self.latest_ww_result = ww_result
        self.latest_signal_state = self.rrl.state

        # Collect event details for new violations
        new_events = []
        for obj in vd_result:
            vid = obj[6]
            cls_id = int(obj[5])
            cls_name = self.config.vd_config.classes_names[cls_id] if cls_id < len(self.config.vd_config.classes_names) else "Vehicle"

            is_violating = (vid in rrl_result) or (vid in tr_result) or (vid in hv_result) or (vid in ww_result)
            plate_info = None
            if is_violating:
                plate_info = self.plate_detector.detect_plate(
                    img, obj[0:4], vehicle_id=int(vid), video_name=getattr(self.config, "video_path", "")
                )
                self.latest_plates[vid] = plate_info

            plate_number = plate_info["text"] if plate_info else None
            plate_bbox = plate_info["bbox"] if plate_info else None
            plate_confidence = plate_info.get("confidence", 0.0) if plate_info else None
            plate_visible = plate_info.get("is_visible", False) if plate_info else None

            # Check Red light
            if vid in rrl_result:
                new_events.append({
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "vehicle_id": int(vid),
                    "vehicle_type": cls_name,
                    "type": "Running Red Light",
                    "details": f"{cls_name} crossed stop line during RED signal",
                    "severity": "CRITICAL",
                    "plate_number": plate_number,
                    "plate_bbox": plate_bbox,
                    "plate_confidence": plate_confidence,
                    "plate_visible": plate_visible,
                })
            # Check Triple Riding
            if vid in tr_result:
                cnt = getattr(self.hv, "rider_counts", {}).get(vid, 3)
                new_events.append({
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "vehicle_id": int(vid),
                    "vehicle_type": cls_name,
                    "type": "Triple Riding",
                    "details": f"{cnt} riders detected on {cls_name} (Max allowed: 2)",
                    "severity": "HIGH",
                    "plate_number": plate_number,
                    "plate_bbox": plate_bbox,
                    "plate_confidence": plate_confidence,
                    "plate_visible": plate_visible,
                })
            # Check Helmet Violation
            if vid in hv_result:
                new_events.append({
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "vehicle_id": int(vid),
                    "vehicle_type": cls_name,
                    "type": "No Helmet Violation",
                    "details": f"Rider without helmet on {cls_name}",
                    "severity": "HIGH",
                    "plate_number": plate_number,
                    "plate_bbox": plate_bbox,
                    "plate_confidence": plate_confidence,
                    "plate_visible": plate_visible,
                })
            # Check Wrong Way
            if vid in ww_result:
                new_events.append({
                    "frame": frame_idx,
                    "timestamp": timestamp,
                    "vehicle_id": int(vid),
                    "vehicle_type": cls_name,
                    "type": "Wrong Way",
                    "details": f"{cls_name} moving opposite to allowed traffic flow",
                    "severity": "MEDIUM",
                    "plate_number": plate_number,
                    "plate_bbox": plate_bbox,
                    "plate_confidence": plate_confidence,
                    "plate_visible": plate_visible,
                })

        self.latest_events = new_events

        # Draw annotations
        img_new = self.annotator.vehicle_detection(img, vd_result)
        img_new = self.annotator.running_red_light(img_new, vd_result, rrl_result, self.rrl.state)
        img_new = self.annotator.helmet_violation(img_new, vd_result, hv_result, plate_dict=self.latest_plates)
        img_new = self.annotator.triple_riding(img_new, vd_result, tr_result, rider_counts=getattr(self.hv, "rider_counts", {}), plate_dict=self.latest_plates)
        img_new = self.annotator.wrongway_detection(img_new, vd_result, direction, ww_result)
        
        return img_new

    def ready_check(self):
        # Ready Check Vehicle Detection and Tracker
        self.vd_ready_status = self.vd.ready_check()
        self.rrl_ready_status = self.rrl.ready_check()
        self.hv_ready_status = self.hv.ready_check()
        self.ww_ready_status = self.ww.ready_check()

        for key in ["vd","rrl", "hv", "ww"]:
            status  = getattr(self, f"{key}_ready_status")
            if status == False:
                return False
        return True
