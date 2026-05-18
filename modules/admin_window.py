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
                              QComboBox, QSplitter, QDateEdit, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, QMargins, pyqtSlot, QDate
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QGradient, QPixmap
from PyQt5.QtChart import (QChart, QChartView, QLineSeries, QDateTimeAxis,
                            QValueAxis, QAreaSeries, QSplineSeries,
                            QBarSeries, QBarSet, QBarCategoryAxis)
from PyQt5.QtCore import QDateTime

from utils.styles import COLORS
from utils.database import (get_revenue_today, get_revenue_last_7_days,
                             get_revenue_last_month, get_revenue_this_year,
                             get_revenue_over_time, get_all_transactions_admin,
                             get_all_staff, create_staff, get_current_shift_staff,
                             get_recent_activity_logs, log_activity,
                             get_staff_shift_history, get_all_staff_with_current_shift,
                             get_staff_login_logout_history, resolve_staff_flag,
                             get_dashboard_summary, get_notifications,
                             set_staff_active,
                             get_settings, update_settings,
                             get_blacklist, add_to_blacklist, remove_from_blacklist,
                             get_reserved_vehicles, add_reserved_vehicle, remove_reserved_vehicle,
                             get_peak_hours, get_revenue_per_staff, get_vehicle_type_breakdown)
from modules.widgets import SideNav, StatCard, SectionLabel
from utils.detection import CameraWorker
from utils.worker import Worker

from datetime import datetime


# ─── CAMERA PREVIEW DIALOG ────────────────────────────────────────────────────

class CameraPreviewDialog(QDialog):
    def __init__(self, camera_index, video_file=None, parent=None):
        super().__init__(parent)
        source_label = "Demo Video" if video_file else f"Camera {camera_index}"
        self.setWindowTitle(f"Camera Preview — {source_label}")
        self.setFixedSize(700, 580)
        self.setStyleSheet(f"background: {COLORS['bg']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        title = QLabel(f"{source_label} Preview")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; font-weight: 700;")
        lay.addWidget(title)

        self.preview_lbl = QLabel("Loading camera…")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setFixedSize(660, 495)
        self.preview_lbl.setStyleSheet(
            f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 8px; color: {COLORS['text_muted']}; font-size: 13px;"
        )
        lay.addWidget(self.preview_lbl)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 8px;
                font-size: 13px; font-weight: 600; padding: 0 20px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        close_btn.clicked.connect(self.close)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)

        self.worker = CameraWorker(camera_index=camera_index, mode='entry', video_file=video_file)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_frame(self, img):
        pix = QPixmap.fromImage(img).scaled(
            660, 495, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_lbl.setPixmap(pix)

    def _on_error(self, msg):
        self.preview_lbl.setText(f"Error: {msg}")

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)


# ─── TABLE STYLESHEET HELPER ──────────────────────────────────────────────────

def _table_style():
    return ""

def _btn_primary():
    return ""

def _field_style():
    return ""

def _card_frame():
    f = QFrame()
    f.setProperty("card", "true")
    return f


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
            f.setStyleSheet(_field_style())
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
        save.setStyleSheet(_btn_primary())
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
            ("", "Settings"),
            ("", "Blacklist"),
            ("", "Reserved"),
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
        root.addWidget(self.stack)

        self.stack.addWidget(self._build_overview())    # 0
        self.stack.addWidget(self._build_history())     # 1
        self.stack.addWidget(self._build_staff())       # 2
        self.stack.addWidget(self._build_settings())    # 3
        self.stack.addWidget(self._build_blacklist())   # 4
        self.stack.addWidget(self._build_reserved())    # 5

        self.nav.select(0)
        self._load_overview()

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        if   idx == 0: self._load_overview()
        elif idx == 1: self._load_history()
        elif idx == 2: self._load_staff()
        elif idx == 3: self._load_settings()
        elif idx == 4: self._load_blacklist()
        elif idx == 5: self._load_reserved()

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 0 — OVERVIEW DASHBOARD
    # ──────────────────────────────────────────────────────────────────────────

    def _build_overview(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

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

        # ── Today's summary cards ─────────────────────────────────────────────
        sum_row = QHBoxLayout(); sum_row.setSpacing(14)
        self.sum_entries   = StatCard("ENTRIES TODAY",     "0", accent=COLORS['success'])
        self.sum_exits     = StatCard("EXITS TODAY",       "0", accent=COLORS['primary'])
        self.sum_parked    = StatCard("CURRENTLY PARKED",  "0", accent=COLORS['accent'])
        self.sum_overstay  = StatCard("OVERSTAYS",         "0", accent=COLORS['danger'])
        self.sum_capacity  = StatCard("LOT CAPACITY",      "0", accent=COLORS['warning'])
        for c in [self.sum_entries, self.sum_exits, self.sum_parked,
                self.sum_overstay, self.sum_capacity]:
            sum_row.addWidget(c)
        lay.addLayout(sum_row)

        # ── Revenue cards ─────────────────────────────────────────────────────
        rev_row = QHBoxLayout(); rev_row.setSpacing(14)
        self.rev_today = StatCard("TODAY'S REVENUE",  "₱0.00", accent=COLORS['success'])
        self.rev_yest  = StatCard("LAST 7 DAYS",       "₱0.00", accent=COLORS['primary'])
        self.rev_month = StatCard("LAST MONTH",       "₱0.00", accent=COLORS['accent'])
        self.rev_year  = StatCard("THIS YEAR",        "₱0.00", accent=COLORS['warning'])
        for c in [self.rev_today, self.rev_yest, self.rev_month, self.rev_year]:
            rev_row.addWidget(c)
        lay.addLayout(rev_row)

        # ── Revenue chart ─────────────────────────────────────────────────────
        chart_card = _card_frame()
        chart_lay = QVBoxLayout(chart_card)
        chart_lay.setContentsMargins(16, 14, 16, 14)
        chart_lay.setSpacing(10)

        chart_hdr = QHBoxLayout()
        chart_t = QLabel("Revenue Over Time")
        chart_t.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; font-weight: 700;")
        chart_hdr.addWidget(chart_t)
        chart_hdr.addStretch()

        self.period_btns = {}
        for label, key in [("7D", "7d"), ("Month", "month"),
                            ("3M", "3m"), ("6M", "6m"), ("Year", "year")]:
            btn = QPushButton(label)
            btn.setFixedSize(76, 28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']}; border-radius: 6px; font-size: 11px;
                }}
                QPushButton:hover {{ background: {COLORS['bg_hover']}; color: {COLORS['text']}; }}
                QPushButton[selected=true] {{
                    background: {COLORS['primary']}; color: white; border-color: {COLORS['primary']};
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._load_chart(k))
            chart_hdr.addWidget(btn)
            self.period_btns[key] = btn

        chart_lay.addLayout(chart_hdr)
        self._chart_view = self._create_chart_view()
        chart_lay.addWidget(self._chart_view)
        lay.addWidget(chart_card)

        # ── On Shift card ─────────────────────────────────────────────────────
        self.shift_card = _card_frame()
        self.shift_card_layout = QVBoxLayout(self.shift_card)
        self.shift_card_layout.setContentsMargins(20, 14, 20, 14)
        self.shift_card_layout.setSpacing(8)
        self.shift_lbl = QLabel("No staff currently on shift")
        self.shift_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        self.shift_card_layout.addWidget(self.shift_lbl)
        lay.addWidget(self.shift_card)

        # ── Notifications panel ───────────────────────────────────────────────
        notif_card = _card_frame()
        notif_lay = QVBoxLayout(notif_card)
        notif_lay.setContentsMargins(16, 14, 16, 14)

        notif_hdr = QHBoxLayout()
        notif_t = QLabel("NOTIFICATIONS")
        notif_t.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        notif_hdr.addWidget(notif_t)
        notif_hdr.addStretch()
        notif_lay.addLayout(notif_hdr)

        self.notif_widget = QWidget()
        self.notif_layout = QVBoxLayout(self.notif_widget)
        self.notif_layout.setContentsMargins(0, 0, 0, 0)
        self.notif_layout.setSpacing(8)
        notif_lay.addWidget(self.notif_widget)
        lay.addWidget(notif_card)

        # ── Activity log ──────────────────────────────────────────────────────
        log_card = _card_frame()
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
        self.log_table.setMinimumHeight(400)
        self.log_table.setStyleSheet(_table_style())
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
        view.setMinimumHeight(220)
        return view

    def _load_chart(self, period='7d'):
        for p, btn in self.period_btns.items():
            btn.setProperty('selected', p == period)
            btn.style().unpolish(btn); btn.style().polish(btn)

        def fetch():
            return get_revenue_over_time(period)

        _w = Worker(fetch)
        _w.result.connect(lambda data: self._render_chart(data, period))
        _w.start()
        self._chart_worker = _w

    def _render_chart(self, data, period='7d'):
        self._chart.removeAllSeries()
        for ax in self._chart.axes():
            self._chart.removeAxis(ax)

        if not data:
            return

        self._series = QSplineSeries(self._chart)
        self._series.setColor(QColor(COLORS['primary']))
        pen = self._series.pen(); pen.setWidth(2); self._series.setPen(pen)

        self._lower = QSplineSeries(self._chart)
        for label, val in data:
            try:
                dt = QDateTime.fromString(label + "-01", "yyyy-MM-dd") if len(label) == 7 \
                     else QDateTime.fromString(label, "yyyy-MM-dd")
                ms = dt.toMSecsSinceEpoch()
                self._series.append(ms, float(val))
                self._lower.append(ms, 0)
            except Exception:
                continue

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
        self._ay.setLabelFormat("P%.0f")
        self._ay.setLabelsColor(QColor(COLORS['text_muted']))
        self._ay.setGridLineColor(QColor(COLORS['border']))
        self._chart.addAxis(self._ay, Qt.AlignLeft)
        self._area.attachAxis(self._ay)

    def _load_overview(self):
        if getattr(self, '_overview_worker', None) and self._overview_worker.isRunning():
            return

        def fetch():
            return {
                'summary':      get_dashboard_summary(),
                'rev_today':    get_revenue_today(),
                'rev_7d':       get_revenue_last_7_days(),
                'rev_month':    get_revenue_last_month(),
                'rev_year':     get_revenue_this_year(),
                'chart_data':   get_revenue_over_time('7d'),
                'active_staff': get_all_staff_with_current_shift(),
                'notifs':       get_notifications(),
                'logs':         get_recent_activity_logs(30),
            }

        self._overview_worker = Worker(fetch)
        self._overview_worker.result.connect(self._on_overview_loaded)
        self._overview_worker.start()

    def _on_overview_loaded(self, data):
        try:
            summary = data.get('summary') or {}
            if summary:
                capacity = int(summary.get('capacity') or 50)
                parked   = int(summary.get('currently_parked') or 0)
                self.sum_entries.set_value(summary.get('entries_today', 0))
                self.sum_exits.set_value(summary.get('exits_today', 0))
                self.sum_parked.set_value(f"{parked} / {capacity}")
                self.sum_overstay.set_value(summary.get('overstay_count', 0))
                free = max(0, capacity - parked)
                pct  = int((parked / capacity) * 100) if capacity > 0 else 0
                self.sum_capacity.set_value(f"{free} free")
                if pct >= 90:
                    self.sum_capacity.setStyleSheet(f"""
                        QFrame {{ background: {COLORS['danger']}18;
                        border: 1px solid {COLORS['danger']}40; border-radius: 12px; }}
                    """)
                elif pct >= 70:
                    self.sum_capacity.setStyleSheet(f"""
                        QFrame {{ background: {COLORS['warning']}18;
                        border: 1px solid {COLORS['warning']}40; border-radius: 12px; }}
                    """)
        except Exception:
            pass

        try:
            self.rev_today.set_value(f"₱{data['rev_today']:.2f}")
            self.rev_yest.set_value(f"₱{data['rev_7d']:.2f}")
            self.rev_month.set_value(f"₱{data['rev_month']:.2f}")
            self.rev_year.set_value(f"₱{data['rev_year']:.2f}")
        except Exception:
            pass

        try:
            for p, btn in self.period_btns.items():
                btn.setProperty('selected', p == '7d')
                btn.style().unpolish(btn); btn.style().polish(btn)
            self._render_chart(data.get('chart_data') or [], '7d')
        except Exception:
            pass

        try:
            while self.shift_card_layout.count():
                item = self.shift_card_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            active = data.get('active_staff') or []
            if not active:
                lbl = QLabel("No staff currently on shift")
                lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
                self.shift_card_layout.addWidget(lbl)
            else:
                for s in active:
                    row = QHBoxLayout()
                    dot = QFrame(); dot.setFixedSize(10, 10)
                    dot.setStyleSheet(f"background: {COLORS['success']}; border-radius: 5px; border: none;")
                    row.addWidget(dot); row.addSpacing(8)
                    start = s['shift_start']
                    start_s = start.strftime("%H:%M") if isinstance(start, datetime) else "—"
                    lbl = QLabel(f"On Shift: {s['full_name']}  —  since {start_s}")
                    lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
                    row.addWidget(lbl); row.addStretch()
                    sys_total = float(s.get('current_collected') or 0)
                    rev_lbl = QLabel(f"System Total: ₱{sys_total:.2f}")
                    rev_lbl.setStyleSheet(f"color: {COLORS['success']}; font-size: 13px; font-weight: 600;")
                    row.addWidget(rev_lbl)
                    w = QWidget(); w.setLayout(row); w.setStyleSheet("background: transparent;")
                    self.shift_card_layout.addWidget(w)
        except Exception:
            pass

        try:
            while self.notif_layout.count():
                item = self.notif_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            notifs = data.get('notifs') or []
            if not notifs:
                lbl = QLabel("No active notifications")
                lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
                self.notif_layout.addWidget(lbl)
            else:
                for n in notifs:
                    row = QFrame()
                    is_overstay = n['type'] == 'overstay'
                    accent = COLORS['warning'] if is_overstay else COLORS['danger']
                    row.setStyleSheet(f"background: {accent}18; border: 1px solid {accent}40; border-radius: 8px;")
                    rl = QHBoxLayout(row); rl.setContentsMargins(12, 10, 12, 10)
                    icon_lbl = QLabel("⏰" if is_overstay else "⚑")
                    icon_lbl.setStyleSheet(f"color: {accent}; font-size: 16px; background: transparent; border: none;")
                    rl.addWidget(icon_lbl); rl.addSpacing(8)
                    msg_lbl = QLabel(f"<b>{n['name']}</b> — {n['message']}")
                    msg_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; background: transparent; border: none;")
                    rl.addWidget(msg_lbl); rl.addStretch()
                    ts = n['event_time']
                    ts_s = ts.strftime("%b %d %H:%M") if isinstance(ts, datetime) else str(ts)
                    ts_lbl = QLabel(ts_s)
                    ts_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent; border: none;")
                    rl.addWidget(ts_lbl)
                    self.notif_layout.addWidget(row)
        except Exception:
            pass

        try:
            logs = data.get('logs') or []
            self.log_table.setRowCount(len(logs))
            for r, row in enumerate(logs):
                ts = row['log_time']
                ts_str = ts.strftime("%H:%M  %d %b") if isinstance(ts, datetime) else str(ts)
                for c, val in enumerate([ts_str, row['username'], row['action'], row.get('details', '')]):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.log_table.setItem(r, c, item)
            self.log_table.resizeRowsToContents()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1 — VEHICLE HISTORY
    # ──────────────────────────────────────────────────────────────────────────

    def _build_history(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("Vehicle Parking History")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()

        self.export_period = QComboBox()
        self.export_period.addItems(["Today", "Yesterday", "Weekly", "Monthly", "All"])
        self.export_period.setFixedHeight(34)
        self.export_period.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_input']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                padding: 0 12px; font-size: 13px; min-width: 120px;
            }}
            QComboBox::drop-down {{ border: none; padding-right: 8px; }}
            QComboBox QAbstractItemView {{
                background: {COLORS['bg_card']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
            }}
        """)
        hdr.addWidget(self.export_period)

        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setFixedHeight(34)
        export_pdf_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['danger']}; color: white; border: none;
                border-radius: 7px; padding: 0 16px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #DC2626; }}
        """)
        export_pdf_btn.clicked.connect(lambda: self._export_report('pdf'))
        hdr.addWidget(export_pdf_btn)

        export_excel_btn = QPushButton("Export Excel")
        export_excel_btn.setFixedHeight(34)
        export_excel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['success']}; color: white; border: none;
                border-radius: 7px; padding: 0 16px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #059669; }}
        """)
        export_excel_btn.clicked.connect(lambda: self._export_report('excel'))
        hdr.addWidget(export_excel_btn)

        lay.addLayout(hdr)

        # Analytics row
        analytics_row = QHBoxLayout(); analytics_row.setSpacing(14)
        self.analytics_cars    = StatCard("CARS",         "0",     accent=COLORS['primary'])
        self.analytics_motos   = StatCard("MOTORCYCLES",  "0",     accent=COLORS['success'])
        self.analytics_trucks  = StatCard("TRUCKS/BUSES", "0",     accent=COLORS['warning'])
        self.analytics_revenue = StatCard("TOTAL REVENUE","₱0.00", accent=COLORS['accent'])
        for c in [self.analytics_cars, self.analytics_motos,
                  self.analytics_trucks, self.analytics_revenue]:
            analytics_row.addWidget(c)
        lay.addLayout(analytics_row)

        # Search + table
        search_row = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search...")
        self.history_search.setFixedHeight(36)
        self.history_search.setStyleSheet(f"""
            background-color: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 8px;
            padding: 0 12px; font-size: 13px;
        """)
        self.history_search.textChanged.connect(self._filter_history)
        search_row.addWidget(self.history_search); search_row.addStretch()
        lay.addLayout(search_row)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(12)
        self.history_table.setHorizontalHeaderLabels([
            "TXN ID", "Plate", "Type", "Date",
            "Staff (Entry)", "Time In", "Staff (Exit)", "Time Out",
            "Duration", "Total (₱)", "Status", "Actions"
        ])
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(11, QHeaderView.Fixed)
        self.history_table.setColumnWidth(0, 200)
        self.history_table.setColumnWidth(11, 145)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.setStyleSheet(_table_style())
        lay.addWidget(self.history_table)

        # ── Peak Hours chart ──────────────────────────────────────────────────
        peak_card = _card_frame()
        peak_lay = QVBoxLayout(peak_card)
        peak_lay.setContentsMargins(16, 14, 16, 14)
        peak_lay.setSpacing(10)
        peak_title = QLabel("Peak Hours — Vehicle Arrivals by Hour")
        peak_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; font-weight: 700;")
        peak_lay.addWidget(peak_title)

        self._peak_chart = QChart()
        self._peak_chart.setBackgroundBrush(QColor(COLORS['bg_card']))
        self._peak_chart.legend().hide()
        self._peak_chart.setMargins(QMargins(0, 0, 0, 0))
        self._peak_view = QChartView(self._peak_chart)
        self._peak_view.setRenderHint(QPainter.Antialiasing)
        self._peak_view.setMinimumHeight(200)
        peak_lay.addWidget(self._peak_view)
        lay.addWidget(peak_card)

        # ── Revenue per Staff table ───────────────────────────────────────────
        rev_staff_card = _card_frame()
        rs_lay = QVBoxLayout(rev_staff_card)
        rs_lay.setContentsMargins(16, 14, 16, 14)
        rs_lay.setSpacing(10)
        rs_title = QLabel("Revenue per Staff Member")
        rs_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; font-weight: 700;")
        rs_lay.addWidget(rs_title)

        self.revenue_staff_table = QTableWidget()
        self.revenue_staff_table.setColumnCount(4)
        self.revenue_staff_table.setHorizontalHeaderLabels(
            ["Full Name", "Username", "Transactions", "Revenue (₱)"])
        self.revenue_staff_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.revenue_staff_table.verticalHeader().setVisible(False)
        self.revenue_staff_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.revenue_staff_table.setAlternatingRowColors(True)
        self.revenue_staff_table.setShowGrid(False)
        self.revenue_staff_table.setMaximumHeight(220)
        self.revenue_staff_table.setStyleSheet(_table_style())
        rs_lay.addWidget(self.revenue_staff_table)
        lay.addWidget(rev_staff_card)

        scroll.setWidget(page)
        return scroll

    def _load_history(self):
        if getattr(self, '_history_worker', None) and self._history_worker.isRunning():
            return

        def fetch():
            return {
                'txns':      get_all_transactions_admin(),
                'breakdown': get_vehicle_type_breakdown(),
                'peak':      get_peak_hours(),
                'per_staff': get_revenue_per_staff(),
            }

        self._history_worker = Worker(fetch)
        self._history_worker.result.connect(self._on_history_loaded)
        self._history_worker.start()

    def _on_history_loaded(self, data):
        try:
            cars = motos = trucks = total_rev = 0
            for b in data.get('breakdown') or []:
                vtype = (b['vehicle_type'] or '').lower()
                cnt = int(b['count']); rev = float(b['revenue'])
                total_rev += rev
                if 'car' in vtype:              cars  += cnt
                elif 'motorcycle' in vtype:     motos += cnt
                elif 'truck' in vtype or 'bus' in vtype: trucks += cnt
            self.analytics_cars.set_value(cars)
            self.analytics_motos.set_value(motos)
            self.analytics_trucks.set_value(trucks)
            self.analytics_revenue.set_value(f"₱{total_rev:.2f}")
        except Exception:
            pass

        rows_raw = data.get('txns') or []
        self._history_raw = rows_raw
        self._render_history(rows_raw)

        try:
            self._render_peak_hours_chart(data.get('peak') or [])
        except Exception:
            pass

        try:
            self._render_revenue_per_staff(data.get('per_staff') or [])
        except Exception:
            pass

    def _render_history(self, data):
        self.history_table.setRowCount(len(data))
        for row_idx, r in enumerate(data):
            ti = r['time_in']; to = r['time_out']
            ti_s = ti.strftime("%H:%M:%S") if isinstance(ti, datetime) else str(ti)
            to_s = to.strftime("%H:%M:%S") if isinstance(to, datetime) and to else '—'
            di   = r['date_in']
            di_s = di.strftime("%Y-%m-%d") if hasattr(di, 'strftime') else str(di)
            mins = r.get('duration_minutes') or 0
            h, m = divmod(mins, 60)

            vals = [
                r['transaction_id'], r['plate_number'],
                r.get('vehicle_type') or '—', di_s,
                r.get('staff_entry_name') or '—', ti_s,
                r.get('staff_exit_name') or '—', to_s,
                f"{h}h {m}m" if mins else '—',
                f"₱{r['total_charge']:.2f}" if r.get('total_charge') else '—',
                (r.get('status') or 'unknown').upper(),
                ''
            ]

            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.history_table.setItem(row_idx, c, item)

            self.history_table.setRowHeight(row_idx, 68)

            btn_widget = QWidget(); btn_widget.setFixedWidth(145)
            btn_lay = QHBoxLayout(btn_widget)
            btn_lay.setContentsMargins(4, 12, 4, 12)
            btn_lay.setSpacing(4)

            _cell_btn_style = """
                border-radius: 4px; font-size: 11px; padding: 0 8px;
                color: white; border: none;
            """
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(44)
            edit_btn.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['primary']}; {_cell_btn_style} }}
                QPushButton:hover {{ background: {COLORS['primary_h']}; }}
            """)
            edit_btn.clicked.connect(lambda _, txn=r: self._edit_transaction(txn))

            if str(r.get('status', '')).lower() in ('active', 'unknown') or r.get('time_out') is None:
                edit_btn.setFixedWidth(64)
                close_btn = QPushButton("Close"); close_btn.setFixedWidth(64); close_btn.setFixedHeight(44)
                close_btn.setStyleSheet(f"""
                    QPushButton {{ background: {COLORS['warning']}; {_cell_btn_style} }}
                    QPushButton:hover {{ background: #D97706; }}
                """)
                close_btn.clicked.connect(lambda _, txn=r: self._close_transaction(txn))
                btn_lay.addWidget(edit_btn); btn_lay.addWidget(close_btn)
            else:
                edit_btn.setFixedWidth(133); btn_lay.addWidget(edit_btn)

            self.history_table.setCellWidget(row_idx, 11, btn_widget)

    def _filter_history(self, text):
        if not hasattr(self, '_history_raw'):
            return
        if not text:
            self._render_history(self._history_raw); return
        text = text.lower()
        filtered = [r for r in self._history_raw
                    if any(text in str(v).lower() for v in r.values())]
        self._render_history(filtered)

    def _render_peak_hours_chart(self, data):
        self._peak_chart.removeAllSeries()
        for ax in self._peak_chart.axes():
            self._peak_chart.removeAxis(ax)
        if not data:
            return

        hour_map = {int(r['hour']): int(r['vehicle_count']) for r in data}
        self._ph_bar_set = QBarSet("Vehicles")
        self._ph_bar_set.setColor(QColor(COLORS['primary']))
        categories = []
        for h in range(24):
            self._ph_bar_set.append(hour_map.get(h, 0))
            categories.append(f"{h:02d}h")

        self._ph_series = QBarSeries()
        self._ph_series.append(self._ph_bar_set)
        self._peak_chart.addSeries(self._ph_series)

        self._ph_axis_x = QBarCategoryAxis()
        self._ph_axis_x.append(categories)
        self._ph_axis_x.setLabelsColor(QColor(COLORS['text_muted']))
        self._peak_chart.addAxis(self._ph_axis_x, Qt.AlignBottom)
        self._ph_series.attachAxis(self._ph_axis_x)

        self._ph_axis_y = QValueAxis()
        self._ph_axis_y.setLabelsColor(QColor(COLORS['text_muted']))
        self._ph_axis_y.setGridLineColor(QColor(COLORS['border']))
        self._ph_axis_y.setLabelFormat("%d")
        self._peak_chart.addAxis(self._ph_axis_y, Qt.AlignLeft)
        self._ph_series.attachAxis(self._ph_axis_y)

    def _render_revenue_per_staff(self, data):
        self.revenue_staff_table.setRowCount(len(data))
        for r_idx, r in enumerate(data):
            vals = [
                r['full_name'], r['username'],
                str(r['transactions']),
                f"₱{float(r['revenue']):.2f}"
            ]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.revenue_staff_table.setItem(r_idx, c, item)
            self.revenue_staff_table.setRowHeight(r_idx, 40)

    def _export_report(self, fmt):
        from PyQt5.QtWidgets import QFileDialog
        from utils.export import export_transactions_pdf, export_transactions_excel
        from utils.database import get_transactions_for_export

        period_map = {
            "Today": "today", "Yesterday": "yesterday",
            "Weekly": "weekly", "Monthly": "monthly", "All": "all"
        }
        period = period_map.get(self.export_period.currentText(), "today")
        transactions = get_transactions_for_export(period)

        if not transactions:
            QMessageBox.information(self, "No Data",
                "No transactions found for the selected period.")
            return

        if fmt == 'pdf':
            path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF Report", f"parkease_report_{period}.pdf",
                "PDF Files (*.pdf)")
            if path:
                try:
                    export_transactions_pdf(transactions, period, path)
                    QMessageBox.information(self, "Exported", f"PDF report saved to:\n{path}")
                except Exception as e:
                    QMessageBox.warning(self, "Export Failed", str(e))
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Excel Report", f"parkease_report_{period}.xlsx",
                "Excel Files (*.xlsx)")
            if path:
                try:
                    export_transactions_excel(transactions, period, path)
                    QMessageBox.information(self, "Exported", f"Excel report saved to:\n{path}")
                except Exception as e:
                    QMessageBox.warning(self, "Export Failed", str(e))

    def _edit_transaction(self, txn):
        from utils.database import edit_transaction
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Transaction")
        dlg.setFixedSize(420, 340)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 24); lay.setSpacing(18)

        title = QLabel("Edit Transaction")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(title)

        sub = QLabel(f"Transaction: {txn['transaction_id']}")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        lay.addWidget(sub)

        def field(placeholder, current):
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            f.setText(str(current) if current else "")
            f.setStyleSheet(_field_style())
            return f

        form = QFormLayout(); form.setSpacing(14); form.setContentsMargins(0, 8, 0, 8)
        plate_input  = field("Plate number", txn.get('plate_number'))
        type_combo   = QComboBox()
        type_combo.addItems(["Car", "Motorcycle", "Bus", "Truck"])
        type_combo.setCurrentText(txn.get('vehicle_type', 'Car'))
        type_combo.setStyleSheet(f"""
            background: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 6px 10px;
        """)
        charge_input = field("Total charge", txn.get('total_charge'))
        form.addRow(QLabel("Plate Number:"), plate_input)
        form.addRow(QLabel("Vehicle Type:"), type_combo)
        form.addRow(QLabel("Total Charge:"), charge_input)
        lay.addLayout(form)

        err_lbl = QLabel("")
        err_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        err_lbl.hide(); lay.addWidget(err_lbl)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 9px 16px;
            }}
        """)
        cancel.clicked.connect(dlg.reject)
        save = QPushButton("Save Changes"); save.setStyleSheet(_btn_primary())

        def do_save():
            try:
                charge = float(charge_input.text()) if charge_input.text() else None
                edit_transaction(txn['transaction_id'],
                                 plate_number=plate_input.text().strip(),
                                 vehicle_type=type_combo.currentText(),
                                 total_charge=charge, admin_id=self.user['user_id'])
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Edit Transaction', f"Edited {txn['transaction_id']}")
                dlg.accept(); self._load_history()
            except Exception as e:
                err_lbl.setText(str(e)); err_lbl.show()

        save.clicked.connect(do_save)
        btns.addWidget(cancel); btns.addStretch(); btns.addWidget(save)
        lay.addLayout(btns)
        dlg.exec_()

    def _close_transaction(self, txn):
        from utils.database import manually_close_transaction
        reply = QMessageBox.question(
            self, "Close Transaction",
            f"Manually close transaction {txn['transaction_id']}?\n\n"
            f"Plate: {txn['plate_number']}\n"
            f"This will calculate the charge based on current time.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                result = manually_close_transaction(txn['transaction_id'], self.user['user_id'])
                if result:
                    log_activity('admin', self.user['user_id'], self.user['username'],
                                 'Manual Close',
                                 f"Closed {txn['transaction_id']} — ₱{result['total_charge']:.2f}")
                    QMessageBox.information(self, "Closed",
                        f"Transaction closed.\nDuration: {result['duration_minutes']} mins\n"
                        f"Charge: ₱{result['total_charge']:.2f}")
                    self._load_history()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2 — STAFF SETTINGS
    # ──────────────────────────────────────────────────────────────────────────

    def _build_staff(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("Staff Settings")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t); hdr.addStretch()
        add_btn = QPushButton("+ Add Staff"); add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(_btn_primary())
        add_btn.clicked.connect(self._add_staff)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # Currently On Shift
        sec1 = QLabel("CURRENTLY ON SHIFT")
        sec1.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(sec1)

        self.on_shift_frame = _card_frame()
        self.on_shift_layout = QVBoxLayout(self.on_shift_frame)
        self.on_shift_layout.setContentsMargins(16, 14, 16, 14)
        self.on_shift_layout.setSpacing(8)
        lay.addWidget(self.on_shift_frame)

        # All Staff — raw table with Actions column
        sec2 = QLabel("ALL STAFF")
        sec2.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(sec2)

        staff_search_row = QHBoxLayout()
        self.staff_search = QLineEdit()
        self.staff_search.setPlaceholderText("Search staff…")
        self.staff_search.setFixedHeight(36)
        self.staff_search.setStyleSheet(f"""
            background: {COLORS['bg_input']}; color: {COLORS['text']};
            border: 1px solid {COLORS['border']}; border-radius: 8px;
            padding: 0 12px; font-size: 13px;
        """)
        self.staff_search.textChanged.connect(self._filter_staff)
        staff_search_row.addWidget(self.staff_search); staff_search_row.addStretch()
        lay.addLayout(staff_search_row)

        self.staff_table = QTableWidget()
        self.staff_table.setColumnCount(8)
        self.staff_table.setHorizontalHeaderLabels(
            ["ID", "Full Name", "Username", "Status",
             "Discrepancy Stats", "Created At", "Created By", "Actions"])
        hdr2 = self.staff_table.horizontalHeader()
        hdr2.setSectionResizeMode(QHeaderView.Stretch)
        hdr2.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr2.setSectionResizeMode(7, QHeaderView.Fixed)
        self.staff_table.setColumnWidth(7, 160)
        self.staff_table.verticalHeader().setVisible(False)
        self.staff_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.staff_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.staff_table.setAlternatingRowColors(True)
        self.staff_table.setShowGrid(False)
        self.staff_table.setMaximumHeight(260)
        self.staff_table.setStyleSheet(_table_style())
        lay.addWidget(self.staff_table)

        # Login/Logout History
        hist_hdr = QHBoxLayout()
        sec3 = QLabel("LOGIN / LOGOUT HISTORY")
        sec3.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        hist_hdr.addWidget(sec3); hist_hdr.addStretch()

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
        self.shift_history_table.setStyleSheet(_table_style())
        lay.addWidget(self.shift_history_table)

        scroll.setWidget(page)
        return scroll

    def _load_staff(self):
        if getattr(self, '_staff_worker', None) and self._staff_worker.isRunning():
            return

        def fetch():
            return {
                'active': get_all_staff_with_current_shift(),
                'all':    get_all_staff(),
            }

        self._staff_worker = Worker(fetch)
        self._staff_worker.result.connect(self._on_staff_loaded)
        self._staff_worker.start()

    def _on_staff_loaded(self, data):
        try:
            while self.on_shift_layout.count():
                item = self.on_shift_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()

            active = data.get('active') or []
            if not active:
                lbl = QLabel("No staff currently on shift.")
                lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 13px;")
                self.on_shift_layout.addWidget(lbl)
            else:
                for s in active:
                    card = _card_frame()
                    cl = QHBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12)
                    dot = QFrame(); dot.setFixedSize(10, 10)
                    dot.setStyleSheet(f"background: {COLORS['success']}; border-radius: 5px; border: none;")
                    cl.addWidget(dot); cl.addSpacing(8)
                    name_lbl = QLabel(s['full_name'])
                    name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 700;")
                    cl.addWidget(name_lbl); cl.addSpacing(16)
                    start = s['shift_start']
                    start_s = start.strftime("%b %d, %Y  %H:%M") if isinstance(start, datetime) else "—"
                    since_lbl = QLabel(f"Since {start_s}")
                    since_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
                    cl.addWidget(since_lbl); cl.addStretch()
                    sys_total = float(s.get('current_collected') or 0)
                    total_lbl = QLabel(f"System Total:  ₱{sys_total:.2f}")
                    total_lbl.setStyleSheet(f"color: {COLORS['success']}; font-size: 13px; font-weight: 600;")
                    cl.addWidget(total_lbl)
                    self.on_shift_layout.addWidget(card)
        except Exception:
            pass

        try:
            self._staff_raw_list = data.get('all') or []
            self._render_staff(self._staff_raw_list)

            self.staff_combo.blockSignals(True)
            current = self.staff_combo.currentText()
            self.staff_combo.clear()
            self._staff_id_map = {}
            for r in self._staff_raw_list:
                self.staff_combo.addItem(r['full_name'])
                self._staff_id_map[r['full_name']] = r['id']
            idx = self.staff_combo.findText(current)
            self.staff_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.staff_combo.blockSignals(False)
        except Exception:
            pass

        self._load_shift_history()

    def _render_staff(self, data):
        self.staff_table.setRowCount(len(data))
        for row_idx, r in enumerate(data):
            is_active    = bool(r['is_active'])
            total_shifts = r.get('total_shifts', 0) or 0
            total_disc   = r.get('total_discrepancies', 0) or 0
            unresolved   = r.get('unresolved_discrepancies', 0) or 0

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

            vals = [r['id'], r['full_name'], r['username'],
                    "Active" if is_active else "Inactive",
                    disc_stat, ca_s, r.get('created_by_name') or '—']

            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val) if val is not None else '—')
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if unresolved > 0:
                    item.setForeground(QColor(COLORS['danger']))
                elif total_disc > 0:
                    item.setForeground(QColor(COLORS['warning']))
                self.staff_table.setItem(row_idx, c, item)

            self.staff_table.setRowHeight(row_idx, 68)

            btn_widget = QWidget()
            btn_lay = QHBoxLayout(btn_widget)
            btn_lay.setContentsMargins(4, 12, 4, 12)
            btn_lay.setSpacing(4)

            toggle_btn = QPushButton("Deactivate" if is_active else "Activate")
            toggle_btn.setFixedHeight(44)
            color = COLORS['warning'] if is_active else COLORS['success']
            toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color}; color: white; border: none;
                    border-radius: 4px; font-size: 11px; padding: 0 10px;
                }}
                QPushButton:hover {{ opacity: 0.85; }}
            """)
            toggle_btn.clicked.connect(
                lambda _, sid=r['id'], active=is_active: self._toggle_staff_active(sid, active))
            btn_lay.addWidget(toggle_btn)
            self.staff_table.setCellWidget(row_idx, 7, btn_widget)

    def _filter_staff(self, text):
        if not hasattr(self, '_staff_raw_list'):
            return
        if not text:
            self._render_staff(self._staff_raw_list); return
        text = text.lower()
        filtered = [r for r in self._staff_raw_list
                    if any(text in str(v).lower() for v in r.values())]
        self._render_staff(filtered)

    def _toggle_staff_active(self, staff_id, currently_active):
        new_state = not currently_active
        action = "Deactivate" if currently_active else "Activate"
        reply = QMessageBox.question(
            self, f"{action} Staff",
            f"Are you sure you want to {action.lower()} this staff account?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                set_staff_active(staff_id, new_state)
                log_activity('admin', self.user['user_id'], self.user['username'],
                             f'{action} Staff', f"Staff ID {staff_id} {action.lower()}d")
                self._load_staff()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _load_shift_history(self):
        name = self.staff_combo.currentText()
        if not name or not hasattr(self, '_staff_id_map'):
            return
        staff_id = self._staff_id_map.get(name)
        if not staff_id:
            return

        if getattr(self, '_shift_hist_worker', None) and self._shift_hist_worker.isRunning():
            return

        def fetch():
            return get_staff_login_logout_history(staff_id)

        self._shift_hist_worker = Worker(fetch)
        self._shift_hist_worker.result.connect(
            lambda shifts: self._render_shift_history(shifts, staff_id))
        self._shift_hist_worker.start()

    def _render_shift_history(self, shifts, staff_id):
        try:
            self.shift_history_table.setRowCount(len(shifts))

            for r, sh in enumerate(shifts):
                start   = sh['shift_start']; end = sh['shift_end']
                sys_rev = float(sh.get('system_revenue') or 0)
                rep_rev = float(sh.get('staff_reported_revenue') or 0)
                flagged = sh.get('is_flagged', False)
                vehicles = sh.get('vehicles_handled', 0)
                is_active = end is None

                date_s = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else "—"
                tin_s  = start.strftime("%H:%M")    if isinstance(start, datetime) else "—"
                tout_s = end.strftime("%H:%M")       if isinstance(end,   datetime) else "On Shift"
                disc   = sys_rev - rep_rev

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
                        item.setForeground(QColor(COLORS['warning']))
                    elif is_active:
                        item.setForeground(QColor(COLORS['warning']))
                    self.shift_history_table.setItem(r, c, item)

                if flagged and not is_resolved and not is_active:
                    resolve_btn = QPushButton("Resolve"); resolve_btn.setFixedHeight(28)
                    resolve_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {COLORS['success']}; color: white; border: none;
                            border-radius: 5px; font-size: 11px; font-weight: 600; padding: 0 10px;
                        }}
                        QPushButton:hover {{ background: #059669; }}
                    """)
                    resolve_btn.clicked.connect(
                        lambda _, sid=staff_id, shid=sh['id']: self._resolve_flag(sid, shid))
                    self.shift_history_table.setCellWidget(r, 7, resolve_btn)
                else:
                    self.shift_history_table.setCellWidget(r, 7, None)

            self.shift_history_table.resizeRowsToContents()
        except Exception:
            pass

    def _resolve_flag(self, staff_id, shift_id):
        reply = QMessageBox.question(
            self, "Resolve Discrepancy",
            "Mark this shift's discrepancy as reviewed?\n\n"
            "The record will be kept but marked as resolved.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                remaining = resolve_staff_flag(staff_id, shift_id)
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Resolved Discrepancy',
                             f"Shift ID {shift_id} resolved for staff ID {staff_id}. "
                             f"{remaining} unresolved remaining.")
                self._load_staff()
                msg = ("All discrepancies cleared — staff flag removed."
                       if remaining == 0
                       else f"{remaining} other discrepancy/ies still pending.")
                QMessageBox.information(self, "Resolved",
                    f"Discrepancy marked as resolved.\n{msg}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_staff(self):
        dlg = AddStaffDialog(self.user['user_id'], self.user['username'], self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_staff()
            QMessageBox.information(self, "Success", "Staff account created successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3 — SETTINGS
    # ──────────────────────────────────────────────────────────────────────────

    def _build_settings(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("System Settings")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t); hdr.addStretch()
        save_btn = QPushButton("Save Settings"); save_btn.setFixedHeight(36)
        save_btn.setStyleSheet(_btn_primary())
        save_btn.clicked.connect(self._save_settings)
        hdr.addWidget(save_btn)
        lay.addLayout(hdr)

        # ── Parking Rates card ────────────────────────────────────────────────
        rates_card = _card_frame()
        rc_lay = QVBoxLayout(rates_card)
        rc_lay.setContentsMargins(24, 20, 24, 20)
        rc_lay.setSpacing(16)
        rc_title = QLabel("Parking Rates")
        rc_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 15px; font-weight: 700;")
        rc_lay.addWidget(rc_title)

        form = QFormLayout(); form.setSpacing(14); form.setContentsMargins(0, 0, 0, 0)

        lbl_style = f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 600;"

        rate_type_container = QWidget()
        rate_type_container.setStyleSheet("background: transparent; border: none;")
        rt_lay = QVBoxLayout(rate_type_container)
        rt_lay.setContentsMargins(0, 0, 0, 0)
        rt_lay.setSpacing(5)

        self.settings_rate_type = QComboBox()
        self.settings_rate_type.addItems(["Hourly", "Flat", "Daily Max"])
        self.settings_rate_type.setStyleSheet(_field_style())
        rt_lay.addWidget(self.settings_rate_type)

        rate_hint = QLabel(
            "<b>Hourly</b> — charges Rate per Hour for each hour parked.  "
            "<b>Flat</b> — charges a single fixed Flat Rate regardless of duration.  "
            "<b>Daily Max</b> — charges Rate per Hour but never exceeds Daily Max Rate per day."
        )
        rate_hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        rate_hint.setWordWrap(True)
        rt_lay.addWidget(rate_hint)

        form.addRow(_lbl("Rate Type:", lbl_style), rate_type_container)

        self.settings_rate_hour = QLineEdit(); self.settings_rate_hour.setStyleSheet(_field_style())
        form.addRow(_lbl("Rate per Hour (₱):", lbl_style), self.settings_rate_hour)

        self.settings_flat_rate = QLineEdit(); self.settings_flat_rate.setStyleSheet(_field_style())
        form.addRow(_lbl("Flat Rate (₱):", lbl_style), self.settings_flat_rate)

        self.settings_daily_max = QLineEdit(); self.settings_daily_max.setStyleSheet(_field_style())
        form.addRow(_lbl("Daily Max Rate (₱):", lbl_style), self.settings_daily_max)

        self.settings_min_charge = QLineEdit(); self.settings_min_charge.setStyleSheet(_field_style())
        form.addRow(_lbl("Minimum Charge (₱):", lbl_style), self.settings_min_charge)

        self.settings_capacity = QLineEdit(); self.settings_capacity.setStyleSheet(_field_style())
        form.addRow(_lbl("Parking Capacity (slots):", lbl_style), self.settings_capacity)

        self.settings_overstay = QLineEdit(); self.settings_overstay.setStyleSheet(_field_style())
        form.addRow(_lbl("Overstay Threshold (hours):", lbl_style), self.settings_overstay)

        rc_lay.addLayout(form)
        lay.addWidget(rates_card)

        # ── Camera Settings card ──────────────────────────────────────────────
        cam_card = _card_frame()
        cam_lay = QVBoxLayout(cam_card)
        cam_lay.setContentsMargins(24, 20, 24, 20)
        cam_lay.setSpacing(16)
        cam_title = QLabel("Camera Settings")
        cam_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 15px; font-weight: 700;")
        cam_lay.addWidget(cam_title)

        cam_options = ["0 — Built-in webcam", "1 — External camera 1", "2 — External camera 2"]

        cam_form = QFormLayout(); cam_form.setSpacing(14); cam_form.setContentsMargins(0, 0, 0, 0)

        # Entry camera row
        entry_container = QWidget(); entry_container.setStyleSheet("background: transparent; border: none;")
        entry_row = QHBoxLayout(entry_container); entry_row.setContentsMargins(0, 0, 0, 0); entry_row.setSpacing(8)
        self.settings_entry_cam = QComboBox(); self.settings_entry_cam.addItems(cam_options)
        entry_test_btn = QPushButton("Test"); entry_test_btn.setFixedSize(60, 36)
        entry_test_btn.setProperty("btnStyle", "compact")
        entry_test_btn.clicked.connect(lambda: self._test_camera(
            self.settings_entry_cam.currentIndex(),
            self.settings_demo_video.text().strip() or None))
        entry_row.addWidget(self.settings_entry_cam); entry_row.addWidget(entry_test_btn)
        cam_form.addRow(_lbl("Entry Camera:", lbl_style), entry_container)

        # Exit camera row
        exit_container = QWidget(); exit_container.setStyleSheet("background: transparent; border: none;")
        exit_row = QHBoxLayout(exit_container); exit_row.setContentsMargins(0, 0, 0, 0); exit_row.setSpacing(8)
        self.settings_exit_cam = QComboBox(); self.settings_exit_cam.addItems(cam_options)
        exit_test_btn = QPushButton("Test"); exit_test_btn.setFixedSize(60, 36)
        exit_test_btn.setProperty("btnStyle", "compact")
        exit_test_btn.clicked.connect(lambda: self._test_camera(
            self.settings_exit_cam.currentIndex(),
            self.settings_demo_video.text().strip() or None))
        exit_row.addWidget(self.settings_exit_cam); exit_row.addWidget(exit_test_btn)
        cam_form.addRow(_lbl("Exit Camera:", lbl_style), exit_container)

        # Demo video path row
        demo_container = QWidget(); demo_container.setStyleSheet("background: transparent; border: none;")
        demo_row = QHBoxLayout(demo_container); demo_row.setContentsMargins(0, 0, 0, 0); demo_row.setSpacing(8)
        self.settings_demo_video = QLineEdit()
        self.settings_demo_video.setPlaceholderText("Leave empty to use live camera")
        browse_btn = QPushButton("Browse"); browse_btn.setFixedSize(80, 36)
        browse_btn.setProperty("btnStyle", "compact")
        browse_btn.clicked.connect(self._browse_demo_video)
        demo_row.addWidget(self.settings_demo_video); demo_row.addWidget(browse_btn)
        cam_form.addRow(_lbl("Demo Video Path:", lbl_style), demo_container)

        cam_lay.addLayout(cam_form)

        demo_hint = QLabel("Leave empty to use live camera. Enter full file path to use a video file for demo/testing.")
        demo_hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        demo_hint.setWordWrap(True)
        cam_lay.addWidget(demo_hint)

        lay.addWidget(cam_card)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    def _load_settings(self):
        try:
            s = get_settings()
            if not s:
                return
            _to_display = {"hourly": "Hourly", "flat": "Flat", "daily_max": "Daily Max"}
            display_val = _to_display.get(s.get('rate_type', 'hourly'), "Hourly")
            idx = self.settings_rate_type.findText(display_val)
            if idx >= 0:
                self.settings_rate_type.setCurrentIndex(idx)
            self.settings_rate_hour.setText(str(s.get('rate_per_hour', '') or ''))
            self.settings_flat_rate.setText(str(s.get('flat_rate', '') or ''))
            self.settings_daily_max.setText(str(s.get('daily_max_rate', '') or ''))
            self.settings_min_charge.setText(str(s.get('minimum_charge', '') or ''))
            self.settings_capacity.setText(str(s.get('parking_capacity', '') or ''))
            self.settings_overstay.setText(str(s.get('overstay_hours', '') or ''))
            entry_idx = min(int(s.get('entry_camera_index', 0) or 0), self.settings_entry_cam.count() - 1)
            self.settings_entry_cam.setCurrentIndex(max(0, entry_idx))
            exit_idx = min(int(s.get('exit_camera_index', 1) or 0), self.settings_exit_cam.count() - 1)
            self.settings_exit_cam.setCurrentIndex(max(0, exit_idx))
            self.settings_demo_video.setText(s.get('demo_video_path', '') or '')

        except Exception:
            pass

    def _save_settings(self):
        try:
            _to_db = {"Hourly": "hourly", "Flat": "flat", "Daily Max": "daily_max"}
            kwargs = dict(
                rate_type=_to_db.get(self.settings_rate_type.currentText(), "hourly"),
            )
            def _to_float(text, key):
                t = text.strip()
                if t:
                    kwargs[key] = float(t)
            def _to_int(text, key):
                t = text.strip()
                if t:
                    kwargs[key] = int(t)
            _to_float(self.settings_rate_hour.text(), 'rate_per_hour')
            _to_float(self.settings_flat_rate.text(), 'flat_rate')
            _to_float(self.settings_daily_max.text(), 'daily_max_rate')
            _to_float(self.settings_min_charge.text(), 'minimum_charge')
            _to_int(self.settings_capacity.text(), 'parking_capacity')
            _to_int(self.settings_overstay.text(), 'overstay_hours')
            kwargs['entry_camera_index'] = self.settings_entry_cam.currentIndex()
            kwargs['exit_camera_index'] = self.settings_exit_cam.currentIndex()
            kwargs['demo_video_path'] = self.settings_demo_video.text().strip()
            update_settings(**kwargs)
            log_activity('admin', self.user['user_id'], self.user['username'],
                         'Update Settings', str(kwargs))
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Please check numeric fields:\n{e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _browse_demo_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Demo Video", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;All Files (*)"
        )
        if path:
            self.settings_demo_video.setText(path)

    def _test_camera(self, camera_index, video_file=None):
        dlg = CameraPreviewDialog(camera_index, video_file, self)
        dlg.exec_()

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 4 — BLACKLIST
    # ──────────────────────────────────────────────────────────────────────────

    def _build_blacklist(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        t = QLabel("Plate Blacklist")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t); hdr.addStretch()
        add_btn = QPushButton("+ Add to Blacklist"); add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(_btn_primary())
        add_btn.clicked.connect(self._add_blacklist)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        sub = QLabel("Vehicles on this list will be denied entry. The staff will see an alert when a blacklisted plate is detected.")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self.blacklist_table = QTableWidget()
        self.blacklist_table.setColumnCount(5)
        self.blacklist_table.setHorizontalHeaderLabels(
            ["Plate Number", "Reason", "Added By", "Added At", "Actions"])
        blh = self.blacklist_table.horizontalHeader()
        blh.setSectionResizeMode(QHeaderView.Stretch)
        blh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.blacklist_table.setColumnWidth(4, 120)
        self.blacklist_table.verticalHeader().setVisible(False)
        self.blacklist_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.blacklist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.blacklist_table.setAlternatingRowColors(True)
        self.blacklist_table.setShowGrid(False)
        self.blacklist_table.setStyleSheet(_table_style())
        lay.addWidget(self.blacklist_table)

        return page

    def _load_blacklist(self):
        try:
            data = get_blacklist()
            self.blacklist_table.setRowCount(len(data))
            for r_idx, r in enumerate(data):
                added_at = r.get('added_at')
                at_s = added_at.strftime("%Y-%m-%d %H:%M") if isinstance(added_at, datetime) else str(added_at or '—')
                vals = [
                    r.get('plate_number', '—'),
                    r.get('reason', '—'),
                    r.get('added_by_name', '—'),
                    at_s,
                    ''
                ]
                for c, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.blacklist_table.setItem(r_idx, c, item)
                self.blacklist_table.setRowHeight(r_idx, 68)

                rm_btn = QPushButton("Remove")
                rm_btn.setFixedHeight(44)
                rm_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['danger']}; color: white; border: none;
                        border-radius: 4px; font-size: 11px; padding: 0 10px;
                    }}
                    QPushButton:hover {{ background: #DC2626; }}
                """)
                rm_btn.clicked.connect(
                    lambda _, plate=r['plate_number']: self._remove_blacklist(plate))
                btn_w = QWidget(); bl = QHBoxLayout(btn_w)
                bl.setContentsMargins(4, 12, 4, 12)
                bl.addWidget(rm_btn)
                self.blacklist_table.setCellWidget(r_idx, 4, btn_w)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _add_blacklist(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add to Blacklist")
        dlg.setFixedSize(400, 260)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}")

        lay = QVBoxLayout(dlg); lay.setContentsMargins(28, 24, 28, 24); lay.setSpacing(14)
        title = QLabel("Add Plate to Blacklist")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(12)
        plate_input = QLineEdit(); plate_input.setPlaceholderText("e.g. ABC1234")
        plate_input.setStyleSheet(_field_style())
        reason_input = QLineEdit(); reason_input.setPlaceholderText("Reason for blacklisting")
        reason_input.setStyleSheet(_field_style())
        form.addRow(_lbl("Plate Number:"), plate_input)
        form.addRow(_lbl("Reason:"),       reason_input)
        lay.addLayout(form)

        err_lbl = QLabel(""); err_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        err_lbl.hide(); lay.addWidget(err_lbl)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 9px 16px;
            }}
        """)
        cancel.clicked.connect(dlg.reject)
        add = QPushButton("Add to Blacklist"); add.setStyleSheet(_btn_primary())

        def do_add():
            plate  = plate_input.text().strip().upper()
            reason = reason_input.text().strip()
            if not plate:
                err_lbl.setText("Plate number is required."); err_lbl.show(); return
            try:
                add_to_blacklist(plate, reason, self.user['user_id'])
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Blacklist Add', f"Plate {plate}: {reason}")
                dlg.accept(); self._load_blacklist()
            except ValueError as e:
                err_lbl.setText(str(e)); err_lbl.show()
            except Exception as e:
                err_lbl.setText(f"Error: {e}"); err_lbl.show()

        add.clicked.connect(do_add)
        btns.addWidget(cancel); btns.addStretch(); btns.addWidget(add)
        lay.addLayout(btns)
        dlg.exec_()

    def _remove_blacklist(self, plate):
        reply = QMessageBox.question(
            self, "Remove from Blacklist",
            f"Remove {plate} from the blacklist?\nThey will be allowed entry again.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                remove_from_blacklist(plate)
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Blacklist Remove', f"Plate {plate} removed")
                self._load_blacklist()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 5 — RESERVED VEHICLES
    # ──────────────────────────────────────────────────────────────────────────

    def _build_reserved(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        t = QLabel("Reserved / Monthly Vehicles")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t); hdr.addStretch()
        add_btn = QPushButton("+ Add Reserved Vehicle"); add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(_btn_primary())
        add_btn.clicked.connect(self._add_reserved)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        sub = QLabel("Reserved vehicles are monthly parkers. They are charged ₱0 on exit.")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        lay.addWidget(sub)

        self.reserved_table = QTableWidget()
        self.reserved_table.setColumnCount(7)
        self.reserved_table.setHorizontalHeaderLabels(
            ["Plate", "Owner", "Contact", "Monthly Fee", "Start", "Expiry", "Actions"])
        rh = self.reserved_table.horizontalHeader()
        rh.setSectionResizeMode(QHeaderView.Stretch)
        rh.setSectionResizeMode(6, QHeaderView.Fixed)
        self.reserved_table.setColumnWidth(6, 120)
        self.reserved_table.verticalHeader().setVisible(False)
        self.reserved_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.reserved_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.reserved_table.setAlternatingRowColors(True)
        self.reserved_table.setShowGrid(False)
        self.reserved_table.setStyleSheet(_table_style())
        lay.addWidget(self.reserved_table)

        return page

    def _load_reserved(self):
        try:
            data = get_reserved_vehicles()
            self.reserved_table.setRowCount(len(data))
            for r_idx, r in enumerate(data):
                start  = r.get('start_date')
                expiry = r.get('expiry_date')
                start_s  = start.strftime("%Y-%m-%d")  if hasattr(start,  'strftime') else str(start or '—')
                expiry_s = expiry.strftime("%Y-%m-%d") if hasattr(expiry, 'strftime') else str(expiry or '—')
                vals = [
                    r.get('plate_number', '—'),
                    r.get('owner_name', '—'),
                    r.get('contact_number', '—'),
                    f"₱{float(r.get('monthly_fee') or 0):.2f}",
                    start_s, expiry_s, ''
                ]
                for c, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.reserved_table.setItem(r_idx, c, item)
                self.reserved_table.setRowHeight(r_idx, 68)

                rm_btn = QPushButton("Remove")
                rm_btn.setFixedHeight(44)
                rm_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['danger']}; color: white; border: none;
                        border-radius: 4px; font-size: 11px; padding: 0 10px;
                    }}
                    QPushButton:hover {{ background: #DC2626; }}
                """)
                rm_btn.clicked.connect(
                    lambda _, plate=r['plate_number']: self._remove_reserved(plate))
                btn_w = QWidget(); rl = QHBoxLayout(btn_w)
                rl.setContentsMargins(4, 12, 4, 12)
                rl.addWidget(rm_btn)
                self.reserved_table.setCellWidget(r_idx, 6, btn_w)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _add_reserved(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Reserved Vehicle")
        dlg.setFixedSize(460, 420)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}")

        lay = QVBoxLayout(dlg); lay.setContentsMargins(28, 24, 28, 24); lay.setSpacing(14)
        title = QLabel("Add Monthly/Reserved Vehicle")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(12)

        def fld(ph=''):
            f = QLineEdit(); f.setPlaceholderText(ph); f.setStyleSheet(_field_style()); return f

        plate_input   = fld("e.g. ABC1234")
        owner_input   = fld("Owner full name")
        contact_input = fld("e.g. 09XXXXXXXXX")
        fee_input     = fld("e.g. 500.00")

        start_edit  = QDateEdit(QDate.currentDate())
        start_edit.setCalendarPopup(True)
        start_edit.setStyleSheet(_field_style())

        expiry_edit = QDateEdit(QDate.currentDate().addMonths(1))
        expiry_edit.setCalendarPopup(True)
        expiry_edit.setStyleSheet(_field_style())

        form.addRow(_lbl("Plate Number:"),  plate_input)
        form.addRow(_lbl("Owner Name:"),    owner_input)
        form.addRow(_lbl("Contact:"),       contact_input)
        form.addRow(_lbl("Monthly Fee (₱):"), fee_input)
        form.addRow(_lbl("Start Date:"),    start_edit)
        form.addRow(_lbl("Expiry Date:"),   expiry_edit)
        lay.addLayout(form)

        err_lbl = QLabel(""); err_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        err_lbl.hide(); lay.addWidget(err_lbl)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 9px 16px;
            }}
        """)
        cancel.clicked.connect(dlg.reject)
        add = QPushButton("Add Vehicle"); add.setStyleSheet(_btn_primary())

        def do_add():
            plate   = plate_input.text().strip().upper()
            owner   = owner_input.text().strip()
            contact = contact_input.text().strip()
            fee_txt = fee_input.text().strip()
            if not plate or not owner:
                err_lbl.setText("Plate and owner name are required."); err_lbl.show(); return
            try:
                fee = float(fee_txt) if fee_txt else 0.0
                start  = start_edit.date().toPyDate()
                expiry = expiry_edit.date().toPyDate()
                add_reserved_vehicle(
                    plate, owner, contact, fee, start, expiry,
                    'admin', self.user['user_id']
                )
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Reserved Add', f"Plate {plate} — {owner}")
                dlg.accept(); self._load_reserved()
            except ValueError as e:
                err_lbl.setText(str(e)); err_lbl.show()
            except Exception as e:
                err_lbl.setText(f"Error: {e}"); err_lbl.show()

        add.clicked.connect(do_add)
        btns.addWidget(cancel); btns.addStretch(); btns.addWidget(add)
        lay.addLayout(btns)
        dlg.exec_()

    def _remove_reserved(self, plate):
        reply = QMessageBox.question(
            self, "Remove Reserved Vehicle",
            f"Remove {plate} from reserved vehicles?\nThey will be charged normally on exit.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                remove_reserved_vehicle(plate)
                log_activity('admin', self.user['user_id'], self.user['username'],
                             'Reserved Remove', f"Plate {plate} removed")
                self._load_reserved()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

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


# ─── MODULE-LEVEL HELPERS ─────────────────────────────────────────────────────

def _lbl(text, style=None):
    l = QLabel(text)
    if style:
        l.setStyleSheet(style)
    return l
