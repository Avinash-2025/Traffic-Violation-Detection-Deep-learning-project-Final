import cv2
import numpy as np

from PySide2.QtWidgets import QLabel
from PySide2.QtCore import Qt, QPoint, Signal, QRect
from PySide2.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap, QImage, QCursor

from .theme import (
    BG_APP,
    SURFACE,
    SURFACE_ELEVATED,
    BORDER,
    PRIMARY_CYAN,
    PRIMARY_CYAN_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    DANGER,
    WARNING,
    LETTERBOX_BG,
    COLOR_RED_LIGHT,
    COLOR_WRONG_WAY,
)


class InteractiveVideoCanvas(QLabel):
    # Signals emitted when interactive tools finish drawing or modifying geometry
    stop_line_drawn = Signal(list)       # [[x1, y1], [x2, y2]] in normalized [0, 1]
    signal_pointer_set = Signal(list)    # [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    detection_area_set = Signal(list)    # list of [x, y] points
    direction_arrow_set = Signal(list)   # [[x1, y1], [x2, y2]]

    MODE_VIEW = 0
    MODE_MARKUP_LINE = 1
    MODE_SIGNAL_POINTER = 2
    MODE_DETECTION_AREA = 3
    MODE_DIRECTION_ARROW = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setMinimumSize(640, 360)

        self.current_mode = self.MODE_VIEW
        self.cv_img = None
        self.ori_w = 1280
        self.ori_h = 720

        # Drawing state
        self.markup_points = []       # temporary QPoints in widget coords
        self.mouse_pos = QPoint()     # current hover pos
        self.is_dragging = False
        self.drag_start = QPoint()

        # Handle interaction state (dragging existing handles)
        self.dragging_handle_idx = -1
        self.hover_handle_idx = -1

        # Configured overlays (normalized [0, 1])
        self.overlay_stop_line = None
        self.overlay_traffic_light = None
        self.overlay_detection_area = None
        self.overlay_direction_arrow = None
        self.current_signal_state = "green"

        self.setStyleSheet(
            f"background-color: {LETTERBOX_BG}; border: 1px solid {BORDER}; border-radius: 12px;"
        )

    def set_mode(self, mode: int):
        self.current_mode = mode
        self.markup_points = []
        self.is_dragging = False
        self.dragging_handle_idx = -1

        if mode == self.MODE_VIEW:
            self.setCursor(QCursor(Qt.ArrowCursor))
        else:
            self.setCursor(QCursor(Qt.CrossCursor))

        self.update()

    def set_frame(self, cv_img):
        if cv_img is None or not hasattr(cv_img, "shape") or cv_img.size == 0:
            return
        self.cv_img = cv_img
        self.ori_h, self.ori_w = cv_img.shape[:2]

        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qimage = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.pixmap_data = QPixmap.fromImage(qimage)
        self.update()

    def set_overlays(self, stop_line=None, traffic_light_area=None, detection_area=None, direction_arrow=None, signal_state=None):
        if stop_line is not None:
            self.overlay_stop_line = stop_line
        if traffic_light_area is not None:
            self.overlay_traffic_light = traffic_light_area
        if detection_area is not None:
            self.overlay_detection_area = detection_area
        if direction_arrow is not None:
            self.overlay_direction_arrow = direction_arrow
        if signal_state is not None:
            self.current_signal_state = signal_state
        self.update()

    def get_render_rect(self):
        """Calculates the sub-rectangle within the widget where the video frame is drawn with aspect ratio maintained."""
        if not hasattr(self, "pixmap_data") or self.pixmap_data.isNull():
            return QRect(0, 0, self.width(), self.height())

        pw = self.pixmap_data.width()
        ph = self.pixmap_data.height()
        ww = self.width()
        wh = self.height()

        scaled = self.pixmap_data.scaled(ww, wh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        sw = scaled.width()
        sh = scaled.height()
        sx = (ww - sw) // 2
        sy = (wh - sh) // 2
        return QRect(sx, sy, sw, sh)

    def widget_to_normalized(self, pt: QPoint):
        """Converts a widget QPoint to normalized [0, 1] video frame coordinates."""
        r = self.get_render_rect()
        if r.width() == 0 or r.height() == 0:
            return 0.0, 0.0

        nx = (pt.x() - r.x()) / float(r.width())
        ny = (pt.y() - r.y()) / float(r.height())
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    def normalized_to_widget(self, nx: float, ny: float):
        """Converts normalized [0, 1] video frame coordinates to widget QPoint."""
        r = self.get_render_rect()
        wx = int(r.x() + nx * r.width())
        wy = int(r.y() + ny * r.height())
        return QPoint(wx, wy)

    # Mouse Events
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            r = self.get_render_rect()
            if not r.contains(event.pos()):
                return

            if self.current_mode == self.MODE_MARKUP_LINE:
                self.markup_points.append(event.pos())
                if len(self.markup_points) >= 2:
                    p1_norm = self.widget_to_normalized(self.markup_points[0])
                    p2_norm = self.widget_to_normalized(self.markup_points[1])
                    result = [
                        [round(p1_norm[0], 4), round(p1_norm[1], 4)],
                        [round(p2_norm[0], 4), round(p2_norm[1], 4)],
                    ]
                    self.overlay_stop_line = result
                    self.stop_line_drawn.emit(result)
                    self.markup_points = []
                    self.set_mode(self.MODE_VIEW)
                self.update()

            elif self.current_mode == self.MODE_SIGNAL_POINTER:
                self.is_dragging = True
                self.drag_start = event.pos()
                self.markup_points = [event.pos()]
                self.update()

            elif self.current_mode == self.MODE_DETECTION_AREA:
                self.markup_points.append(event.pos())
                self.update()

            elif self.current_mode == self.MODE_DIRECTION_ARROW:
                self.is_dragging = True
                self.drag_start = event.pos()
                self.markup_points = [event.pos()]
                self.update()

        elif event.button() == Qt.RightButton:
            # Right click finishes polygon or cancels current action
            if self.current_mode == self.MODE_DETECTION_AREA and len(self.markup_points) >= 3:
                norm_pts = []
                for pt in self.markup_points:
                    nx, ny = self.widget_to_normalized(pt)
                    norm_pts.append([round(nx, 4), round(ny, 4)])
                self.overlay_detection_area = norm_pts
                self.detection_area_set.emit(norm_pts)
                self.markup_points = []
                self.set_mode(self.MODE_VIEW)
            else:
                self.markup_points = []
                self.set_mode(self.MODE_VIEW)
            self.update()

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.pos()
        if self.current_mode != self.MODE_VIEW:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.current_mode == self.MODE_SIGNAL_POINTER and self.is_dragging:
                self.is_dragging = False
                p1 = self.drag_start
                p2 = event.pos()

                dist = (p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2
                if dist < 36:
                    # Single click: create clean compact region around crosshair
                    nx, ny = self.widget_to_normalized(p1)
                    hw, hh = 0.035, 0.065
                    box = [
                        [round(max(0.0, nx - hw), 4), round(max(0.0, ny - hh), 4)],
                        [round(min(1.0, nx + hw), 4), round(max(0.0, ny - hh), 4)],
                        [round(min(1.0, nx + hw), 4), round(min(1.0, ny + hh), 4)],
                        [round(max(0.0, nx - hw), 4), round(min(1.0, ny + hh), 4)],
                    ]
                else:
                    x1, y1 = self.widget_to_normalized(QPoint(min(p1.x(), p2.x()), min(p1.y(), p2.y())))
                    x2, y2 = self.widget_to_normalized(QPoint(max(p1.x(), p2.x()), max(p1.y(), p2.y())))
                    box = [
                        [round(x1, 4), round(y1, 4)],
                        [round(x2, 4), round(y1, 4)],
                        [round(x2, 4), round(y2, 4)],
                        [round(x1, 4), round(y2, 4)],
                    ]

                self.overlay_traffic_light = box
                self.signal_pointer_set.emit(box)
                self.markup_points = []
                self.set_mode(self.MODE_VIEW)
                self.update()

            elif self.current_mode == self.MODE_DIRECTION_ARROW and self.is_dragging:
                self.is_dragging = False
                p1 = self.drag_start
                p2 = event.pos()
                p1_norm = self.widget_to_normalized(p1)
                p2_norm = self.widget_to_normalized(p2)
                arrow = [
                    [round(p1_norm[0], 4), round(p1_norm[1], 4)],
                    [round(p2_norm[0], 4), round(p2_norm[1], 4)],
                ]
                self.overlay_direction_arrow = arrow
                self.direction_arrow_set.emit(arrow)
                self.markup_points = []
                self.set_mode(self.MODE_VIEW)
                self.update()

    def mouseDoubleClickEvent(self, event):
        # Double-click closes polygon in detection area tool
        if self.current_mode == self.MODE_DETECTION_AREA and len(self.markup_points) >= 3:
            norm_pts = []
            for pt in self.markup_points:
                nx, ny = self.widget_to_normalized(pt)
                norm_pts.append([round(nx, 4), round(ny, 4)])
            self.overlay_detection_area = norm_pts
            self.detection_area_set.emit(norm_pts)
            self.markup_points = []
            self.set_mode(self.MODE_VIEW)
            self.update()

    # Painting
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.get_render_rect()

        # 1. Fill letterbox background in #05080D
        painter.fillRect(self.rect(), QColor(LETTERBOX_BG))

        # 2. Draw video frame scaled
        if hasattr(self, "pixmap_data") and not self.pixmap_data.isNull():
            painter.drawPixmap(r, self.pixmap_data)
        else:
            painter.setPen(QColor(TEXT_MUTED))
            font = QFont("Inter", 12)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "No Video Stream Available\nClick 'Browse Video' in the left sidebar to load media",
            )

        # 3. Draw active tool overlays
        if self.current_mode == self.MODE_MARKUP_LINE:
            self._draw_banner(
                painter,
                "STOP LINE TOOL: Click start point on road, then click end point across lane",
                QColor(COLOR_RED_LIGHT),
            )
            if len(self.markup_points) == 1:
                p1 = self.markup_points[0]
                p2 = self.mouse_pos
                # Glowing dashed line
                painter.setPen(QPen(QColor(COLOR_RED_LIGHT), 3, Qt.DashLine))
                painter.drawLine(p1, p2)
                # Outer glow
                painter.setPen(QPen(QColor(239, 68, 68, 80), 7, Qt.SolidLine))
                painter.drawLine(p1, p2)
                # Start anchor handle
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.setPen(QPen(QColor(COLOR_RED_LIGHT), 2))
                painter.drawEllipse(p1, 6, 6)

        elif self.current_mode == self.MODE_SIGNAL_POINTER:
            self._draw_banner(
                painter,
                "SIGNAL POINTER: Click to center crosshair or drag a box around the traffic lamp",
                QColor(PRIMARY_CYAN),
            )
            if self.is_dragging:
                rect = QRect(self.drag_start, self.mouse_pos).normalized()
                painter.setPen(QPen(QColor(PRIMARY_CYAN), 2, Qt.DashLine))
                painter.setBrush(QBrush(QColor(34, 211, 238, 40)))
                painter.drawRoundedRect(rect, 4, 4)
            else:
                # Target crosshair at cursor
                painter.setPen(QPen(QColor(PRIMARY_CYAN), 2))
                painter.drawLine(self.mouse_pos.x() - 14, self.mouse_pos.y(), self.mouse_pos.x() + 14, self.mouse_pos.y())
                painter.drawLine(self.mouse_pos.x(), self.mouse_pos.y() - 14, self.mouse_pos.x(), self.mouse_pos.y() + 14)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.mouse_pos, 8, 8)

        elif self.current_mode == self.MODE_DETECTION_AREA:
            self._draw_banner(
                painter,
                f"DETECTION AREA: Click to place vertices ({len(self.markup_points)}). Double-click or Right-click to close.",
                QColor(PRIMARY_CYAN),
            )
            if len(self.markup_points) > 0:
                painter.setPen(QPen(QColor(PRIMARY_CYAN), 2, Qt.DashLine))
                for i in range(len(self.markup_points) - 1):
                    painter.drawLine(self.markup_points[i], self.markup_points[i + 1])
                painter.drawLine(self.markup_points[-1], self.mouse_pos)

                for pt in self.markup_points:
                    painter.setBrush(QBrush(QColor(PRIMARY_CYAN)))
                    painter.setPen(QPen(QColor("#FFFFFF"), 1))
                    painter.drawEllipse(pt, 5, 5)

        elif self.current_mode == self.MODE_DIRECTION_ARROW:
            self._draw_banner(
                painter,
                "ALLOWED DIRECTION: Drag arrow in allowed traffic flow direction",
                QColor(COLOR_WRONG_WAY),
            )
            if self.is_dragging:
                p1 = self.drag_start
                p2 = self.mouse_pos
                painter.setPen(QPen(QColor(COLOR_WRONG_WAY), 3))
                painter.drawLine(p1, p2)
                # Draw arrowhead
                angle = np.arctan2(p2.y() - p1.y(), p2.x() - p1.x())
                arrow_sz = 14
                p_left = QPoint(
                    int(p2.x() - arrow_sz * np.cos(angle - np.pi / 6)),
                    int(p2.y() - arrow_sz * np.sin(angle - np.pi / 6)),
                )
                p_right = QPoint(
                    int(p2.x() - arrow_sz * np.cos(angle + np.pi / 6)),
                    int(p2.y() - arrow_sz * np.sin(angle + np.pi / 6)),
                )
                painter.setBrush(QBrush(QColor(COLOR_WRONG_WAY)))
                painter.drawPolygon([p2, p_left, p_right])

        painter.end()

    def _draw_banner(self, painter, text, accent_color):
        painter.save()
        font = QFont("Inter", 11, QFont.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) if hasattr(fm, "horizontalAdvance") else fm.width(text)
        th = fm.height()

        padding = 10
        bx = 16
        by = 16
        bw = tw + padding * 2 + 12
        bh = th + padding * 2

        # Glassmorphism container
        painter.setBrush(QBrush(QColor(17, 24, 38, 230)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(bx, by, bw, bh, 8, 8)

        # Left accent pill
        painter.setBrush(QBrush(accent_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bx + 4, by + 6, 4, bh - 12, 2, 2)

        # Text
        painter.setPen(QColor(TEXT_PRIMARY))
        painter.drawText(bx + padding + 10, by + padding + th - 4, text)
        painter.restore()
