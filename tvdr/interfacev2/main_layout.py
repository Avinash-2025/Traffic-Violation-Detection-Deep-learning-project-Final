import os
import sys
import time
import csv
import json
import cv2
import numpy as np

from PySide2.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QSlider,
    QMessageBox,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFrame,
    QAbstractItemView,
    QScrollArea,
    QSizePolicy,
)
from PySide2.QtCore import Qt, QTimer, Signal, QSize
from PySide2.QtGui import QPixmap, QImage, QColor, QFont, QPainter, QBrush, QPen

from tvdr.core import (
    PipelineConfig,
    Pipeline,
    VehicleDetectionConfig,
    RunningRedLightConfig,
    HelmetViolationConfig,
    WrongWayDetectionConfig,
)
from .interactive_canvas import InteractiveVideoCanvas
from .vehicle_detection_window import VehicleDetectionInterface
from .running_redlight_window import RunningRedLightInterface
from .helmet_violation_window import HelmetViolationInterface
from .wrongway_window import WrongWayInterface
from .theme import (
    BG_APP,
    SURFACE,
    SURFACE_ELEVATED,
    BORDER,
    PRIMARY_CYAN,
    PRIMARY_CYAN_HOVER,
    SECONDARY_INDIGO,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    SUCCESS_READY,
    WARNING,
    DANGER,
    COLOR_RED_LIGHT,
    COLOR_NO_HELMET,
    COLOR_TRIPLE_RIDING,
    COLOR_WRONG_WAY,
    COLOR_VEHICLES,
    SIGNAL_RED,
    SIGNAL_YELLOW,
    SIGNAL_GREEN,
    LETTERBOX_BG,
    COMMAND_CENTER_QSS,
)


class SignalWidget(QFrame):
    """Compact Traffic Signal pill widget with 3 round 14px lamps and glowing active state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 19px; padding: 2px 10px;"
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(8)

        # 3 round lamps
        self.red_lamp = QLabel()
        self.yellow_lamp = QLabel()
        self.green_lamp = QLabel()

        for lamp in (self.red_lamp, self.yellow_lamp, self.green_lamp):
            lamp.setFixedSize(14, 14)

        layout.addWidget(self.red_lamp)
        layout.addWidget(self.yellow_lamp)
        layout.addWidget(self.green_lamp)

        self.label = QLabel("GREEN – GO")
        font = QFont("Inter", 11, QFont.Bold)
        self.label.setFont(font)
        layout.addWidget(self.label)

        self.setLayout(layout)
        self.set_state("green")

    def set_state(self, state: str):
        state_str = str(state).lower()
        dim_red = "background-color: rgba(239, 68, 68, 0.18); border-radius: 7px; border: 1px solid rgba(239, 68, 68, 0.3);"
        dim_yellow = "background-color: rgba(250, 204, 21, 0.18); border-radius: 7px; border: 1px solid rgba(250, 204, 21, 0.3);"
        dim_green = "background-color: rgba(34, 197, 94, 0.18); border-radius: 7px; border: 1px solid rgba(34, 197, 94, 0.3);"

        lit_red = f"background-color: {SIGNAL_RED}; border-radius: 7px; border: 2px solid #FFFFFF;"
        lit_yellow = f"background-color: {SIGNAL_YELLOW}; border-radius: 7px; border: 2px solid #FFFFFF;"
        lit_green = f"background-color: {SIGNAL_GREEN}; border-radius: 7px; border: 2px solid #FFFFFF;"

        if state_str == "red":
            self.red_lamp.setStyleSheet(lit_red)
            self.yellow_lamp.setStyleSheet(dim_yellow)
            self.green_lamp.setStyleSheet(dim_green)
            self.label.setText("RED – STOP")
            self.label.setStyleSheet(f"color: {SIGNAL_RED}; font-weight: 700; font-size: 11px;")
        elif state_str == "yellow":
            self.red_lamp.setStyleSheet(dim_red)
            self.yellow_lamp.setStyleSheet(lit_yellow)
            self.green_lamp.setStyleSheet(dim_green)
            self.label.setText("CAUTION")
            self.label.setStyleSheet(f"color: {SIGNAL_YELLOW}; font-weight: 700; font-size: 11px;")
        else:
            self.red_lamp.setStyleSheet(dim_red)
            self.yellow_lamp.setStyleSheet(dim_yellow)
            self.green_lamp.setStyleSheet(lit_green)
            self.label.setText("GREEN – GO")
            self.label.setStyleSheet(f"color: {SIGNAL_GREEN}; font-weight: 700; font-size: 11px;")


class CounterCard(QFrame):
    """Modern command center stat card with 15% opacity icon chip, 32px bold number, and thin bottom accent line."""

    def __init__(self, title: str, color_hex: str, label_code: str = "", parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedHeight(84)
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-bottom: 3px solid {color_hex};
                border-radius: 12px;
            }}
            """
        )

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(14, 10, 14, 8)
        v_layout.setSpacing(2)

        # Top row: title label + icon badge chip
        top_h = QHBoxLayout()
        top_h.setSpacing(6)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; border: none;")
        top_h.addWidget(title_lbl)
        top_h.addStretch(1)

        chip = QLabel(label_code)
        chip.setStyleSheet(
            f"background-color: rgba({int(color_hex[1:3], 16)}, {int(color_hex[3:5], 16)}, {int(color_hex[5:7], 16)}, 0.16); "
            f"color: {color_hex}; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; border: none;"
        )
        top_h.addWidget(chip)
        v_layout.addLayout(top_h)

        # Bottom row: Big 32px bold stat number in tabular numerals
        self.count_lbl = QLabel("0")
        self.count_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 30px; font-weight: 700; font-family: 'JetBrains Mono', 'Roboto Mono', monospace; border: none;"
        )
        v_layout.addWidget(self.count_lbl)

        self.setLayout(v_layout)

    def set_count(self, count: int):
        self.count_lbl.setText(str(count))


class ModelCard(QFrame):
    """Compact 2x2 Model Card with name, weights, status chip, and gear config button."""

    def __init__(self, name: str, weights: str, on_config_cb, parent=None):
        super().__init__(parent)
        self.on_config_cb = on_config_cb
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {SURFACE_ELEVATED};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
            """
        )

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(8, 8, 8, 8)
        v_layout.setSpacing(4)

        # Top row: Name + Gear button
        top_h = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 11px; border: none;")
        top_h.addWidget(name_lbl)
        top_h.addStretch(1)

        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(22, 22)
        gear_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT_SECONDARY};
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: {PRIMARY_CYAN};
                color: {PRIMARY_CYAN};
                background-color: {SURFACE};
            }}
            """
        )
        gear_btn.setToolTip(f"Configure {name}")
        gear_btn.clicked.connect(self.on_config_cb)
        top_h.addWidget(gear_btn)
        v_layout.addLayout(top_h)

        # Subtitle: weights
        weights_lbl = QLabel(weights)
        weights_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; border: none;")
        v_layout.addWidget(weights_lbl)

        # Bottom row: Status chip (Ready = green dot)
        chip_h = QHBoxLayout()
        self.dot = QLabel()
        self.dot.setFixedSize(7, 7)
        self.dot.setStyleSheet(f"background-color: {SUCCESS_READY}; border-radius: 3px; border: none;")

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color: {SUCCESS_READY}; font-size: 10px; font-weight: 600; border: none;")

        chip_h.addWidget(self.dot)
        chip_h.addWidget(self.status_lbl)
        chip_h.addStretch(1)
        v_layout.addLayout(chip_h)

        self.setLayout(v_layout)

    def set_status(self, is_ready: bool, text: str = None):
        color = SUCCESS_READY if is_ready else DANGER
        self.dot.setStyleSheet(f"background-color: {color}; border-radius: 3px; border: none;")
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600; border: none;")
        self.status_lbl.setText(text if text else ("Ready" if is_ready else "Error"))


class MainLayout(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(COMMAND_CENTER_QSS)

        # 1. Pipeline Initialize with project defaults
        self.pipeline_cfg = PipelineConfig()
        self.pipeline = Pipeline(self.pipeline_cfg)
        self.is_playing = False
        self.vid = None
        self.frame_total = 0
        self.current_frame_idx = 0
        self.recorded_events = []
        self.seen_violations = set()

        # Violation counters
        self.counts = {
            "red_light": 0,
            "no_helmet": 0,
            "triple_riding": 0,
            "wrong_way": 0,
            "total_vehicles": 0,
        }

        # 2. Main Layout Container: Top Header + Body (Left Sidebar & Center Stage)
        root_v_layout = QVBoxLayout()
        root_v_layout.setContentsMargins(12, 10, 12, 10)
        root_v_layout.setSpacing(10)

        # Header Bar (56px)
        header_bar = self._create_header_bar()
        root_v_layout.addWidget(header_bar)

        # Splitter / Main Content Area
        body_h_layout = QHBoxLayout()
        body_h_layout.setContentsMargins(0, 0, 0, 0)
        body_h_layout.setSpacing(10)

        # Left panel: Configuration & Controls (320px)
        left_panel = self._create_left_panel()
        body_h_layout.addWidget(left_panel, 0)

        # Center stage: Stats + Toolbar + Video Canvas + Player Bar + Violations Table
        center_panel = self._create_center_panel()
        body_h_layout.addWidget(center_panel, 1)

        root_v_layout.addLayout(body_h_layout)
        self.setLayout(root_v_layout)

        # 3. Connect Canvas Signals
        self.canvas.stop_line_drawn.connect(self._on_stop_line_drawn)
        self.canvas.signal_pointer_set.connect(self._on_signal_pointer_set)
        self.canvas.detection_area_set.connect(self._on_detection_area_set)
        self.canvas.direction_arrow_set.connect(self._on_direction_arrow_set)

        # 4. Timer for Video Playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # 5. Auto-load default video & perform ready check
        self._init_defaults()

    def _init_defaults(self):
        """Auto-loads default video and initializes models so everything is immediately Ready."""
        if self.pipeline_cfg.video_path and os.path.exists(self.pipeline_cfg.video_path):
            self._load_video_from_path(self.pipeline_cfg.video_path)

        self.ready_check()

    def _create_header_bar(self):
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(
            f"background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; padding: 4px 14px;"
        )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(10, 4, 10, 4)
        h_layout.setSpacing(14)

        # App Logo & Title
        title_group = QVBoxLayout()
        title_group.setSpacing(0)
        main_title = QLabel("Traffic Violation Detection")
        font_title = QFont("Inter", 15, QFont.Bold)
        main_title.setFont(font_title)
        main_title.setStyleSheet(f"color: {TEXT_PRIMARY}; border: none;")

        sub_title = QLabel("AI Multi-Model Surveillance • Smart-City Command Center")
        sub_title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
        title_group.addWidget(main_title)
        title_group.addWidget(sub_title)
        h_layout.addLayout(title_group)

        h_layout.addStretch(1)

        # Live Status Pill in Center
        self.status_pill = QFrame()
        self.status_pill.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 14px; padding: 4px 12px;"
        )
        pill_layout = QHBoxLayout()
        pill_layout.setContentsMargins(6, 2, 6, 2)
        pill_layout.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet(f"background-color: {SUCCESS_READY}; border-radius: 4px; border: none;")
        self.status_text = QLabel("DETECTING")
        self.status_text.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; border: none;")
        pill_layout.addWidget(self.status_dot)
        pill_layout.addWidget(self.status_text)
        self.status_pill.setLayout(pill_layout)
        h_layout.addWidget(self.status_pill)

        h_layout.addStretch(1)

        # Right: Signal Widget & FPS Badge
        self.signal_widget = SignalWidget()
        h_layout.addWidget(self.signal_widget)

        self.header_fps_badge = QLabel("0.0 FPS")
        self.header_fps_badge.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 8px; "
            f"padding: 6px 10px; color: {PRIMARY_CYAN}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;"
        )
        h_layout.addWidget(self.header_fps_badge)

        header.setLayout(h_layout)
        return header

    def _create_left_panel(self):
        container = QWidget()
        container.setFixedWidth(320)
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(8)

        # 1. Video Input Section
        vid_box = QGroupBox("VIDEO INPUT")
        vid_layout = QVBoxLayout()
        vid_layout.setContentsMargins(8, 12, 8, 8)
        vid_layout.setSpacing(6)

        self.video_lineedit = QLineEdit(self.pipeline_cfg.video_path or "")
        self.video_lineedit.setReadOnly(True)
        self.video_lineedit.setPlaceholderText("No video loaded...")
        self.video_lineedit.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 8px; color: {TEXT_PRIMARY}; font-size: 11px; padding: 6px;"
        )

        self.video_load_button = QPushButton("Browse Video")
        self.video_load_button.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 8px; color: {TEXT_PRIMARY}; padding: 6px;"
        )
        self.video_load_button.clicked.connect(self.load_video_dialog)

        vid_layout.addWidget(self.video_lineedit)
        vid_layout.addWidget(self.video_load_button)
        vid_box.setLayout(vid_layout)
        v_layout.addWidget(vid_box)

        # 2. 4 Fixed Models: 2x2 Grid with individual Gear config buttons
        models_box = QGroupBox("MODELS (FIXED WEIGHTS)")
        models_layout = QVBoxLayout()
        models_layout.setContentsMargins(8, 12, 8, 8)

        grid = QGridLayout()
        grid.setSpacing(6)

        self.card_m_vd = ModelCard("Vehicle Detector", "best.pt • YOLOv5", self.load_vd_config)
        self.card_m_hv = ModelCard("Helmet Violation", "best.pt • YOLOv5", self.load_hv_config)
        self.card_m_tr = ModelCard("Triple Riding", "Limit: ≥ 3 Riders", self.load_hv_config)
        self.card_m_rrl = ModelCard("Signal & StopLine", "Red Light Crossing", self.load_rrld_config)

        grid.addWidget(self.card_m_vd, 0, 0)
        grid.addWidget(self.card_m_hv, 0, 1)
        grid.addWidget(self.card_m_tr, 1, 0)
        grid.addWidget(self.card_m_rrl, 1, 1)

        models_layout.addLayout(grid)
        models_box.setLayout(models_layout)
        v_layout.addWidget(models_box)

        # 3. Configuration Profile: Segmented pair of secondary buttons
        cfg_io_box = QGroupBox("CONFIGURATION PROFILE")
        cfg_io_layout = QHBoxLayout()
        cfg_io_layout.setContentsMargins(8, 12, 8, 8)
        cfg_io_layout.setSpacing(6)

        self.load_cfg_btn = QPushButton("Load JSON")
        self.load_cfg_btn.clicked.connect(self.load_config_dialog)
        self.save_cfg_btn = QPushButton("Save JSON")
        self.save_cfg_btn.clicked.connect(self.save_config_dialog)

        cfg_io_layout.addWidget(self.load_cfg_btn)
        cfg_io_layout.addWidget(self.save_cfg_btn)
        cfg_io_box.setLayout(cfg_io_layout)
        v_layout.addWidget(cfg_io_box)

        # 4. Violation Snapshot: 16:9 preview card with dashed placeholder
        snapshot_box = QGroupBox("VIOLATION SNAPSHOT")
        snapshot_layout = QVBoxLayout()
        snapshot_layout.setContentsMargins(8, 12, 8, 8)

        self.snapshot_lbl = QLabel("Select violation row below to preview")
        self.snapshot_lbl.setAlignment(Qt.AlignCenter)
        self.snapshot_lbl.setFixedSize(302, 160)
        self.snapshot_lbl.setStyleSheet(
            f"background-color: {LETTERBOX_BG}; border: 1px dashed {BORDER}; border-radius: 8px; color: {TEXT_MUTED}; font-size: 11px;"
        )
        snapshot_layout.addWidget(self.snapshot_lbl)
        snapshot_box.setLayout(snapshot_layout)
        v_layout.addWidget(snapshot_box)

        v_layout.addStretch(1)

        # 5. Pinned Controls at Bottom
        ctrl_box = QFrame()
        ctrl_box.setStyleSheet(f"background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; padding: 6px;")
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setContentsMargins(8, 8, 8, 8)
        ctrl_layout.setSpacing(8)

        self.ready_btn = QPushButton("Re-Check Models")
        self.ready_btn.clicked.connect(self.ready_check)
        ctrl_layout.addWidget(self.ready_btn)

        h_ctrl = QHBoxLayout()
        h_ctrl.setSpacing(6)

        self.start_btn = QPushButton("Pause")
        self.start_btn.setObjectName("btnPrimary")
        self.start_btn.clicked.connect(self.toggle_start)

        self.stop_btn = QPushButton("Stop & Save")
        self.stop_btn.setObjectName("btnDanger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)

        h_ctrl.addWidget(self.start_btn)
        h_ctrl.addWidget(self.stop_btn)
        ctrl_layout.addLayout(h_ctrl)

        ctrl_box.setLayout(ctrl_layout)
        v_layout.addWidget(ctrl_box)

        container.setLayout(v_layout)
        return container

    def _create_center_panel(self):
        container = QWidget()
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(8)

        # 1. Stat Cards Row: 5 equal cards
        stat_bar = QHBoxLayout()
        stat_bar.setSpacing(8)

        self.card_red_light = CounterCard("Red Light", COLOR_RED_LIGHT, "RRL")
        self.card_no_helmet = CounterCard("No Helmet", COLOR_NO_HELMET, "HELMET")
        self.card_triple_riding = CounterCard("Triple Riding", COLOR_TRIPLE_RIDING, "3+ RIDER")
        self.card_wrong_way = CounterCard("Wrong Way", COLOR_WRONG_WAY, "WRONG WAY")
        self.card_total = CounterCard("Vehicles", COLOR_VEHICLES, "COUNT")

        stat_bar.addWidget(self.card_red_light)
        stat_bar.addWidget(self.card_no_helmet)
        stat_bar.addWidget(self.card_triple_riding)
        stat_bar.addWidget(self.card_wrong_way)
        stat_bar.addWidget(self.card_total)

        v_layout.addLayout(stat_bar)

        # 2. Floating Toolbar above Video: Segmented Control
        toolbar_frame = QFrame()
        toolbar_frame.setFixedHeight(44)
        toolbar_frame.setStyleSheet(
            f"background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 2px 6px;"
        )
        tool_bar = QHBoxLayout()
        tool_bar.setContentsMargins(4, 2, 4, 2)
        tool_bar.setSpacing(6)

        self.btn_tool_view = QPushButton("Normal View")
        self.btn_tool_view.setCheckable(True)
        self.btn_tool_view.setChecked(True)
        self.btn_tool_view.clicked.connect(lambda: self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW))

        self.btn_tool_stopline = QPushButton("Mark Up Stop Line")
        self.btn_tool_stopline.setCheckable(True)
        self.btn_tool_stopline.clicked.connect(lambda: self._set_canvas_tool(InteractiveVideoCanvas.MODE_MARKUP_LINE))

        self.btn_tool_signal = QPushButton("Point at Signal")
        self.btn_tool_signal.setCheckable(True)
        self.btn_tool_signal.clicked.connect(lambda: self._set_canvas_tool(InteractiveVideoCanvas.MODE_SIGNAL_POINTER))

        self.btn_tool_detection = QPushButton("Detection Area")
        self.btn_tool_detection.setCheckable(True)
        self.btn_tool_detection.clicked.connect(lambda: self._set_canvas_tool(InteractiveVideoCanvas.MODE_DETECTION_AREA))

        self.btn_tool_direction = QPushButton("Allowed Direction")
        self.btn_tool_direction.setCheckable(True)
        self.btn_tool_direction.clicked.connect(lambda: self._set_canvas_tool(InteractiveVideoCanvas.MODE_DIRECTION_ARROW))

        self.btn_clear_tools = QPushButton("Clear Markup")
        self.btn_clear_tools.setObjectName("btnGhostDanger")
        self.btn_clear_tools.clicked.connect(self._clear_canvas_markup)

        tool_bar.addWidget(self.btn_tool_view)
        tool_bar.addWidget(self.btn_tool_stopline)
        tool_bar.addWidget(self.btn_tool_signal)
        tool_bar.addWidget(self.btn_tool_detection)
        tool_bar.addWidget(self.btn_tool_direction)
        tool_bar.addStretch(1)
        tool_bar.addWidget(self.btn_clear_tools)

        toolbar_frame.setLayout(tool_bar)
        v_layout.addWidget(toolbar_frame)

        # 3. Hero Video Container
        self.canvas = InteractiveVideoCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v_layout.addWidget(self.canvas, 2)

        # 4. Custom Player Bar Below Video
        player_frame = QFrame()
        player_frame.setFixedHeight(42)
        player_frame.setStyleSheet(
            f"background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 2px 10px;"
        )
        player_layout = QHBoxLayout()
        player_layout.setContentsMargins(6, 2, 6, 2)
        player_layout.setSpacing(8)

        self.btn_step_prev = QPushButton("⏮")
        self.btn_step_prev.setObjectName("btnGhost")
        self.btn_step_prev.setFixedSize(30, 30)
        self.btn_step_prev.setToolTip("Previous Frame")
        self.btn_step_prev.clicked.connect(self.step_prev)

        self.btn_play_pause = QPushButton("⏸")
        self.btn_play_pause.setObjectName("btnGhost")
        self.btn_play_pause.setFixedSize(30, 30)
        self.btn_play_pause.setToolTip("Play / Pause")
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)

        self.btn_step_next = QPushButton("⏭")
        self.btn_step_next.setObjectName("btnGhost")
        self.btn_step_next.setFixedSize(30, 30)
        self.btn_step_next.setToolTip("Next Frame")
        self.btn_step_next.clicked.connect(self.step_next)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.sliderMoved.connect(self.seek_frame)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: 'JetBrains Mono', monospace; font-size: 11px; min-width: 90px;"
        )

        self.fps_label = QLabel("0.0 FPS")
        self.fps_label.setStyleSheet(
            f"color: {PRIMARY_CYAN}; font-family: 'JetBrains Mono', monospace; font-size: 11px; min-width: 55px;"
        )

        player_layout.addWidget(self.btn_step_prev)
        player_layout.addWidget(self.btn_play_pause)
        player_layout.addWidget(self.btn_step_next)
        player_layout.addWidget(self.progress_slider)
        player_layout.addWidget(self.time_label)
        player_layout.addWidget(self.fps_label)

        player_frame.setLayout(player_layout)
        v_layout.addWidget(player_frame)

        # 5. Bottom: Real-Time Violations Log Table (240px)
        table_container = QFrame()
        table_container.setFixedHeight(220)
        table_container.setStyleSheet(
            f"background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; padding: 6px;"
        )
        t_layout = QVBoxLayout()
        t_layout.setContentsMargins(6, 6, 6, 6)
        t_layout.setSpacing(6)

        log_header_layout = QHBoxLayout()
        log_title = QLabel("REAL-TIME VIOLATIONS LOG")
        log_title.setStyleSheet(f"font-weight: 700; color: {TEXT_PRIMARY}; font-size: 11px; letter-spacing: 0.08em;")

        self.violations_count_badge = QLabel("0 Violations")
        self.violations_count_badge.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 4px; padding: 2px 6px; color: {TEXT_MUTED}; font-size: 10px;"
        )

        log_header_layout.addWidget(log_title)
        log_header_layout.addWidget(self.violations_count_badge)
        log_header_layout.addStretch(1)

        self.btn_export_log = QPushButton("Export CSV Report")
        self.btn_export_log.setStyleSheet(
            f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 10px; font-size: 11px;"
        )
        self.btn_export_log.clicked.connect(self.export_csv_report)
        log_header_layout.addWidget(self.btn_export_log)
        t_layout.addLayout(log_header_layout)

        self.violation_table = QTableWidget(0, 6)
        self.violation_table.setHorizontalHeaderLabels(
            ["Time", "Frame", "Vehicle ID", "Violation Type", "Details", "Severity"]
        )
        self.violation_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.violation_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.violation_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.violation_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.violation_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.violation_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.violation_table.setAlternatingRowColors(True)
        self.violation_table.verticalHeader().setDefaultSectionSize(36)
        self.violation_table.itemSelectionChanged.connect(self._on_table_row_selected)
        t_layout.addWidget(self.violation_table)

        table_container.setLayout(t_layout)
        v_layout.addWidget(table_container)

        container.setLayout(v_layout)
        self._update_toolbar_styles(InteractiveVideoCanvas.MODE_VIEW)
        return container

    def _update_toolbar_styles(self, active_mode):
        active_style = f"background-color: rgba(34, 211, 238, 0.15); border: 1px solid {PRIMARY_CYAN}; color: {PRIMARY_CYAN}; font-weight: 600;"
        inactive_style = f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; color: {TEXT_SECONDARY};"

        self.btn_tool_view.setStyleSheet(active_style if active_mode == InteractiveVideoCanvas.MODE_VIEW else inactive_style)
        self.btn_tool_stopline.setStyleSheet(active_style if active_mode == InteractiveVideoCanvas.MODE_MARKUP_LINE else inactive_style)
        self.btn_tool_signal.setStyleSheet(active_style if active_mode == InteractiveVideoCanvas.MODE_SIGNAL_POINTER else inactive_style)
        self.btn_tool_detection.setStyleSheet(active_style if active_mode == InteractiveVideoCanvas.MODE_DETECTION_AREA else inactive_style)
        self.btn_tool_direction.setStyleSheet(active_style if active_mode == InteractiveVideoCanvas.MODE_DIRECTION_ARROW else inactive_style)

    # Tool and Markup Event Handlers
    def _set_canvas_tool(self, mode: int):
        self._update_toolbar_styles(mode)
        self.canvas.set_mode(mode)

    def _on_stop_line_drawn(self, points):
        """Called when user finishes drawing stop line with markup tool."""
        self.pipeline_cfg.rrl_config.stop_line = points
        self.pipeline.rrl.config.stop_line = points
        self.pipeline.annotator.rrl_config.stop_line = points
        self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW)
        print(f"[Markup Tool] Stop line set: {points[0]} -> {points[1]}")

    def _on_signal_pointer_set(self, points):
        """Called when user points at traffic signal with signal pointer tool."""
        self.pipeline_cfg.rrl_config.traffic_light_area = points
        self.pipeline.rrl.config.traffic_light_area = points
        self.pipeline.annotator.rrl_config.traffic_light_area = points
        self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW)
        print(f"[Signal Pointer] Traffic signal region set: {points}")

    def _on_detection_area_set(self, points):
        """Called when user draws vehicle detection ROI."""
        self.pipeline_cfg.vd_config.detection_area = points
        self.pipeline.vd.config.detection_area = points
        self.pipeline.annotator.vd_config.detection_area = points
        self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW)

    def _on_direction_arrow_set(self, points):
        """Called when user draws allowed traffic direction arrow."""
        self.pipeline_cfg.ww_config.allowed_direction = points
        self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW)

    def _clear_canvas_markup(self):
        """Resets stop line and pointer to default values and full-frame detection area."""
        self.pipeline_cfg.rrl_config.stop_line = [[0.1, 0.7], [0.9, 0.7]]
        self.pipeline_cfg.rrl_config.traffic_light_area = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]
        self.pipeline_cfg.vd_config.detection_area = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

        self.pipeline.rrl.config.stop_line = self.pipeline_cfg.rrl_config.stop_line
        self.pipeline.rrl.config.traffic_light_area = self.pipeline_cfg.rrl_config.traffic_light_area
        self.pipeline.vd.config.detection_area = self.pipeline_cfg.vd_config.detection_area

        self.pipeline.annotator.rrl_config.stop_line = self.pipeline_cfg.rrl_config.stop_line
        self.pipeline.annotator.rrl_config.traffic_light_area = self.pipeline_cfg.rrl_config.traffic_light_area
        self.pipeline.annotator.vd_config.detection_area = self.pipeline_cfg.vd_config.detection_area

        self.canvas.set_overlays(
            stop_line=self.pipeline_cfg.rrl_config.stop_line,
            traffic_light_area=self.pipeline_cfg.rrl_config.traffic_light_area,
            detection_area=self.pipeline_cfg.vd_config.detection_area,
        )
        self._set_canvas_tool(InteractiveVideoCanvas.MODE_VIEW)

    # Video Loading & Playback
    def load_video_dialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)",
            options=options,
        )
        if fileName:
            self._load_video_from_path(fileName)

    def _load_video_from_path(self, path: str):
        if not os.path.exists(path):
            return
        self.pipeline_cfg.video_path = path
        self.video_lineedit.setText(os.path.basename(path))

        if self.vid is not None:
            self.vid.release()

        self.vid = cv2.VideoCapture(path)
        if not self.vid.isOpened():
            print(f"Failed to open video: {path}")
            return

        self.frame_total = int(self.vid.get(cv2.CAP_PROP_FRAME_COUNT))
        self.progress_slider.setMaximum(max(0, self.frame_total - 1))
        self.current_frame_idx = 0

        # Read first frame and display
        ret, frame = self.vid.read()
        if ret and frame is not None:
            self.current_raw_frame = frame
            annotated = self.pipeline.update(frame, frame_idx=0, timestamp="00:00.0")
            self.canvas.set_frame(annotated)
            self._update_time_label()

    def ready_check(self):
        """Performs ready check on all 4 models/subsystems and updates UI."""
        self.pipeline.config = self.pipeline_cfg
        self.pipeline.reload_config()
        self.ready_status = self.pipeline.ready_check()

        # Update model card chips
        self.card_m_vd.set_status(self.pipeline.vd_ready_status)
        self.card_m_hv.set_status(self.pipeline.hv_ready_status)
        self.card_m_tr.set_status(self.pipeline.hv_ready_status)
        self.card_m_rrl.set_status(self.pipeline.rrl_ready_status)

        return self.ready_status

    def toggle_start(self):
        if not self.is_playing:
            self.start()
        else:
            self.pause()

    def start(self):
        if not self.ready_status:
            self.ready_check()

        if self.vid is None or not self.vid.isOpened():
            if self.pipeline_cfg.video_path:
                self._load_video_from_path(self.pipeline_cfg.video_path)

        if self.vid is None or not self.vid.isOpened():
            QMessageBox.warning(self, "No Video", "Please select a valid video file first.")
            return

        self.pipeline.video_recorder_init(self.pipeline_cfg.video_path)
        self.is_playing = True
        self.start_btn.setText("Pause")
        self.stop_btn.setEnabled(True)
        self.btn_play_pause.setText("⏸")
        self.status_dot.setStyleSheet(f"background-color: {SUCCESS_READY}; border-radius: 4px; border: none;")
        self.status_text.setText("DETECTING")
        self.timer.start(1000.0 / 30.0)

    def pause(self):
        self.timer.stop()
        self.is_playing = False
        self.start_btn.setText("Resume")
        self.btn_play_pause.setText("▶")
        self.status_dot.setStyleSheet(f"background-color: {WARNING}; border-radius: 4px; border: none;")
        self.status_text.setText("PAUSED")

    def toggle_play_pause(self):
        if self.is_playing:
            self.pause()
        else:
            self.start()

    def stop(self):
        self.timer.stop()
        self.is_playing = False
        self.start_btn.setText("Start Video")
        self.stop_btn.setEnabled(False)
        self.btn_play_pause.setText("▶")
        self.status_dot.setStyleSheet(f"background-color: {TEXT_MUTED}; border-radius: 4px; border: none;")
        self.status_text.setText("IDLE")

        try:
            out_path = self.pipeline.video_recorder_close()
            QMessageBox.information(self, "Finished", f"Processing complete!\nVideo saved to:\n{out_path}")
        except Exception:
            pass

    def update_frame(self):
        if self.vid is None or not self.vid.isOpened():
            self.stop()
            return

        t0 = time.time()
        ret, frame = self.vid.read()
        if not ret or frame is None:
            self.stop()
            return

        self.current_frame_idx = int(self.vid.get(cv2.CAP_PROP_POS_FRAMES))
        fps_in = self.vid.get(cv2.CAP_PROP_FPS) or 30.0
        sec = self.current_frame_idx / fps_in
        timestamp_str = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"

        self.current_raw_frame = frame

        # Process frame through full multi-task pipeline
        result_frame = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=timestamp_str)
        self.pipeline.video_recorder_update(result_frame)

        # Update canvas
        self.canvas.set_frame(result_frame)

        # Update metrics
        t_proc = time.time() - t0
        cur_fps = 1.0 / max(0.001, t_proc)
        fps_text = f"{cur_fps:.1f} FPS"
        self.fps_label.setText(fps_text)
        self.header_fps_badge.setText(fps_text)

        # Amber under 10 fps, red under 5
        if cur_fps < 5:
            self.header_fps_badge.setStyleSheet(f"background-color: {SURFACE_ELEVATED}; border: 1px solid {DANGER}; border-radius: 8px; padding: 6px 10px; color: {DANGER}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;")
        elif cur_fps < 10:
            self.header_fps_badge.setStyleSheet(f"background-color: {SURFACE_ELEVATED}; border: 1px solid {WARNING}; border-radius: 8px; padding: 6px 10px; color: {WARNING}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;")
        else:
            self.header_fps_badge.setStyleSheet(f"background-color: {SURFACE_ELEVATED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px; color: {PRIMARY_CYAN}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;")

        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(self.current_frame_idx)
        self.progress_slider.blockSignals(False)
        self._update_time_label()

        # Update signal indicator
        state = getattr(self.pipeline, "latest_signal_state", "green")
        self.signal_widget.set_state(state)

        # Process new violation events
        for ev in getattr(self.pipeline, "latest_events", []):
            vkey = (ev["vehicle_id"], ev["type"])
            if vkey not in self.seen_violations:
                self.seen_violations.add(vkey)
                self.recorded_events.append(ev)
                self._add_violation_row(ev, frame)

        # Update counters
        vd_cnt = len(getattr(self.pipeline, "latest_vd_result", []))
        self.counts["total_vehicles"] = max(self.counts["total_vehicles"], vd_cnt)
        self.card_total.set_count(self.counts["total_vehicles"])

        if self.current_frame_idx >= self.frame_total - 1:
            self.stop()

    def _add_violation_row(self, ev: dict, frame: np.ndarray):
        row = self.violation_table.rowCount()
        self.violation_table.insertRow(row)

        vtype = ev["type"]
        color = PRIMARY_CYAN
        if "Red" in vtype:
            self.counts["red_light"] += 1
            self.card_red_light.set_count(self.counts["red_light"])
            color = COLOR_RED_LIGHT
        elif "Helmet" in vtype:
            self.counts["no_helmet"] += 1
            self.card_no_helmet.set_count(self.counts["no_helmet"])
            color = COLOR_NO_HELMET
        elif "Triple" in vtype:
            self.counts["triple_riding"] += 1
            self.card_triple_riding.set_count(self.counts["triple_riding"])
            color = COLOR_TRIPLE_RIDING
        elif "Wrong" in vtype:
            self.counts["wrong_way"] += 1
            self.card_wrong_way.set_count(self.counts["wrong_way"])
            color = COLOR_WRONG_WAY

        self.violations_count_badge.setText(f"{len(self.recorded_events)} Violations")

        item_time = QTableWidgetItem(ev["timestamp"])
        item_frame = QTableWidgetItem(str(ev["frame"]))
        item_id = QTableWidgetItem(f"#{ev['vehicle_id']} ({ev['vehicle_type']})")
        item_type = QTableWidgetItem(ev["type"])
        item_details = QTableWidgetItem(ev["details"])
        item_sev = QTableWidgetItem(ev["severity"])

        # Styled pill text color
        item_type.setForeground(QColor(color))
        font_bold = QFont("Inter", 11, QFont.Bold)
        item_type.setFont(font_bold)

        # Severity chip color
        sev = str(ev["severity"]).upper()
        if "HIGH" in sev:
            item_sev.setForeground(QColor(DANGER))
        elif "MED" in sev:
            item_sev.setForeground(QColor(WARNING))
        else:
            item_sev.setForeground(QColor(COLOR_WRONG_WAY))
        item_sev.setFont(font_bold)

        self.violation_table.setItem(row, 0, item_time)
        self.violation_table.setItem(row, 1, item_frame)
        self.violation_table.setItem(row, 2, item_id)
        self.violation_table.setItem(row, 3, item_type)
        self.violation_table.setItem(row, 4, item_details)
        self.violation_table.setItem(row, 5, item_sev)

        self.violation_table.scrollToBottom()

    def _on_table_row_selected(self):
        selected_rows = self.violation_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self.recorded_events):
            if hasattr(self, "current_raw_frame") and self.current_raw_frame is not None:
                thumb = cv2.resize(self.current_raw_frame, (300, 160))
                thumb_rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                qimg = QImage(thumb_rgb.data, 300, 160, 300 * 3, QImage.Format_RGB888)
                self.snapshot_lbl.setPixmap(QPixmap.fromImage(qimg))

    def step_next(self):
        if self.vid and self.vid.isOpened():
            self.current_frame_idx += 1
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
            ret, frame = self.vid.read()
            if ret and frame is not None:
                self.current_raw_frame = frame
                fps_in = self.vid.get(cv2.CAP_PROP_FPS) or 30.0
                sec = self.current_frame_idx / fps_in
                ts = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"
                out = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=ts)
                self.canvas.set_frame(out)
                self.progress_slider.setValue(self.current_frame_idx)
                self._update_time_label()

    def step_prev(self):
        if self.vid and self.vid.isOpened():
            self.current_frame_idx = max(0, self.current_frame_idx - 1)
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
            ret, frame = self.vid.read()
            if ret and frame is not None:
                self.current_raw_frame = frame
                fps_in = self.vid.get(cv2.CAP_PROP_FPS) or 30.0
                sec = self.current_frame_idx / fps_in
                ts = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"
                out = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=ts)
                self.canvas.set_frame(out)
                self.progress_slider.setValue(self.current_frame_idx)
                self._update_time_label()

    def seek_frame(self, pos: int):
        if self.vid and self.vid.isOpened():
            self.current_frame_idx = pos
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = self.vid.read()
            if ret and frame is not None:
                self.current_raw_frame = frame
                fps_in = self.vid.get(cv2.CAP_PROP_FPS) or 30.0
                sec = self.current_frame_idx / fps_in
                ts = f"{int(sec // 60):02d}:{int(sec % 60):02d}.{int((sec % 1) * 10):01d}"
                out = self.pipeline.update(frame, frame_idx=self.current_frame_idx, timestamp=ts)
                self.canvas.set_frame(out)
                self._update_time_label()

    def _update_time_label(self):
        fps_in = (self.vid.get(cv2.CAP_PROP_FPS) if self.vid else 30.0) or 30.0
        cur_sec = self.current_frame_idx / fps_in
        tot_sec = self.frame_total / fps_in
        cur_str = f"{int(cur_sec // 60):02d}:{int(cur_sec % 60):02d}"
        tot_str = f"{int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}"
        self.time_label.setText(f"{cur_str} / {tot_str}")

    def export_csv_report(self):
        """Exports violation log table to CSV."""
        if not self.recorded_events:
            QMessageBox.information(self, "Export", "No violations recorded to export yet.")
            return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Violations CSV", "violations_report.csv", "CSV Files (*.csv)", options=options
        )
        if path:
            if not path.endswith(".csv"):
                path += ".csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Frame", "Vehicle ID", "Vehicle Type", "Violation Type", "Details", "Severity"])
                for ev in self.recorded_events:
                    writer.writerow([
                        ev["timestamp"],
                        ev["frame"],
                        ev["vehicle_id"],
                        ev["vehicle_type"],
                        ev["type"],
                        ev["details"],
                        ev["severity"],
                    ])
            QMessageBox.information(self, "Export Successful", f"Saved {len(self.recorded_events)} events to:\n{path}")

    # Sub-dialog configurations (with preloaded models)
    def load_vd_config(self):
        vdi = VehicleDetectionInterface(
            config=self.pipeline_cfg.vd_config, video_path=self.pipeline_cfg.video_path
        )
        vdi.exec_()
        if vdi.result() == 1:
            self.pipeline_cfg.vd_config = vdi.config
            self.ready_check()

    def load_rrld_config(self):
        rrli = RunningRedLightInterface(
            config=self.pipeline_cfg.rrl_config,
            config_vd=self.pipeline_cfg.vd_config,
            video_path=self.pipeline_cfg.video_path,
        )
        rrli.exec_()
        if rrli.result() == 1:
            self.pipeline_cfg.rrl_config = rrli.config
            self.ready_check()

    def load_hv_config(self):
        hvi = HelmetViolationInterface(
            config=self.pipeline_cfg.hv_config,
            config_vd=self.pipeline_cfg.vd_config,
            video_path=self.pipeline_cfg.video_path,
        )
        hvi.exec_()
        if hvi.result() == 1:
            self.pipeline_cfg.hv_config = hvi.config
            self.ready_check()

    def load_ww_config(self):
        wwi = WrongWayInterface(
            config=self.pipeline_cfg.ww_config,
            vd_config=self.pipeline_cfg.vd_config,
            video_path=self.pipeline_cfg.video_path,
        )
        wwi.exec_()
        if wwi.result() == 1:
            self.pipeline_cfg.ww_config = wwi.config
            self.ready_check()

    def load_config_dialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Config File", "", "Config File (*.json)", options=options
        )
        if path:
            self.pipeline_cfg.load_config(path)
            self._load_video_from_path(self.pipeline_cfg.video_path)
            self.ready_check()

    def save_config_dialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config File", "default_config.json", "Config File (*.json)", options=options
        )
        if path:
            if not path.endswith(".json"):
                path += ".json"
            self.pipeline_cfg.save_config(path)
            QMessageBox.information(self, "Saved", f"Configuration saved to:\n{path}")
