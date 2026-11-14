import os
import torch
import cv2
import numpy as np
import logging

from tvdr.utils.general import (
    check_img_size,
    letterbox,
    non_max_suppression,
    scale_coords,
    combine_yolo_sort_result,
)
from .configuration_vehicle_detection import VehicleDetectionConfig
from ..sort import Sort

class VehicleDetection:
    def __init__(self, config: VehicleDetectionConfig):
        self.config = config
        self.load_model()
        self.load_tracker()

    def load_model(self):
        try:
            # Load vehicle detection model (yolo5 architecture)
            repo = "yolov5_repo" if os.path.isdir("yolov5_repo") else "ultralytics/yolov5"
            source = "local" if os.path.isdir("yolov5_repo") else "github"
            self.model = torch.hub.load(
                repo, "custom", path=self.config.model_path, source=source
            )
            # Calculate best imgsz based on model stride
            self.imgsz = check_img_size(self.config.imgsz, self.model.stride)

            # Warmup model if device is 'gpu'
            if self.config.device == "gpu":
                dummy_im = torch.zeros((1, 3, self.imgsz, self.imgsz)).to(
                    self.config.device
                )
                self.model.forward(dummy_im)
            return True

        except Exception as e:
            logging.info(e)
            return False

    def load_tracker(self):
        # Load tracker
        # Currently only support forSORT, maybe in the future i will add DeepSORT or another good tracker method
        try:
            if self.config.tracker == "SORT":
                self.tracker = Sort(
                    self.config.sort_max_age,
                    self.config.sort_min_hits,
                    self.config.sort_iou_thres,
                )
            return True
        except:
            return False

    def update(self, img):
        # Detect vehicle object
        preds = self.predict(img)

        # Track vehicle object
        preds = self.track(preds)

        # Post-processing (Remove object outside detection area)
        img_size = img.shape
        preds = self.post_processing(preds, img_size)

        return preds

    def reset_tracker(self):
        if self.config.tracker == "SORT":
            self.tracker.reset_count()

    def predict(self, img) -> np.ndarray:
        # Padding image
        im = letterbox(
            img,
            new_shape=self.imgsz,
            stride=self.model.stride,
            auto=True,
            scaleFill=True,
        )[0]

        # Convert cv2 colorspace from bgr to rgb
        im = im.transpose((2, 0, 1))[::-1]
        im = np.ascontiguousarray(im)
        im = torch.from_numpy(im).to(self.config.device).float()

        # Normalize
        im = im / 255

        # if inference is single image size then add dimension
        if len(im.shape) == 3:
            im = im[None]

        # Inference img
        preds = self.model(im)

        # Non Max Suppression
        preds = non_max_suppression(
            prediction=preds,
            conf_thres=self.config.conf_thres,
            iou_thres=self.config.iou_thres,
            max_det=self.config.max_detection,
        )

        # Rescale result to original resolution
        preds = preds[0]
        preds[:, :4] = scale_coords(im.shape[2:], preds[:, :4], img.shape).round()

        # Convert to tensor cpu if tensor cuda
        if preds.is_cuda:
            preds = preds.cpu()

        return preds.numpy()

    def track(self, preds: np.ndarray):
        if self.config.tracker == "SORT":
            bbox = preds[:, 0:5]
            sort_result = self.tracker.update(bbox)
            tracker_result = combine_yolo_sort_result(preds, sort_result)

            return tracker_result

    def post_processing(self, preds, img_shape):
        if preds is None or len(preds) == 0:
            return np.empty((0, 7))

        da = self.config.detection_area
        if da is None or len(da) < 3:
            return preds

        da_arr = np.array(da, dtype=np.float32)
        # Check if full-frame (corners around 0 and 1)
        if len(da) == 4 and da_arr[:, 0].min() <= 0.05 and da_arr[:, 0].max() >= 0.95 and da_arr[:, 1].min() <= 0.05 and da_arr[:, 1].max() >= 0.95:
            return preds

        h, w = img_shape[:2]
        pts_pixel = np.array([[int(p[0] * w), int(p[1] * h)] for p in da], dtype=np.int32)

        result_post = np.empty((0, preds.shape[1]))
        for obj in preds:
            cx = int((obj[0] + obj[2]) / 2.0)
            cy = int((obj[1] + obj[3]) / 2.0)
            # Check centroid in polygon
            dist = cv2.pointPolygonTest(pts_pixel, (cx, cy), False)
            if dist >= 0:
                result_post = np.append(result_post, obj.reshape(1, preds.shape[1]), axis=0)

        return result_post

    def ready_check(self) -> bool:
        """Ready Check"""
        if not self.config.model_path:
            return False

        if len(self.config.detection_area) < 3:
            return False

        # Force Reload Model and Tracker
        if self.load_model() == False:
            logging.info("Failed to initialize VD Model")
            return False

        if self.load_tracker() == False:
            return False

        return True
