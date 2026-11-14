import sys
import os

from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QPalette, QColor
from .main_layout import MainLayout
from .theme import COMMAND_CENTER_QSS, BG_APP, TEXT_PRIMARY, SURFACE, BORDER


class MainWindows:
    def __init__(self, run_loop: bool = True):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        QApplication.setStyle("Fusion")
        self.app.setStyleSheet(COMMAND_CENTER_QSS)

        self.widget = QMainWindow()
        self.widget.setWindowTitle("Traffic Violation Detection — Smart-City Command Center")
        self.widget.setMinimumSize(1280, 720)
        self.widget.resize(1360, 850)

        # Main Layout Widget
        self.main_layout_widget = MainLayout()
        self.widget.setCentralWidget(self.main_layout_widget)
        self.widget.show()

        if run_loop:
            sys.exit(self.app.exec_())


def main():
    MainWindows()


if __name__ == "__main__":
    main()
