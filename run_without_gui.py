import argparse
import cv2
import sys
import time
import logging
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YOLOV5_PATH = os.path.join(CURRENT_DIR, "yolov5_repo")
if YOLOV5_PATH not in sys.path:
    sys.path.insert(0, YOLOV5_PATH)

from tqdm import tqdm
from tvdr.core import PipelineConfig, Pipeline
from tvdr.utils.path import create_folder

logging.basicConfig()
logger = logging.getLogger("tvdr")
logger.setLevel(logging.INFO)


def parser():
    parser = argparse.ArgumentParser(
        description="Traffic Violation Detection CLI"
    )
    parser.add_argument(
        "--config_file",
        type=str,
        default="default_config.json",
        help="path to configuration json file",
    )
    parser.add_argument(
        "--video_path",
        type=str,
        default=None,
        help="path to video file to process",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="device to use (cpu or cuda)",
    )
    parser.add_argument(
        "--output_dir",
        "--output_path",
        dest="output_dir",
        type=str,
        default="result",
        help="directory to save result video",
    )
    parser.add_argument(
        "--max_frames",
        type=int,
        default=None,
        help="optional maximum frames to process",
    )
    return parser


def main():
    args = parser().parse_args()
    create_folder(args.output_dir)

    # Initialize configuration
    cfg = PipelineConfig()
    if args.config_file and os.path.exists(args.config_file):
        try:
            cfg.load_config(args.config_file)
        except Exception as e:
            logger.warning(f"Could not load config file {args.config_file}: {e}")

    if args.video_path:
        cfg.video_path = args.video_path

    if args.device:
        cfg.vd_config.device = args.device
        cfg.hv_config.device = args.device

    video_path = cfg.video_path
    if not video_path or not os.path.exists(video_path):
        print(f"ERROR: Video file '{video_path}' does not exist!")
        return 1

    print(f"Initializing TVDR Pipeline...")
    pipeline = Pipeline(cfg)
    if not pipeline.ready_check():
        print("WARNING: Pipeline ready check failed, attempting to proceed...")

    pipeline.video_recorder_init(video_path)

    vid = cv2.VideoCapture(video_path)
    if not vid.isOpened():
        print(f"ERROR: Cannot open video '{video_path}'")
        return 1

    total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = vid.get(cv2.CAP_PROP_FPS) or 30.0
    if args.max_frames and args.max_frames < total_frames:
        total_frames = args.max_frames

    print(f"Processing '{video_path}': {total_frames} frames @ {fps:.1f} FPS")
    start_time = time.time()

    violations_count = {
        "Red Light": 0,
        "No Helmet": 0,
        "Triple Riding": 0,
        "Wrong Way": 0,
    }

    seen_violations = set()

    for i in tqdm(range(total_frames)):
        ret, frame = vid.read()
        if not ret or frame is None:
            break

        timestamp_str = f"{int(i / fps // 60):02d}:{int(i / fps % 60):02d}.{int((i % fps) / fps * 10):01d}"
        result_frame = pipeline.update(frame, frame_idx=i, timestamp=timestamp_str)
        pipeline.video_recorder_update(result_frame)

        # Log new violation events
        for ev in getattr(pipeline, "latest_events", []):
            vkey = (ev["vehicle_id"], ev["type"])
            if vkey not in seen_violations:
                seen_violations.add(vkey)
                vtype = ev["type"]
                if "Red" in vtype:
                    violations_count["Red Light"] += 1
                elif "Helmet" in vtype:
                    violations_count["No Helmet"] += 1
                elif "Triple" in vtype:
                    violations_count["Triple Riding"] += 1
                elif "Wrong" in vtype:
                    violations_count["Wrong Way"] += 1
                tqdm.write(f"[{ev['timestamp']}] Frame {i}: {ev['type']} on Vehicle #{ev['vehicle_id']} ({ev['details']})")

    out_file = pipeline.video_recorder_close()
    vid.release()
    elapsed = time.time() - start_time

    print(f"\nProcessing Complete!")
    print(f"Output saved to: {out_file}")
    print(f"Total Time: {elapsed:.2f}s ({total_frames / max(elapsed, 0.001):.1f} FPS)")
    print(f"Violations Summary:")
    for k, v in violations_count.items():
        print(f"  - {k}: {v}")

    return 0


if __name__ == "__main__":
    main()
