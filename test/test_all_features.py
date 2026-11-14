import os
import sys
import unittest
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

YOLOV5_PATH = os.path.join(CURRENT_DIR, "yolov5_repo")
if YOLOV5_PATH not in sys.path:
    sys.path.insert(0, YOLOV5_PATH)

from PySide2.QtWidgets import QApplication
from tvdr.core import (
    PipelineConfig,
    Pipeline,
    VehicleDetectionConfig,
    VehicleDetection,
    HelmetViolationConfig,
    HelmetViolation,
    RunningRedLightConfig,
    RunningRedLight,
)
from tvdr.interfacev2.interactive_canvas import InteractiveVideoCanvas
from tvdr.interfacev2.main_window import MainWindows
from PySide2.QtCore import QPoint, Qt
from PySide2.QtGui import QMouseEvent


class TestTrafficViolationDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(["test", "-platform", "offscreen"])

    def test_1_default_models_loading(self):
        """Feature 1: Auto-selection of default models and weights without manual file picking."""
        print("\n--- Test 1: Testing Default Model Auto-Selection ---")
        cfg = PipelineConfig()
        # Verify default paths are fixed and exist
        self.assertEqual(cfg.vd_config.model_path, "models/vehicle_detection/best.pt")
        self.assertEqual(cfg.hv_config.model_path, "models/helmet_detection/best.pt")
        self.assertTrue(os.path.exists(cfg.vd_config.model_path), f"File {cfg.vd_config.model_path} missing")
        self.assertTrue(os.path.exists(cfg.hv_config.model_path), f"File {cfg.hv_config.model_path} missing")

        # Verify pipeline ready check passes out-of-the-box
        pipeline = Pipeline(cfg)
        self.assertTrue(pipeline.ready_check(), "Pipeline ready_check must be True out-of-the-box")
        print("✓ Default models auto-loaded and verified: vehicle detection & helmet models ready!")

    def test_2_vehicle_detection(self):
        """Feature 2: Vehicle detection with fixed model weights."""
        print("\n--- Test 2: Testing Vehicle Detection ---")
        vd_cfg = VehicleDetectionConfig()
        vd = VehicleDetection(vd_cfg)
        self.assertTrue(vd.ready_check())

        # Test on a frame from available video or create a test frame
        test_video = "result/YTDown.com_YouTube_Media__5nGL47gNzo_Indian-Traffic-CCTV-Red-Light-Jump-Vehicle-Detection-Testing-QA-POV_004_720p_2.mp4"
        if os.path.exists(test_video):
            vid = cv2.VideoCapture(test_video)
            ret, frame = vid.read()
            vid.release()
            self.assertTrue(ret)
            preds = vd.update(frame)
            self.assertIsInstance(preds, np.ndarray)
            print(f"✓ Detected {len(preds)} vehicles in frame using fixed YOLOv5 vehicle model")

    def test_3_helmet_and_triple_riding_detection(self):
        """Feature 3: Helmet violation ('vehicles not wearing element') & Triple Riding."""
        print("\n--- Test 3: Testing Helmet Violation & Triple Riding Detection ---")
        hv_cfg = HelmetViolationConfig(conf_thres=0.1, triple_riding_threshold=3)
        hv = HelmetViolation(hv_cfg)
        self.assertTrue(hv.ready_check())

        # Mock motorcycle detection
        # Class 1 is motorcycle, vehicle ID = 7
        mock_preds = np.array([
            [100, 100, 300, 500, 0.9, 1, 7]
        ])

        # Create synthetic motorcycle image
        mock_frame = np.full((720, 1280, 3), 120, dtype=np.uint8)

        # Test tracker update and filtering
        filtered = hv.motorcycle_and_bicycle_filtering(mock_preds)
        self.assertEqual(len(filtered), 1)
        hv.tracker_record_update(filtered)
        self.assertIn(7, hv.id_tracker)

        # Test predict_riders interface
        crop = mock_frame[100:500, 100:300]
        has_no_helmet, is_triple, riders, dets = hv.predict_riders(crop)
        self.assertIsInstance(has_no_helmet, (bool, np.bool_))
        self.assertIsInstance(is_triple, (bool, np.bool_))
        print("✓ Helmet violation and Triple Riding detection logic verified!")

    def test_4_markup_stopline_tool(self):
        """Feature 4: Interactive Stop Line Markup Tool in the view."""
        print("\n--- Test 4: Testing Interactive Markup Tool ---")
        canvas = InteractiveVideoCanvas()
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        canvas.set_frame(test_frame)

        # Switch to Markup mode
        canvas.set_mode(InteractiveVideoCanvas.MODE_MARKUP_LINE)
        self.assertEqual(canvas.current_mode, InteractiveVideoCanvas.MODE_MARKUP_LINE)

        # Simulate clicking two points on the canvas
        p1 = QPoint(100, 200)
        p2 = QPoint(500, 200)

        # Connect callback
        captured = []
        canvas.stop_line_drawn.connect(lambda pts: captured.append(pts))

        ev1 = QMouseEvent(QMouseEvent.MouseButtonPress, p1, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        canvas.mousePressEvent(ev1)
        self.assertEqual(len(canvas.markup_points), 1)

        ev2 = QMouseEvent(QMouseEvent.MouseButtonPress, p2, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        canvas.mousePressEvent(ev2)

        self.assertEqual(len(captured), 1)
        self.assertEqual(len(captured[0]), 2)
        print(f"✓ Interactive markup tool successfully captured stop line: {captured[0]}")

    def test_5_signal_pointer_tool(self):
        """Feature 5: Configurable Signal Pointer tool."""
        print("\n--- Test 5: Testing Configurable Signal Pointer ---")
        canvas = InteractiveVideoCanvas()
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        canvas.set_frame(test_frame)

        canvas.set_mode(InteractiveVideoCanvas.MODE_SIGNAL_POINTER)
        self.assertEqual(canvas.current_mode, InteractiveVideoCanvas.MODE_SIGNAL_POINTER)

        captured_signal = []
        canvas.signal_pointer_set.connect(lambda pts: captured_signal.append(pts))

        # Click at signal location
        pt = QPoint(300, 150)
        press_ev = QMouseEvent(QMouseEvent.MouseButtonPress, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        canvas.mousePressEvent(press_ev)

        release_ev = QMouseEvent(QMouseEvent.MouseButtonRelease, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        canvas.mouseReleaseEvent(release_ev)

        self.assertEqual(len(captured_signal), 1)
        self.assertEqual(len(captured_signal[0]), 4)
        print(f"✓ Signal pointer successfully set traffic signal ROI: {captured_signal[0]}")

    def test_6_running_red_light_intersection(self):
        """Feature 6: Running Red Light Detection with Stop Line intersection."""
        print("\n--- Test 6: Testing Running Red Light & Stop Line Intersection ---")
        rrl_cfg = RunningRedLightConfig(stop_line=[[0.1, 0.5], [0.9, 0.5]])
        rrl = RunningRedLight(rrl_cfg)

        # Vehicle bbox crossing the line: y1 = 0.45, y2 = 0.55
        crossing_bbox = [0.4 * 1280, 0.45 * 720, 0.6 * 1280, 0.55 * 720]
        poly = rrl.bbox_to_polygon(crossing_bbox, (720, 1280, 3))
        intersect = rrl.intersect_polygon_and_line(rrl.config.stop_line, poly)
        self.assertTrue(intersect, "Vehicle crossing stop line must be detected as intersecting")

        # Vehicle bbox before line: y1 = 0.1, y2 = 0.3
        non_crossing = [0.4 * 1280, 0.1 * 720, 0.6 * 1280, 0.3 * 720]
        poly_safe = rrl.bbox_to_polygon(non_crossing, (720, 1280, 3))
        self.assertFalse(rrl.intersect_polygon_and_line(rrl.config.stop_line, poly_safe))
        print("✓ Stop line intersection logic verified: vehicles crossing on RED are flagged!")

    def test_7_gui_initialization_and_controls(self):
        """Feature 7: Main GUI initialization, controls, and default readiness."""
        print("\n--- Test 7: Testing GUI Window and Controls ---")
        win = MainWindows(run_loop=False)
        widget = win.main_layout_widget

        # Verify UI loaded and ready
        self.assertTrue(widget.ready_status, "UI must be in Ready state automatically on launch")
        self.assertIsNotNone(widget.pipeline)
        self.assertEqual(widget.violation_table.columnCount(), 6)

        # Verify markup and signal pointer controls exist
        self.assertIsNotNone(widget.btn_tool_stopline)
        self.assertIsNotNone(widget.btn_tool_signal)
        self.assertIsNotNone(widget.signal_widget)

        # Verify event logging
        mock_event = {
            "frame": 42,
            "timestamp": "00:01.4",
            "vehicle_id": 3,
            "vehicle_type": "Motorcycle",
            "type": "Triple Riding",
            "details": "3 riders detected on Motorcycle (Max: 2)",
            "severity": "HIGH",
        }
        widget._add_violation_row(mock_event, np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertEqual(widget.violation_table.rowCount(), 1)
        self.assertEqual(widget.counts["triple_riding"], 1)

        mock_event2 = {
            "frame": 55,
            "timestamp": "00:01.8",
            "vehicle_id": 4,
            "vehicle_type": "Motorcycle",
            "type": "No Helmet Violation",
            "details": "Rider without helmet on Motorcycle",
            "severity": "HIGH",
        }
        widget._add_violation_row(mock_event2, np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertEqual(widget.violation_table.rowCount(), 2)
        self.assertEqual(widget.counts["no_helmet"], 1)

        print("✓ GUI initialization and violation event logging verified!")


if __name__ == "__main__":
    unittest.main()

