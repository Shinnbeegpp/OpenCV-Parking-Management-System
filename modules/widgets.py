# modules/widgets.py
# Reusable UI components

from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                              QPushButton, QFrame, QSizePolicy, QTableWidget,
                              QTableWidgetItem, QHeaderView, QLineEdit,
                              QAbstractItemView, QDialog, QFormLayout,
                              QComboBox, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor
from utils.styles import COLORS


# ─── STAT CARD ────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, title, value, subtitle="", accent=COLORS['primary'], parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(110)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)

        # Accent bar
        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"background-color: {accent}; border-radius: 2px;")
        lay.addWidget(bar)
        lay.addSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        lay.addWidget(lbl_title)

        self.lbl_value = QLabel(str(value))
        self.lbl_value.setStyleSheet(f"color: {COLORS['text']}; font-size: 26px; font-weight: 700;")
        lay.addWidget(self.lbl_value)

        if subtitle:
            self.lbl_sub = QLabel(subtitle)
            self.lbl_sub.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
            lay.addWidget(self.lbl_sub)

    def set_value(self, value):
        self.lbl_value.setText(str(value))


# ─── SECTION LABEL ────────────────────────────────────────────────────────────

class SectionLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            color: {COLORS['text_muted']}; font-size: 11px;
            font-weight: 700; letter-spacing: 1px;
            padding-bottom: 6px;
            border-bottom: 1px solid {COLORS['border']};
        """)


# ─── SEARCHABLE TABLE ─────────────────────────────────────────────────────────

class SearchableTable(QWidget):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self._all_data = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Search bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search…")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet(f"""
            background-color: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 8px;
            padding: 0 12px; font-size: 13px;
        """)
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input)
        search_row.addStretch()
        lay.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_card']};
                alternate-background-color: {COLORS['bg_input']};
                color: {COLORS['text']}; border: 1px solid {COLORS['border']};
                border-radius: 10px; gridline-color: transparent;
                font-size: 12px; outline: none;
            }}
            QTableWidget::item {{ padding: 10px 12px; border: none; }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary']}; color: white;
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg']}; color: {COLORS['text_muted']};
                font-size: 11px; font-weight: 600; padding: 8px 12px;
                border: none; border-bottom: 1px solid {COLORS['border']};
                text-transform: uppercase; letter-spacing: 0.5px;
            }}
        """)
        lay.addWidget(self.table)

    def load_data(self, rows):
        """rows: list of lists/tuples matching columns count."""
        self._all_data = rows
        self._render(rows)

    def _render(self, rows):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "—")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        self.table.resizeRowsToContents()

    def _filter(self, text):
        text = text.lower()
        if not text:
            self._render(self._all_data)
            return
        filtered = [row for row in self._all_data
                    if any(text in str(v).lower() for v in row)]
        self._render(filtered)

    def set_cell_color(self, row, col, color):
        item = self.table.item(row, col)
        if item:
            item.setForeground(QColor(color))


# ─── SIDE NAV BAR ─────────────────────────────────────────────────────────────

class SideNav(QWidget):
    page_changed = pyqtSignal(int)

    def __init__(self, items, user_info, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_card']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        self._buttons = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 24, 12, 24)
        lay.setSpacing(4)

        # Brand
        brand_row = QHBoxLayout()
        brand_icon = QLabel("P")
        brand_icon.setFixedSize(34, 34)
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setStyleSheet(f"""
            background-color: {COLORS['primary']}; color: white;
            font-size: 16px; font-weight: 700; border-radius: 8px;
        """)
        brand_row.addWidget(brand_icon)
        brand_lbl = QLabel("ParkEase")
        brand_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 15px; font-weight: 700; background: transparent; border: none;")
        brand_row.addWidget(brand_lbl)
        brand_row.addStretch()
        lay.addLayout(brand_row)
        lay.addSpacing(28)

        # Role badge
        role = user_info.get('role', '').upper()
        role_lbl = QLabel(role)
        role_lbl.setStyleSheet(f"""
            background-color: {COLORS['primary']}20;
            color: {COLORS['primary']}; font-size: 10px; font-weight: 700;
            padding: 3px 8px; border-radius: 4px; border: none;
            letter-spacing: 0.5px;
        """)
        lay.addWidget(role_lbl)
        lay.addSpacing(4)

        name_lbl = QLabel(user_info.get('full_name', ''))
        name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        uname_lbl = QLabel(f"@{user_info.get('username', '')}")
        uname_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(uname_lbl)

        lay.addSpacing(20)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background-color: {COLORS['border']}; border: none; max-height: 1px;")
        lay.addWidget(div)
        lay.addSpacing(12)

        # Nav items
        for i, (icon, label) in enumerate(items):
            btn = QPushButton(f"  {icon}  {label}")
            btn.setFixedHeight(42)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda _, idx=i: self._select(idx))
            lay.addWidget(btn)
            self._buttons.append(btn)

        lay.addStretch()

    def _btn_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white; border: none; border-radius: 8px;
                    padding: 0 14px; text-align: left; font-size: 13px; font-weight: 600;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']}; border: none; border-radius: 8px;
                padding: 0 14px; text-align: left; font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']}; color: {COLORS['text']};
            }}
        """

    def _select(self, idx):
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(self._btn_style(i == idx))
        self.page_changed.emit(idx)

    def select(self, idx):
        self._select(idx)


# ─── MANUAL INPUT DIALOG ──────────────────────────────────────────────────────

class ManualInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Vehicle Entry")
        self.setFixedSize(400, 280)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}
            QLabel {{ color: {COLORS['text']}; }}
        """)
        self.result_data = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        title = QLabel("⚠  OCR Failed — Manual Entry Required")
        title.setStyleSheet(f"color: {COLORS['warning']}; font-size: 14px; font-weight: 700;")
        lay.addWidget(title)

        sub = QLabel("The system could not read the plate number.\nPlease enter the details manually.")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        lay.addWidget(sub)

        form = QFormLayout()
        form.setSpacing(10)

        self.plate_input = QLineEdit()
        self.plate_input.setPlaceholderText("e.g. ABC1234")
        self.plate_input.setStyleSheet(f"""
            background: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 8px 12px;
        """)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Car", "Motorcycle", "Bus", "Truck"])
        self.type_combo.setStyleSheet(f"""
            background: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 6px 10px;
        """)

        form.addRow(QLabel("Plate Number:"), self.plate_input)
        form.addRow(QLabel("Vehicle Type:"), self.type_combo)
        lay.addLayout(form)

        btns = QHBoxLayout()
        skip_btn = QPushButton("Skip (Log as Unknown)")
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                padding: 8px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        skip_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("Confirm Entry")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']}; color: white;
                border: none; border-radius: 7px; padding: 8px 18px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #059669; }}
        """)
        confirm_btn.clicked.connect(self._confirm)

        btns.addWidget(skip_btn)
        btns.addStretch()
        btns.addWidget(confirm_btn)
        lay.addLayout(btns)

    def _confirm(self):
        plate = self.plate_input.text().strip().upper()
        if not plate:
            self.plate_input.setStyleSheet(self.plate_input.styleSheet().replace(
                COLORS['border'], COLORS['danger']))
            return
        self.result_data = {
            'plate_number': plate,
            'vehicle_type': self.type_combo.currentText()
        }
        self.accept()


# ─── EXIT CONFIRMATION DIALOG ─────────────────────────────────────────────────

class ExitConfirmDialog(QDialog):
    def __init__(self, txn_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vehicle Exit — Confirm Charge")
        self.setFixedSize(440, 360)
        self.confirmed = False
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}")
        self._build(txn_data)

    def _build(self, d):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        title = QLabel("Vehicle Exit Details")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 17px; font-weight: 700;")
        lay.addWidget(title)

        card = QFrame()
        card.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 10px;
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)

        def row(label, val, big=False):
            r = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
            val_lbl = QLabel(str(val))
            sz = "16px" if big else "13px"
            fw = "700" if big else "500"
            col = COLORS['success'] if big else COLORS['text']
            val_lbl.setStyleSheet(f"color: {col}; font-size: {sz}; font-weight: {fw};")
            r.addWidget(lbl)
            r.addStretch()
            r.addWidget(val_lbl)
            cl.addLayout(r)

        row("Plate Number",  d.get('plate_number', '—'))
        row("Vehicle Type",  d.get('vehicle_type', '—'))
        row("Time In",       d.get('time_in', '—'))
        row("Time Out",      d.get('time_out', '—'))

        mins = d.get('duration_minutes', 0)
        h, m = divmod(mins, 60)
        row("Duration",      f"{h}h {m}m")

        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background: {COLORS['border']}; max-height: 1px; border: none;")
        cl.addWidget(div)

        row("Total Charge",  f"₱{d.get('total_charge', 0):.2f}", big=True)
        lay.addWidget(card)

        lay.addStretch()
        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 9px 18px;
            }}
        """)
        cancel.clicked.connect(self.reject)

        confirm = QPushButton("Confirm & Log Exit  ₱{:.2f}".format(d.get('total_charge', 0)))
        confirm.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']}; color: white; border: none;
                border-radius: 7px; padding: 9px 18px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['primary_h']}; }}
        """)
        confirm.clicked.connect(self._confirm)
        btns.addWidget(cancel)
        btns.addStretch()
        btns.addWidget(confirm)
        lay.addLayout(btns)

    def _confirm(self):
        self.confirmed = True
        self.accept()


# ─── BLIND DROP DIALOG ────────────────────────────────────────────────────────

class BlindDropDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("End of Shift — Cash Declaration")
        self.setFixedSize(400, 300)
        self.amount = None
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)

        title = QLabel("Cash Drop Declaration")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(title)

        sub = QLabel("Count your cash drawer and enter the total amount below.\nDo not reference any screen totals.")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; line-height: 1.5;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lbl = QLabel("Total Cash Collected (₱)")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 600;")
        lay.addWidget(lbl)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setFixedHeight(48)
        self.amount_input.setStyleSheet(f"""
            background: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 9px;
            padding: 0 16px; font-size: 20px; font-weight: 700;
        """)
        lay.addWidget(self.amount_input)

        lay.addStretch()
        btns = QHBoxLayout()
        submit = QPushButton("Submit & Logout")
        submit.setFixedHeight(44)
        submit.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']}; color: white;
                border: none; border-radius: 8px; font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['primary_h']}; }}
        """)
        submit.clicked.connect(self._submit)
        btns.addWidget(submit)
        lay.addLayout(btns)

    def _submit(self):
        try:
            self.amount = float(self.amount_input.text().replace(',', ''))
            self.accept()
        except ValueError:
            self.amount_input.setStyleSheet(self.amount_input.styleSheet() +
                                            f"border-color: {COLORS['danger']};")
