# modules/login_window.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from utils.database import login, start_shift, log_activity
from utils.styles import COLORS


class LoginWindow(QWidget):
    login_success = pyqtSignal(dict)  # emits user info dict

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ParkEase — Login")
        self.setFixedSize(420, 650)
        self.setStyleSheet(f"background-color: {COLORS['bg']}; color: {COLORS['text']};")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 60, 48, 60)
        root.setSpacing(0)

        # Logo / Brand
        brand = QLabel("P")
        brand.setFixedSize(64, 64)
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet(f"""
            background-color: {COLORS['primary']};
            color: white; font-size: 28px; font-weight: 700;
            border-radius: 16px;
        """)
        root.addWidget(brand, alignment=Qt.AlignCenter)
        root.addSpacing(20)

        title = QLabel("ParkEase")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 24px; font-weight: 700;")
        root.addWidget(title)

        sub = QLabel("Parking Management System")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        root.addWidget(sub)
        root.addSpacing(40)

        # Card
        # Card
        card = QFrame()
        card.setObjectName("loginCard") # <-- Add this object name
        
        # Add #loginCard to the CSS so it doesn't bleed to the text labels
        card.setStyleSheet(f"""
            QFrame#loginCard {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 28, 24, 28)
        card_layout.setSpacing(16)

        lbl_user = QLabel("Username")
        lbl_user.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(lbl_user)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setStyleSheet(f"""
            background-color: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 8px;
            padding: 10px 14px; font-size: 13px;
        """)
        card_layout.addWidget(self.username_input)

        lbl_pass = QLabel("Password")
        lbl_pass.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(lbl_pass)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(self.username_input.styleSheet())
        self.password_input.returnPressed.connect(self._do_login)
        card_layout.addWidget(self.password_input)

        card_layout.addSpacing(8)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(44)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']}; color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {COLORS['primary_h']}; }}
            QPushButton:pressed {{ background-color: #1D4ED8; }}
        """)
        self.login_btn.clicked.connect(self._do_login)
        card_layout.addWidget(self.login_btn)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        root.addWidget(card)
        root.addStretch()

    def _do_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        self.login_btn.setText("Signing in…")
        self.login_btn.setEnabled(False)
        self.repaint()

        try:
            result = login(username, password)
        except Exception as e:
            self._show_error(f"Database error: {e}")
            self.login_btn.setText("Sign In")
            self.login_btn.setEnabled(True)
            return

        self.login_btn.setText("Sign In")
        self.login_btn.setEnabled(True)

        if result['success']:
            self.error_label.hide()
            if result['role'] == 'staff':
                try:
                    shift_id = start_shift(result['user_id'])
                    result['shift_id'] = shift_id
                    log_activity('staff', result['user_id'], result['username'],
                                 'Login', f"{result['full_name']} started shift")
                except Exception:
                    pass
            else:
                log_activity('admin', result['user_id'], result['username'],
                             'Login', f"Admin {result['full_name']} logged in")
            self.login_success.emit(result)
        else:
            self._show_error(result.get('message', 'Login failed.'))

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()
