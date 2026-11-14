import os
import sys
import torch

# Ensure yolov5_repo is on path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
_YOLOV5_PATH = os.path.join(_PARENT_DIR, "yolov5_repo")
if os.path.isdir(_YOLOV5_PATH) and _YOLOV5_PATH not in sys.path:
    sys.path.insert(0, _YOLOV5_PATH)

# Patch torch.load for PyTorch 2.6+ compatibility with older YOLO checkpoints
_orig_torch_load = torch.load


def _patched_torch_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)


torch.load = _patched_torch_load

