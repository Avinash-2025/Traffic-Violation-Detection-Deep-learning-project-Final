import torch
from typing import List


class HelmetViolationConfig:
    """Helmet Violation Configuration"""

    def __init__(
        self,
        model_path: str = "models/helmet_detection/best.pt",
        device: str = None,
        imgsz: int = 384,
        vehicle_idx: List[int] = [1, 4],  # Store 2 wheel vehicle class idx
        violation_idx: int = 1,  # Index no helmet model (0: With Helmet, 1: Without Helmet)
        conf_thres: float = 0.32,
        min_age: int = 2,
        detect_interval: int = 1,
        triple_riding_threshold: int = 3,
        detect_triple_riding: bool = True,
        detect_helmet_violation: bool = True,
    ):
        self.model_path = model_path if model_path is not None else "models/helmet_detection/best.pt"
        self.imgsz = imgsz
        self.vehicle_idx = vehicle_idx
        self.violation_idx = violation_idx
        self.conf_thres = conf_thres
        self.min_age = min_age
        self.detect_interval = detect_interval
        self.triple_riding_threshold = triple_riding_threshold
        self.detect_triple_riding = detect_triple_riding
        self.detect_helmet_violation = detect_helmet_violation

        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device
