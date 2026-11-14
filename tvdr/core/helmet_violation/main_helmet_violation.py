import os
import torch
import numpy as np
import torch.nn.functional as F

from .configuration_helmet_violation import HelmetViolationConfig
from tvdr.utils.general import letterbox, non_max_suppression


class HelmetViolation:
    def __init__(self, config: HelmetViolationConfig):
        self.config = config
        self.missing_removal_thres = 150
        self.id_tracker = {}
        self.persisted_helmet_violations = set()
        self.persisted_triple_riding = set()
        self.rider_counts = {}
        self.helmet_violations = []
        self.triple_riding_violations = []
        self.load_model()

    def load_model(self) -> bool:
        if not self.config.model_path or not os.path.exists(self.config.model_path):
            return False
        try:
            try:
                ckpt = torch.load(
                    self.config.model_path,
                    map_location=torch.device(self.config.device),
                    weights_only=False,
                )
            except TypeError:
                ckpt = torch.load(
                    self.config.model_path,
                    map_location=torch.device(self.config.device),
                )
            if isinstance(ckpt, dict) and "model" in ckpt:
                self.model = ckpt["model"].float()
            else:
                self.model = ckpt.float()
            self.model.eval()
            return True
        except Exception as e:
            import logging
            logging.error(f"Error loading helmet violation model: {e}")
            return False

    def update(self, img, preds):
        filter_vehicle = self.motorcycle_and_bicycle_filtering(preds)
        self.tracker_record_update(filter_vehicle)
        list_object_inference = self.get_object_inference(filter_vehicle)
        self.detect_violation(img, list_object_inference)

        # Active violations for vehicles currently present in preds
        active_ids = set([obj[6] for obj in filter_vehicle]) if len(filter_vehicle) > 0 else set()
        self.helmet_violations = [vid for vid in self.persisted_helmet_violations if vid in active_ids]
        self.triple_riding_violations = [vid for vid in self.persisted_triple_riding if vid in active_ids]

        return self.helmet_violations

    def motorcycle_and_bicycle_filtering(self, preds):
        # Get data from vehicle detection and return only 2-wheel vehicles (motorcycle and bicycle)
        if preds is None or len(preds) == 0:
            return np.empty((0, 7))
        result_filter = np.empty((0, preds.shape[1]))
        for obj in preds:
            vehicle_idx = int(obj[5])
            if vehicle_idx in self.config.vehicle_idx:
                result_filter = np.append(
                    result_filter, obj.reshape(1, preds.shape[1]), axis=0
                )
        return result_filter

    def tracker_record_update(self, result_filter):
        list_id = []
        for object in result_filter:
            id = object[6]
            if id not in self.id_tracker.keys():
                self.id_tracker[id] = {
                    "age": 1,
                    "missing": 0,
                    "no_helmet_votes": 0,
                    "with_helmet_votes": 0,
                    "triple_votes": 0,
                }
            else:
                self.id_tracker[id]["age"] += 1
                self.id_tracker[id]["missing"] = 0
            list_id.append(id)

        not_in_list_id = list(set(list(self.id_tracker.keys())) - set(list_id))
        for id in not_in_list_id:
            self.id_tracker[id]["age"] += 1
            self.id_tracker[id]["missing"] += 1

        list_delete_id = []
        for id in self.id_tracker.keys():
            if self.id_tracker[id]["missing"] >= self.missing_removal_thres:
                list_delete_id.append(id)

        for id_delete in list_delete_id:
            del self.id_tracker[id_delete]
            self.persisted_helmet_violations.discard(id_delete)
            self.persisted_triple_riding.discard(id_delete)
            self.rider_counts.pop(id_delete, None)

    def get_object_inference(self, filter_preds):
        if filter_preds is None or len(filter_preds) == 0:
            return np.empty((0, 7))
        object_inference = np.empty((0, filter_preds.shape[1]))
        for object in filter_preds:
            id = object[6]
            if id in self.id_tracker:
                age = self.id_tracker[id]["age"]
                if age >= self.config.min_age and (age % self.config.detect_interval == 0 or age == self.config.min_age):
                    object_inference = np.append(
                        object_inference, object.reshape(1, 7), axis=0
                    )
        return object_inference

    def cropping_img(self, img, bbox):
        # Crop image to get motorcycle/bicycle frame with headroom padding for riders' heads
        h_img, w_img = img.shape[:2]
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        x1 = max(0, int(bbox[0] - 0.08 * bw))
        y1 = max(0, int(bbox[1] - 0.22 * bh))
        x2 = min(w_img, int(bbox[2] + 0.08 * bw))
        y2 = min(h_img, int(bbox[3] + 0.05 * bh))
        # Ensure minimum resolution to avoid false alarms on distant blurry motorcycles
        if (x2 - x1) < 50 or (y2 - y1) < 85:
            return np.zeros((10, 10, 3), dtype=np.uint8)
        return img[y1:y2, x1:x2, :]

    def detect_violation(self, img, list_object):
        for obj in list_object:
            bbox = obj[0:4]
            object_id = obj[6]
            img_crop = self.cropping_img(img, bbox)
            ch, cw = img_crop.shape[:2] if (img_crop is not None and hasattr(img_crop, "shape")) else (0, 0)
            has_no_helmet, is_triple, riders_count, heads = self.predict_riders(img_crop)

            self.rider_counts[object_id] = max(self.rider_counts.get(object_id, 1), riders_count)

            # Initialize tracking stats
            if object_id not in self.id_tracker:
                self.id_tracker[object_id] = {
                    "age": 1,
                    "missing": 0,
                    "total_obs": 0,
                    "no_helmet_votes": 0,
                    "with_helmet_votes": 0,
                    "triple_votes": 0,
                    "max_wh_conf": 0.0,
                    "max_nh_conf": 0.0,
                }
            else:
                self.id_tracker[object_id].setdefault("total_obs", 0)
                self.id_tracker[object_id].setdefault("no_helmet_votes", 0)
                self.id_tracker[object_id].setdefault("with_helmet_votes", 0)
                self.id_tracker[object_id].setdefault("triple_votes", 0)
                self.id_tracker[object_id].setdefault("max_wh_conf", 0.0)
                self.id_tracker[object_id].setdefault("max_nh_conf", 0.0)

            stats = self.id_tracker[object_id]
            wh_confs = [h["conf"] for h in heads if h["cls_id"] == 0]
            nh_confs = [h["conf"] for h in heads if h["cls_id"] == 1]
            if wh_confs:
                stats["max_wh_conf"] = max(stats["max_wh_conf"], max(wh_confs))
            if nh_confs:
                stats["max_nh_conf"] = max(stats["max_nh_conf"], max(nh_confs))

            if riders_count > 0:
                stats["total_obs"] += 1
                if has_no_helmet:
                    stats["no_helmet_votes"] += 1
                elif stats["max_wh_conf"] >= 0.30:
                    stats["with_helmet_votes"] += 1

            if is_triple:
                stats["triple_votes"] += 1
                self.rider_counts[object_id] = max(self.rider_counts.get(object_id, 3), riders_count)

            # Require temporal consistency:
            # Triple Riding:
            # High-confidence close-up motorcycle or repeated multi-frame confirmation
            if self.config.detect_triple_riding:
                if is_triple:
                    if ch >= 280 or stats["triple_votes"] >= 2 or (stats["total_obs"] <= 4 and is_triple):
                        self.persisted_triple_riding.add(object_id)
                elif stats["total_obs"] >= 6 and stats["triple_votes"] < 2:
                    self.persisted_triple_riding.discard(object_id)

            # Helmet Violation:
            # Strict compliance verification: if rider has solid helmet detection, immediately mark compliant.
            # Only declare violation after minimum observation window (>= 6 obs) with overwhelming evidence.
            if self.config.detect_helmet_violation:
                nh_votes = stats["no_helmet_votes"]
                wh_votes = stats["with_helmet_votes"]
                if stats["max_wh_conf"] >= 0.38 or wh_votes >= 2 or wh_votes >= nh_votes:
                    self.persisted_helmet_violations.discard(object_id)
                elif (
                    stats["total_obs"] >= 6
                    and nh_votes >= 5
                    and nh_votes >= 3 * wh_votes
                    and stats["max_nh_conf"] >= 0.60
                    and stats["max_wh_conf"] < 0.35
                ):
                    self.persisted_helmet_violations.add(object_id)
                else:
                    self.persisted_helmet_violations.discard(object_id)

        return list(self.persisted_helmet_violations), list(self.persisted_triple_riding)

    def predict_riders(self, img):
        if img is None or not hasattr(img, "shape") or img.shape[0] < 85 or img.shape[1] < 50 or not hasattr(self, "model"):
            return False, False, 0, []

        try:
            ch, cw = img.shape[:2]
            # Letterbox and preprocess for YOLOv5
            img_sz = (self.config.imgsz, self.config.imgsz)
            img_lb, ratio, (dw, dh) = letterbox(img, img_sz, auto=True, stride=32)
            im = img_lb.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
            im = np.ascontiguousarray(im)
            im = torch.from_numpy(im).float().to(self.config.device) / 255.0
            im = im[None]  # batch dimension

            with torch.no_grad():
                results = self.model(im)
                if isinstance(results, (list, tuple)):
                    results = results[0]

                if results.ndim == 3:
                    # YOLOv5 detection output with configured threshold
                    dets = non_max_suppression(results, conf_thres=0.20, iou_thres=0.35)
                    if len(dets) > 0 and len(dets[0]) > 0:
                        raw_dets = dets[0].cpu().numpy()
                        # Sort raw detections by confidence descending
                        raw_dets = sorted(raw_dets, key=lambda d: float(d[4]), reverse=True)
                        
                        filtered_heads = []
                        r_x = ratio[0] if isinstance(ratio, (tuple, list)) else ratio
                        r_y = ratio[1] if isinstance(ratio, (tuple, list)) else ratio

                        for d in raw_dets:
                            box = d[:4]
                            conf = float(d[4])
                            cls_id = int(d[5])

                            # Convert coordinates from letterboxed 384x384 space to crop space
                            x1_crop = (box[0] - dw) / max(0.001, r_x)
                            y1_crop = (box[1] - dh) / max(0.001, r_y)
                            x2_crop = (box[2] - dw) / max(0.001, r_x)
                            y2_crop = (box[3] - dh) / max(0.001, r_y)

                            # Spatial filter: Head must be in upper 65% of the motorcycle crop
                            cy_crop = (y1_crop + y2_crop) / 2.0
                            if cy_crop > 0.65 * ch:
                                continue

                            cx = (x1_crop + x2_crop) / 2.0
                            cy = cy_crop

                            # Exclude detections whose centers are outside the motorcycle seating zone
                            # (prevents bleed from passing vehicles or pedestrians in adjacent lanes)
                            if cx < 0.08 * cw or cx > 0.92 * cw:
                                continue

                            bw = max(8, x2_crop - x1_crop)
                            bh = max(8, y2_crop - y1_crop)

                            matched = False
                            for h in filtered_heads:
                                h_cx = h["cx"]
                                h_cy = h["cy"]
                                h_bw = h["bw"]
                                h_bh = h["bh"]

                                dx = abs(cx - h_cx)
                                dy = abs(cy - h_cy)
                                # A human rider on a motorcycle spans vertically from helmet to neck/chin.
                                # Duplicate detections on the same person have small horizontal offset.
                                if dx < max(35.0, 0.70 * max(bw, h_bw)) or np.hypot(dx, dy) < max(bw, bh, h_bw, h_bh) * 0.95:
                                    matched = True
                                    # If either detection has With Helmet (cls 0), this person is wearing a helmet
                                    if cls_id == 0 and conf >= 0.25:
                                        h["cls_id"] = 0
                                        h["conf"] = max(h["conf"], conf)
                                        h["box"] = [x1_crop, y1_crop, x2_crop, y2_crop]
                                        h["cx"] = cx
                                        h["cy"] = cy
                                    elif h["cls_id"] == 1 and cls_id == 1 and conf > h["conf"]:
                                        h["conf"] = conf
                                    break
                            if not matched:
                                filtered_heads.append({
                                    "box": [x1_crop, y1_crop, x2_crop, y2_crop],
                                    "conf": conf,
                                    "cls_id": cls_id,
                                    "cx": cx,
                                    "cy": cy,
                                    "bw": bw,
                                    "bh": bh,
                                })

                        # Valid heads: any rider with conf >= 0.25
                        valid_heads = [h for h in filtered_heads if h["conf"] >= 0.25]
                        total_riders = len(valid_heads)

                        wh_heads = [h for h in valid_heads if h["cls_id"] == 0 and h["conf"] >= 0.28]
                        nh_heads = [h for h in valid_heads if h["cls_id"] == 1 and h["conf"] >= 0.50]

                        with_helmet_count = len(wh_heads)
                        no_helmet_count = len(nh_heads)

                        max_wh_conf = max([h["conf"] for h in wh_heads], default=0.0)
                        max_nh_conf = max([h["conf"] for h in nh_heads], default=0.0)

                        if max_wh_conf >= 0.35 or with_helmet_count >= no_helmet_count:
                            has_no_helmet = False
                        else:
                            has_no_helmet = (no_helmet_count > with_helmet_count and max_nh_conf >= 0.52)

                        # Triple riding verification:
                        # Must have >= 3 riders, motorcycle height >= 140px, aspect ratio cw <= 1.20 * ch,
                        # at least one head with conf >= 0.50, and tandem distribution across bike
                        triple_thres = max(3, getattr(self.config, 'triple_riding_threshold', 3))
                        is_triple = False
                        if total_riders >= triple_thres and ch >= 140 and cw <= 1.20 * ch:
                            xs = sorted([h["cx"] for h in valid_heads])
                            spread = xs[-1] - xs[0]
                            max_rider_conf = max([h["conf"] for h in valid_heads])
                            d12 = xs[1] - xs[0]
                            d23 = xs[2] - xs[1]
                            if max_rider_conf >= 0.50 and spread >= max(40.0, 0.28 * cw) and d12 >= 18.0 and d23 >= 18.0:
                                is_triple = True

                        return has_no_helmet, is_triple, total_riders, valid_heads
                    return False, False, 0, []
                elif results.ndim == 2:
                    p = F.softmax(results, dim=1)
                    i = p.argmax()
                    has_no_helmet = (int(i) == self.config.violation_idx and p[0, i] >= 0.50)
                    return has_no_helmet, False, (1 if p[0, i] >= 0.50 else 0), []
                else:
                    return False, False, 0, []
        except Exception:
            return False, False, 0, []

    def predict(self, img):
        has_no_helmet, _, _, _ = self.predict_riders(img)
        return has_no_helmet

    def ready_check(self):
        if not self.config.model_path or not os.path.exists(self.config.model_path):
            return False
        if not hasattr(self, "model") or self.model is None:
            return self.load_model()
        return True
