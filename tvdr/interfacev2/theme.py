"""Design tokens and global stylesheet for the TVDR Smart-City Command Center UI.

Color Palette:
- App Background: #0B0F17
- Surface (cards/panels): #111826
- Elevated surface (hover/inputs): #172033
- Border: #223049
- Primary Accent (cyan): #22D3EE (Hover: #67E8F9)
- Secondary Accent (indigo): #6366F1
- Text Primary: #E6EDF7
- Text Secondary: #8EA0BA
- Text Muted: #5B6B85
- Success / Ready: #22C55E
- Warning: #F59E0B
- Danger: #EF4444

Violation Colors:
- Red Light: #EF4444
- No Helmet: #F59E0B
- Triple Riding: #A855F7
- Wrong Way: #3B82F6
- Vehicles: #10B981

Signal Colors:
- Red: #EF4444
- Yellow: #FACC15
- Green: #22C55E
"""

# Color Constants
BG_APP = "#0B0F17"
SURFACE = "#111826"
SURFACE_ELEVATED = "#172033"
BORDER = "#223049"
PRIMARY_CYAN = "#22D3EE"
PRIMARY_CYAN_HOVER = "#67E8F9"
SECONDARY_INDIGO = "#6366F1"
TEXT_PRIMARY = "#E6EDF7"
TEXT_SECONDARY = "#8EA0BA"
TEXT_MUTED = "#5B6B85"
SUCCESS_READY = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"

# Violation Colors
COLOR_RED_LIGHT = "#EF4444"
COLOR_NO_HELMET = "#F59E0B"
COLOR_TRIPLE_RIDING = "#A855F7"
COLOR_WRONG_WAY = "#3B82F6"
COLOR_VEHICLES = "#10B981"

# Signal
SIGNAL_RED = "#EF4444"
SIGNAL_YELLOW = "#FACC15"
SIGNAL_GREEN = "#22C55E"
LETTERBOX_BG = "#05080D"

# Complete QSS Stylesheet
COMMAND_CENTER_QSS = f"""
/* Global Window */
QMainWindow {{
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
}}

QWidget {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", "SF Pro Text", Helvetica, Arial, sans-serif;
    color: {TEXT_PRIMARY};
}}

/* Tooltips */
QToolTip {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* Custom Scrollbars */
QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {BORDER};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* LineEdit / Inputs */
QLineEdit {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    selection-background-color: {PRIMARY_CYAN};
    selection-color: {BG_APP};
}}
QLineEdit:focus {{
    border: 1px solid {PRIMARY_CYAN};
}}

/* Buttons */
QPushButton {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {PRIMARY_CYAN};
    color: {PRIMARY_CYAN_HOVER};
}}
QPushButton:pressed {{
    background-color: {BORDER};
}}
QPushButton:disabled {{
    opacity: 0.4;
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

/* Primary Button (Cyan Gradient) */
QPushButton#btnPrimary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY_CYAN}, stop:1 #0EA5E9);
    color: {BG_APP};
    border: none;
    border-radius: 10px;
    font-weight: 600;
    min-height: 36px;
    padding: 6px 18px;
}}
QPushButton#btnPrimary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY_CYAN_HOVER}, stop:1 {PRIMARY_CYAN});
}}
QPushButton#btnPrimary:pressed {{
    background: #0EA5E9;
}}

/* Danger Outline Button */
QPushButton#btnDanger {{
    background-color: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
    border-radius: 8px;
    font-weight: 600;
    min-height: 34px;
}}
QPushButton#btnDanger:hover {{
    background-color: {DANGER};
    color: #FFFFFF;
}}

/* Ghost / Subtle Tool Button */
QPushButton#btnGhost {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {TEXT_SECONDARY};
    border-radius: 6px;
    padding: 4px 8px;
}}
QPushButton#btnGhost:hover {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border-color: {BORDER};
}}

/* Danger Ghost Button (Clear Markup) */
QPushButton#btnGhostDanger {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {TEXT_MUTED};
    border-radius: 6px;
    padding: 4px 10px;
}}
QPushButton#btnGhostDanger:hover {{
    background-color: rgba(239, 68, 68, 0.15);
    color: {DANGER};
    border-color: {DANGER};
}}

/* Slider */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY_CYAN};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {PRIMARY_CYAN};
    border: 2px solid #FFFFFF;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {PRIMARY_CYAN_HOVER};
    width: 16px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 8px;
}}

/* Table */
QTableWidget {{
    background-color: {SURFACE};
    alternate-background-color: #0E1522;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: rgba(34, 211, 238, 0.12);
    selection-color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {BORDER};
}}
QTableWidget::item:selected {{
    background-color: rgba(34, 211, 238, 0.15);
    border-left: 3px solid {PRIMARY_CYAN};
}}
QHeaderView::section {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
}}

/* Group Boxes / Panels */
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 18px;
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_MUTED};
    padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 4px;
    color: {TEXT_MUTED};
    letter-spacing: 0.06em;
}}
"""

