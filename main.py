import os
import sys

# Ensure yolov5_repo is on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YOLOV5_PATH = os.path.join(CURRENT_DIR, "yolov5_repo")
if YOLOV5_PATH not in sys.path:
    sys.path.insert(0, YOLOV5_PATH)

from tvdr.interfacev2.main_window import MainWindows


def main():
    MainWindows()


if __name__ == "__main__":
    main()
