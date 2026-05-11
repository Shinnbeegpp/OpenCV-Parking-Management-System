# main.py  —  ParkEase Parking Management System
# Run: python main.py

import sys
import os

# Force torch to load before PyQt5 to avoid DLL conflict on Windows
try:
    import torch
    from ultralytics import YOLO
except Exception:
    pass

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from utils.styles import MAIN_STYLE
from modules.login_window import LoginWindow
from modules.staff_window import StaffWindow
from modules.admin_window import AdminWindow


class ParkEaseApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ParkEase")
        self.app.setOrganizationName("ParkEase Systems")
        self.app.setStyleSheet(MAIN_STYLE)

        # Default font
        font = QFont("Segoe UI", 10)
        self.app.setFont(font)

        self._current_window = None
        self._show_login()

    def _show_login(self):
        self._close_current()
        self._login_win = LoginWindow()
        self._login_win.login_success.connect(self._on_login)
        self._login_win.show()

    def _on_login(self, user_info: dict):
        self._login_win.hide()
        if user_info['role'] == 'admin':
            win = AdminWindow(user_info, on_logout=self._show_login)
        else:
            win = StaffWindow(user_info, on_logout=self._show_login)
        self._current_window = win
        win.show()

    def _close_current(self):
        if self._current_window:
            self._current_window.close()
            self._current_window = None

    def run(self):
        return self.app.exec_()


if __name__ == "__main__":
    # Quick DB connection check before launch
    try:
        from utils.database import get_connection
        conn = get_connection()
        conn.close()
    except Exception as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, "Database Error",
            f"Cannot connect to MySQL database.\n\n"
            f"Error: {e}\n\n"
            f"Please:\n"
            f"1. Make sure MySQL is running\n"
            f"2. Edit utils/database.py and set your DB_CONFIG (host, user, password)\n"
            f"3. Run schema.sql in MySQL Workbench\n"
            f"4. Restart the application"
        )
        sys.exit(1)

    park = ParkEaseApp()
    sys.exit(park.run())
