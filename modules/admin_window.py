# modules/admin_window.py
import sys
import os
import traceback

def exception_hook(exctype, value, tb):
    with open('crash_log.txt', 'w') as f:
        traceback.print_exception(exctype, value, tb, file=f)
    traceback.print_exception(exctype, value, tb)
    input("CRASHED - Press Enter to close...")

sys.excepthook = exception_hook



from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QStackedWidget, QFrame,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QAbstractItemView, QDialog, QFormLayout,
                              QLineEdit, QMessageBox, QSizePolicy, QScrollArea,
                              QComboBox, QSplitter)
from PyQt5.QtCore import Qt, QTimer, QMargins, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QGradient
from PyQt5.QtChart import (QChart, QChartView, QLineSeries, QDateTimeAxis,
                            QValueAxis, QAreaSeries, QSplineSeries)
from PyQt5.QtCore import QDateTime

from utils.styles import COLORS
from utils.database import (get_revenue_today, get_revenue_yesterday,
                             get_revenue_last_month, get_revenue_this_year,
                             get_revenue_over_time, get_all_transactions_admin,
                             get_all_staff, create_staff, get_current_shift_staff,
                             get_recent_activity_logs, log_activity,
                             get_staff_shift_history, get_all_staff_with_current_shift,
                             get_staff_login_logout_history, resolve_staff_flag)
from modules.widgets import SideNav, StatCard, SectionLabel, SearchableTable

from datetime import datetime


# ─── ADD STAFF DIALOG ─────────────────────────────────────────────────────────

class AddStaffDialog(QDialog):
    def __init__(self, admin_id, admin_username, parent=None):
        super().__init__(parent)
        self.admin_id = admin_id
        self.admin_username = admin_username
        self.setWindowTitle("Add New Staff")
        self.setFixedSize(400, 320)
        self.setStyleSheet(f"""
            QDialog {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}
            QLabel  {{ color: {COLORS['text']}; }}
        """)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        title = QLabel("Create Staff Account")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(12)

        def field(ph):
            f = QLineEdit(); f.setPlaceholderText(ph)
            f.setStyleSheet(f"""
                background: {COLORS['bg_input']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                padding: 9px 12px; font-size: 13px;
            """)
            return f

        self.name_input  = field("Full name")
        self.uname_input = field("Username (no spaces)")
        self.pass_input  = field("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)

        form.addRow(QLabel("Full Name:"),  self.name_input)
        form.addRow(QLabel("Username:"),   self.uname_input)
        form.addRow(QLabel("Password:"),   self.pass_input)
        lay.addLayout(form)

        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        self.err_lbl.hide()
        lay.addWidget(self.err_lbl)

        lay.addStretch()
        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 9px 16px;
            }}
        """)
        cancel.clicked.connect(self.reject)

        save = QPushButton("Create Account")
        save.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']}; color: white;
                border: none; border-radius: 7px; padding: 9px 18px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['primary_h']}; }}
        """)
        save.clicked.connect(self._save)
        btns.addWidget(cancel); btns.addStretch(); btns.addWidget(save)
        lay.addLayout(btns)

    def _save(self):
        name  = self.name_input.text().strip()
        uname = self.uname_input.text().strip().replace(' ', '_')
        pwd   = self.pass_input.text()
        if not all([name, uname, pwd]):
            self.err_lbl.setText("All fields are required."); self.err_lbl.show(); return
        if len(pwd) < 6:
            self.err_lbl.setText("Password must be at least 6 characters."); self.err_lbl.show(); return
        try:
            staff_id = create_staff(name, uname, pwd, self.admin_id)
            log_activity('admin', self.admin_id, self.admin_username,
                         'Created Staff', f"New staff '{name}' (@{uname}) ID:{staff_id}")
            self.accept()
        except ValueError as e:
            self.err_lbl.setText(str(e)); self.err_lbl.show()
        except Exception as e:
            self.err_lbl.setText(f"Error: {e}"); self.err_lbl.show()


# ─── ADMIN WINDOW ─────────────────────────────────────────────────────────────

class AdminWindow(QMainWindow):
    def __init__(self, user_info: dict, on_logout=None):
        super().__init__()
        self.user = user_info
        self.on_logout = on_logout
        self.setWindowTitle(f"ParkEase — Admin Panel  ({user_info['full_name']})")
        self.setMinimumSize(1200, 750)
        self.resize(1300, 820)
        self.setStyleSheet(f"background: {COLORS['bg']}; color: {COLORS['text']};")
        self._build_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(60_000)

    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_items = [
            ("", "Overview"),
            ("", "Vehicle History"),
            ("", "Staff Settings"),
        ]
        self.nav = SideNav(nav_items, self.user)
        self.nav.page_changed.connect(self._switch_page)

        logout_btn = QPushButton("Logout")
        logout_btn.setFixedHeight(42)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['danger']};
                border: 1px solid {COLORS['danger']}20; border-radius: 8px;
                padding: 0 14px; text-align: left; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLORS['danger']}15; }}
        """)
        logout_btn.clicked.connect(self._logout)
        self.nav.layout().addWidget(logout_btn)
        root.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg']};")
        root.addWidget(self.stack)

        self.stack.addWidget(self._build_overview())
        self.stack.addWidget(self._build_history())
        self.stack.addWidget(self._build_staff())

        self.nav.select(0)
        self._load_overview()

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        if   idx == 0: self._load_overview()
        elif idx == 1: self._load_history()
        elif idx == 2: self._load_staff()

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1 — OVERVIEW DASHBOARD
    # ──────────────────────────────────────────────────────────────────────────

    def _build_overview(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background: {COLORS['bg']};")

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("Admin Overview")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()
        self.admin_clock = QLabel()
        self.admin_clock.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        hdr.addWidget(self.admin_clock)
        lay.addLayout(hdr)

        clk = QTimer(self); clk.timeout.connect(self._update_admin_clock); clk.start(1000)
        self._update_admin_clock()

        # Revenue cards
        rev_row = QHBoxLayout(); rev_row.setSpacing(14)
        self.rev_today = StatCard("TODAY'S REVENUE",    "₱0.00", accent=COLORS['success'])
        self.rev_yest  = StatCard("YESTERDAY",          "₱0.00", accent=COLORS['primary'])
        self.rev_month = StatCard("LAST MONTH",         "₱0.00", accent=COLORS['accent'])
        self.rev_year  = StatCard("THIS YEAR",          "₱0.00", accent=COLORS['warning'])
        for c in [self.rev_today, self.rev_yest, self.rev_month, self.rev_year]:
            rev_row.addWidget(c)
        lay.addLayout(rev_row)

        # On Shift card
        self.shift_card = QFrame()
        self.shift_card.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 12px;
        """)
        self.shift_card_layout = QVBoxLayout(self.shift_card)
        self.shift_card_layout.setContentsMargins(20, 14, 20, 14)
        self.shift_card_layout.setSpacing(8)
        self.shift_lbl = QLabel("No staff currently on shift")
        self.shift_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        self.shift_card_layout.addWidget(self.shift_lbl)
        lay.addWidget(self.shift_card)

        

        # Activity log
        log_card = QFrame()
        log_card.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 12px;
        """)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(16, 14, 16, 14)
        log_t = QLabel("Recent Activity")
        log_t.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        log_lay.addWidget(log_t)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["Time & Date", "User", "Action", "Details"])
        self.log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setShowGrid(False)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setMaximumHeight(240)
        self.log_table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']}; alternate-background-color: {COLORS['bg_input']};
                color: {COLORS['text']}; border: none; font-size: 12px; outline: none;
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; }}
            QTableWidget::item:selected {{ background: {COLORS['primary']}; }}
            QHeaderView::section {{
                background: {COLORS['bg']}; color: {COLORS['text_muted']};
                font-size: 11px; font-weight: 600; padding: 8px 10px;
                border: none; border-bottom: 1px solid {COLORS['border']};
                text-transform: uppercase;
            }}
        """)
        log_lay.addWidget(self.log_table)
        lay.addWidget(log_card)

        scroll.setWidget(page)
        return scroll

    def _create_chart_view(self):
        self._chart = QChart()
        self._chart.setBackgroundBrush(QColor(COLORS['bg_card']))
        self._chart.setPlotAreaBackgroundBrush(QColor(COLORS['bg_card']))
        self._chart.setPlotAreaBackgroundVisible(True)
        self._chart.legend().hide()
        self._chart.setMargins(QMargins(0, 0, 0, 0))

        view = QChartView(self._chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setStyleSheet(f"background: {COLORS['bg_card']}; border: none;")
        view.setMinimumHeight(220)
        return view

    def _load_chart(self, period='7d'):
        # Highlight active button
        for p, btn in self.period_btns.items():
            btn.setProperty('selected', p == period)
            btn.style().unpolish(btn); btn.style().polish(btn)

        data = get_revenue_over_time(period)
        self._chart.removeAllSeries()
        for ax in self._chart.axes():
            self._chart.removeAxis(ax)

        if not data:
            return

        # FIX: Use self. prefix to prevent Python from garbage collecting these objects!
        self._series = QSplineSeries(self._chart)
        self._series.setColor(QColor(COLORS['primary']))
        pen = self._series.pen()
        pen.setWidth(2)
        self._series.setPen(pen)

        self._lower = QSplineSeries(self._chart)
        for label, val in data:
            try:
                if len(label) == 7:   # YYYY-MM
                    dt = QDateTime.fromString(label + "-01", "yyyy-MM-dd")
                else:
                    dt = QDateTime.fromString(label, "yyyy-MM-dd")
                ms = dt.toMSecsSinceEpoch()
                self._series.append(ms, float(val))
                self._lower.append(ms, 0)
            except Exception:
                continue

        # FIX: Keep area series and axes alive as class attributes
        self._area = QAreaSeries(self._series, self._lower)
        
        from PyQt5.QtGui import QColor as QC, QLinearGradient, QGradient, QPen
        grad = QLinearGradient(0, 0, 0, 1)
        grad.setCoordinateMode(QGradient.ObjectBoundingMode)
        grad.setColorAt(0, QC(59, 130, 246, 80))
        grad.setColorAt(1, QC(59, 130, 246, 5))
        self._area.setBrush(grad)
        self._area.setPen(QPen(Qt.NoPen))

        self._chart.addSeries(self._area)

        self._ax = QDateTimeAxis()
        self._ax.setFormat("MMM d")
        self._ax.setLabelsColor(QColor(COLORS['text_muted']))
        self._ax.setGridLineColor(QColor(COLORS['border']))
        self._chart.addAxis(self._ax, Qt.AlignBottom)
        self._area.attachAxis(self._ax)

        self._ay = QValueAxis()
        self._ay.setLabelFormat("₱%.0f")
        self._ay.setLabelsColor(QColor(COLORS['text_muted']))
        self._ay.setGridLineColor(QColor(COLORS['border']))
        self._chart.addAxis(self._ay, Qt.AlignLeft)
        self._area.attachAxis(self._ay)

    def _load_overview(self):
        try:
            self.rev_today.set_value(f"₱{get_revenue_today():.2f}")
            self.rev_yest.set_value(f"₱{get_revenue_yesterday():.2f}")
            self.rev_month.set_value(f"₱{get_revenue_last_month():.2f}")
            self.rev_year.set_value(f"₱{get_revenue_this_year():.2f}")
        except Exception:
            pass

        try:
            # Clear shift card
            while self.shift_card_layout.count():
                item = self.shift_card_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            active = get_all_staff_with_current_shift()
            if not active:
                lbl = QLabel("No staff currently on shift")
                lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
                self.shift_card_layout.addWidget(lbl)
            else:
                for s in active:
                    row = QHBoxLayout()
                    dot = QFrame(); dot.setFixedSize(10, 10)
                    dot.setStyleSheet(f"background: {COLORS['success']}; border-radius: 5px; border: none;")
                    row.addWidget(dot)
                    row.addSpacing(8)
                    start = s['shift_start']
                    start_s = start.strftime("%H:%M") if isinstance(start, datetime) else "—"
                    lbl = QLabel(f"On Shift: {s['full_name']}  —  since {start_s}")
                    lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
                    row.addWidget(lbl)
                    row.addStretch()
                    sys_total = float(s.get('current_collected') or 0)
                    rev_lbl = QLabel(f"System Total: P{sys_total:.2f}")
                    rev_lbl.setStyleSheet(f"color: {COLORS['success']}; font-size: 13px; font-weight: 600;")
                    row.addWidget(rev_lbl)
                    w = QWidget(); w.setLayout(row)
                    w.setStyleSheet("background: transparent;")
                    self.shift_card_layout.addWidget(w)
        except Exception:
            pass

        try:
            logs = get_recent_activity_logs(30)
            self.log_table.setRowCount(len(logs))
            for r, row in enumerate(logs):
                ts = row['log_time']
                ts_str = ts.strftime("%H:%M  %d %b") if isinstance(ts, datetime) else str(ts)
                for c, val in enumerate([ts_str, row['username'], row['action'], row.get('details','')]):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.log_table.setItem(r, c, item)
            self.log_table.resizeRowsToContents()
        except Exception:
            pass

    

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2 — VEHICLE HISTORY
    # ──────────────────────────────────────────────────────────────────────────

    def _build_history(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        t = QLabel("Vehicle Parking History")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(t)

        cols = ["Txn ID", "Plate", "Date",
                "Staff (Entry)", "Time In", "Staff (Exit)", "Time Out",
                "Duration", "Total (₱)"]
        self.history_table = SearchableTable(cols)
        lay.addWidget(self.history_table)
        return page

    def _load_history(self):
        rows_raw = get_all_transactions_admin()
        rows = []
        for r in rows_raw:
            ti = r['time_in']; to = r['time_out']
            ti_s = ti.strftime("%H:%M:%S") if isinstance(ti, datetime) else str(ti)
            to_s = to.strftime("%H:%M:%S") if isinstance(to, datetime) and to else '—'
            di   = r['date_in']
            di_s = di.strftime("%Y-%m-%d") if hasattr(di, 'strftime') else str(di)
            mins = r.get('duration_minutes') or 0
            h, m = divmod(mins, 60)
            rows.append([
                r['transaction_id'], r['plate_number'], di_s,
                r.get('staff_entry_name') or '—', ti_s,
                r.get('staff_exit_name') or '—', to_s,
                f"{h}h {m}m" if mins else '—',
                f"₱{r['total_charge']:.2f}" if r.get('total_charge') else '—'
            ])
        self.history_table.load_data(rows)

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3 — STAFF SETTINGS
    # ──────────────────────────────────────────────────────────────────────────

    def _build_staff(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background: {COLORS['bg']};")

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(20)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        t = QLabel("Staff Settings")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()
        add_btn = QPushButton("+ Add Staff")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']}; color: white; border: none;
                border-radius: 7px; padding: 0 18px; font-weight: 700; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLORS['primary_h']}; }}
        """)
        add_btn.clicked.connect(self._add_staff)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # ── Currently On Shift ────────────────────────────────────────────────
        sec1 = QLabel("CURRENTLY ON SHIFT")
        sec1.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(sec1)

        self.on_shift_frame = QFrame()
        self.on_shift_frame.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 10px;
        """)
        self.on_shift_layout = QVBoxLayout(self.on_shift_frame)
        self.on_shift_layout.setContentsMargins(16, 14, 16, 14)
        self.on_shift_layout.setSpacing(8)
        lay.addWidget(self.on_shift_frame)

        # ── Staff List ────────────────────────────────────────────────────────
        sec2 = QLabel("ALL STAFF")
        sec2.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(sec2)

        cols = ["ID", "Full Name", "Username", "Status", "Discrepancy Stats", "Created At", "Created By"]
        self.staff_table = SearchableTable(cols)
        self.staff_table.setMaximumHeight(220)
        lay.addWidget(self.staff_table)

        # ── Login/Logout History ──────────────────────────────────────────────
        hist_hdr = QHBoxLayout()
        sec3 = QLabel("LOGIN / LOGOUT HISTORY")
        sec3.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        hist_hdr.addWidget(sec3)
        hist_hdr.addStretch()

        view_lbl = QLabel("View history for:")
        view_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        hist_hdr.addWidget(view_lbl)

        self.staff_combo = QComboBox()
        self.staff_combo.setFixedHeight(34)
        self.staff_combo.setMinimumWidth(200)
        self.staff_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_input']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                padding: 0 12px; font-size: 13px;
            }}
            QComboBox::drop-down {{ border: none; padding-right: 8px; }}
            QComboBox QAbstractItemView {{
                background: {COLORS['bg_card']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
            }}
        """)
        self.staff_combo.currentIndexChanged.connect(self._load_shift_history)
        hist_hdr.addWidget(self.staff_combo)
        lay.addLayout(hist_hdr)

        # History table
        self.shift_history_table = QTableWidget()
        self.shift_history_table.setColumnCount(8)
        self.shift_history_table.setHorizontalHeaderLabels([
            "Date", "Time In", "Time Out", "Vehicles",
            "Staff Reported", "System Total", "Discrepancy", "Action"
        ])
        self.shift_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.shift_history_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.shift_history_table.verticalHeader().setVisible(False)
        self.shift_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.shift_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shift_history_table.setShowGrid(False)
        self.shift_history_table.setAlternatingRowColors(True)
        self.shift_history_table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']}; alternate-background-color: {COLORS['bg_input']};
                color: {COLORS['text']}; border: 1px solid {COLORS['border']};
                border-radius: 10px; font-size: 12px; outline: none;
            }}
            QTableWidget::item {{ padding: 10px 12px; border: none; }}
            QTableWidget::item:selected {{ background: {COLORS['primary']}; color: white; }}
            QHeaderView::section {{
                background: {COLORS['bg']}; color: {COLORS['text_muted']};
                font-size: 11px; font-weight: 600; padding: 8px 12px;
                border: none; border-bottom: 1px solid {COLORS['border']};
                text-transform: uppercase;
            }}
        """)
        lay.addWidget(self.shift_history_table)

        scroll.setWidget(page)
        return scroll

    def _load_staff(self):
        # ── Currently on shift ────────────────────────────────────────────────
        try:
            while self.on_shift_layout.count():
                item = self.on_shift_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            active = get_all_staff_with_current_shift()

            if not active:
                lbl = QLabel("No staff currently on shift.")
                lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 13px;")
                self.on_shift_layout.addWidget(lbl)
            else:
                for s in active:
                    card = QFrame()
                    card.setStyleSheet(f"""
                        background: {COLORS['bg_input']}; border-radius: 8px;
                        border: 1px solid {COLORS['border']};
                    """)
                    cl = QHBoxLayout(card)
                    cl.setContentsMargins(16, 12, 16, 12)

                    dot = QFrame()
                    dot.setFixedSize(10, 10)
                    dot.setStyleSheet(f"background: {COLORS['success']}; border-radius: 5px; border: none;")
                    cl.addWidget(dot)
                    cl.addSpacing(8)

                    name_lbl = QLabel(s['full_name'])
                    name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 700;")
                    cl.addWidget(name_lbl)
                    cl.addSpacing(16)

                    start = s['shift_start']
                    start_s = start.strftime("%b %d, %Y  %H:%M") if isinstance(start, datetime) else "—"
                    since_lbl = QLabel(f"Since {start_s}")
                    since_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
                    cl.addWidget(since_lbl)
                    cl.addStretch()

                    sys_total = float(s.get('current_collected') or 0)
                    total_lbl = QLabel(f"System Total:  P{sys_total:.2f}")
                    total_lbl.setStyleSheet(f"color: {COLORS['success']}; font-size: 13px; font-weight: 600;")
                    cl.addWidget(total_lbl)
                    cl.addSpacing(12)

                    note_lbl = QLabel("Blind drop pending")
                    note_lbl.setStyleSheet(f"""
                        color: {COLORS['warning']}; font-size: 11px;
                        background: {COLORS['warning']}18;
                        border: 1px solid {COLORS['warning']}40;
                        border-radius: 4px; padding: 2px 8px;
                    """)
                    cl.addWidget(note_lbl)
                    self.on_shift_layout.addWidget(card)
        except Exception:
            pass

        # ── Staff list ────────────────────────────────────────────────────────
        try:
            rows_raw = get_all_staff()
            rows = []
            for r in rows_raw:
                status = "Active" if r['is_active'] else "Inactive"
                total_shifts = r.get('total_shifts', 0) or 0
                total_disc   = r.get('total_discrepancies', 0) or 0
                unresolved   = r.get('unresolved_discrepancies', 0) or 0
                # e.g. "2/5 shifts" or "0/3 shifts (clean)"
                if total_shifts == 0:
                    disc_stat = "No shifts yet"
                elif total_disc == 0:
                    disc_stat = f"0/{total_shifts} shifts (clean)"
                else:
                    disc_stat = f"{total_disc}/{total_shifts} shifts flagged"
                    if unresolved > 0:
                        disc_stat += f" ({unresolved} pending)"
                ca = r['created_at']
                ca_s = ca.strftime("%Y-%m-%d %H:%M") if isinstance(ca, datetime) else str(ca)
                rows.append([
                    r['id'], r['full_name'], r['username'],
                    status, disc_stat, ca_s, r.get('created_by_name') or '—'
                ])
            self.staff_table.load_data(rows)
            for row_idx, row in enumerate(rows):
                has_unresolved = "pending" in row[4]
                has_any_disc   = "flagged" in row[4]
                for col in range(len(row)):
                    item = self.staff_table.table.item(row_idx, col)
                    if item:
                        if has_unresolved:
                            item.setForeground(QColor(COLORS['danger']))
                        elif has_any_disc:
                            item.setForeground(QColor(COLORS['warning']))

            # Populate dropdown
            self.staff_combo.blockSignals(True)
            current = self.staff_combo.currentText()
            self.staff_combo.clear()
            self._staff_id_map = {}
            self._staff_raw = {}
            for r in rows_raw:
                self.staff_combo.addItem(r['full_name'])
                self._staff_id_map[r['full_name']] = r['id']
                self._staff_raw[r['id']] = r
            idx = self.staff_combo.findText(current)
            self.staff_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.staff_combo.blockSignals(False)
        except Exception:
            pass

        self._load_shift_history()

    def _load_shift_history(self):
        try:
            name = self.staff_combo.currentText()
            if not name or not hasattr(self, '_staff_id_map'):
                return
            staff_id = self._staff_id_map.get(name)
            if not staff_id:
                return

            shifts = get_staff_login_logout_history(staff_id)
            self.shift_history_table.setRowCount(len(shifts))

            for r, sh in enumerate(shifts):
                start    = sh['shift_start']
                end      = sh['shift_end']
                sys_rev  = float(sh.get('system_revenue') or 0)
                rep_rev  = float(sh.get('staff_reported_revenue') or 0)
                flagged  = sh.get('is_flagged', False)
                vehicles = sh.get('vehicles_handled', 0)
                is_active = end is None

                date_s  = start.strftime("%Y-%m-%d")  if isinstance(start, datetime) else "—"
                tin_s   = start.strftime("%H:%M")     if isinstance(start, datetime) else "—"
                tout_s  = end.strftime("%H:%M")       if isinstance(end,   datetime) else "On Shift"
                disc    = sys_rev - rep_rev

                is_resolved = sh.get('is_resolved', False)
                if is_active:
                    disc_s = "—"
                elif flagged and not is_resolved:
                    disc_s = f"P{abs(disc):.2f} {'SHORT' if disc > 0 else 'OVER'} ⚑"
                elif flagged and is_resolved:
                    disc_s = f"P{abs(disc):.2f} (Resolved)"
                else:
                    disc_s = "None"

                vals = [date_s, tin_s, tout_s, str(vehicles),
                        f"P{rep_rev:.2f}" if not is_active else "—",
                        f"P{sys_rev:.2f}" if not is_active else "—",
                        disc_s]

                for c, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    if flagged and not is_resolved and not is_active:
                        item.setForeground(QColor(COLORS['danger']))
                    elif flagged and is_resolved:
                        item.setForeground(QColor(COLORS['warning']))  # faded — resolved but noted
                    elif is_active:
                        item.setForeground(QColor(COLORS['warning']))
                    self.shift_history_table.setItem(r, c, item)

                # Resolve button — only for flagged completed shifts
                if flagged and not is_resolved and not is_active:
                    resolve_btn = QPushButton("Resolve")
                    resolve_btn.setFixedHeight(28)
                    resolve_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {COLORS['success']}; color: white; border: none;
                            border-radius: 5px; font-size: 11px; font-weight: 600;
                            padding: 0 10px;
                        }}
                        QPushButton:hover {{ background: #059669; }}
                    """)
                    resolve_btn.clicked.connect(lambda _, sid=staff_id, shid=sh['id']: self._resolve_flag(sid, shid))
                    self.shift_history_table.setCellWidget(r, 7, resolve_btn)
                else:
                    self.shift_history_table.setCellWidget(r, 7, None)

            self.shift_history_table.resizeRowsToContents()
        except Exception:
            pass

    def _resolve_flag(self, staff_id, shift_id):
        reply = QMessageBox.question(
            self, "Resolve Discrepancy",
            "Mark this specific shift's discrepancy as reviewed?\n\n"
            "The record will be kept but marked as resolved.\n"
            "The staff flag will be cleared only if no other pending discrepancies remain.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                remaining = resolve_staff_flag(staff_id, shift_id)
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Resolved Discrepancy',
                             f"Shift ID {shift_id} resolved for staff ID {staff_id}. "
                             f"{remaining} unresolved remaining.")
                self._load_staff()
                if remaining == 0:
                    QMessageBox.information(self, "Resolved",
                        "Discrepancy marked as resolved.\nAll discrepancies cleared — staff flag removed.")
                else:
                    QMessageBox.information(self, "Resolved",
                        f"Discrepancy marked as resolved.\n{remaining} other discrepancy/ies still pending.")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_staff(self):
        dlg = AddStaffDialog(self.user['user_id'], self.user['username'], self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_staff()
            QMessageBox.information(self, "Success", "Staff account created successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _update_admin_clock(self):
        self.admin_clock.setText(datetime.now().strftime("%A, %d %B %Y  •  %H:%M:%S"))

    def _auto_refresh(self):
        if self.stack.currentIndex() == 0:
            self._load_overview()

    def _logout(self):
        log_activity('admin', self.user['user_id'], self.user['username'],
                     'Logout', f"Admin {self.user['full_name']} logged out")
        if self.on_logout:
            self.on_logout()
