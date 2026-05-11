# modules/staff_window.py

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QStackedWidget, QFrame,
                              QScrollArea, QSizePolicy, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QFont

from utils.styles import COLORS
from utils.database import (log_vehicle_entry, log_vehicle_exit,
                             get_active_vehicles, get_completed_transactions,
                             find_active_vehicle_by_plate, log_activity, end_shift)
from utils.detection import CameraWorker, load_models
from modules.widgets import (SideNav, StatCard, SearchableTable, SectionLabel,
                              ManualInputDialog, ExitConfirmDialog, BlindDropDialog)

from datetime import datetime


class StaffWindow(QMainWindow):
    def __init__(self, user_info: dict, on_logout=None):
        super().__init__()
        self.user = user_info
        self.on_logout = on_logout
        self.setWindowTitle(f"ParkEase — Staff Panel  ({user_info['full_name']})")
        self.setMinimumSize(1200, 750)
        self.resize(1280, 800)

        # Load AI models (background, errors are non-fatal)
        self._model_errors = load_models()

        self._entry_count = 0
        self._exit_count  = 0
        self._recent_entries = []
        self._recent_exits   = []

        self._build_ui()
        self._start_cameras()

        # Auto-refresh tables every 30 s
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_tables)
        self._refresh_timer.start(30_000)

    # ──────────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.setStyleSheet(f"background-color: {COLORS['bg']}; color: {COLORS['text']};")

        nav_items = [
            ("", "Live Dashboard"),
            ("", "Active Parking"),
            ("", "Completed Txns"),
        ]
        self.nav = SideNav(nav_items, self.user)
        self.nav.page_changed.connect(self._switch_page)

        # Logout button at bottom of nav
        logout_btn = QPushButton("Logout")
        logout_btn.setFixedHeight(42)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['danger']};
                border: 1px solid {COLORS['danger']}20; border-radius: 8px;
                padding: 0 14px; text-align: left; font-size: 13px;
                margin: 0 0 0 0;
            }}
            QPushButton:hover {{ background: {COLORS['danger']}15; }}
        """)
        logout_btn.clicked.connect(self._logout)
        self.nav.layout().addWidget(logout_btn)

        root.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {COLORS['bg']};")
        root.addWidget(self.stack)

        self.page_dashboard   = self._build_dashboard()
        self.page_active      = self._build_active_page()
        self.page_completed   = self._build_completed_page()

        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_active)
        self.stack.addWidget(self.page_completed)

        self.nav.select(0)

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        if idx == 1:
            self._load_active()
        elif idx == 2:
            self._load_completed()

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1 — LIVE DASHBOARD
    # ──────────────────────────────────────────────────────────────────────────

    def _build_dashboard(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("Live Monitoring Dashboard")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()
        self.clock_lbl = QLabel()
        self.clock_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        hdr.addWidget(self.clock_lbl)
        lay.addLayout(hdr)

        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(1000)
        self._update_clock()

        if self._model_errors:
            warn = QLabel("⚠  " + "  |  ".join(self._model_errors) + "  — detection limited")
            warn.setStyleSheet(f"""
                background: {COLORS['warning']}20; color: {COLORS['warning']};
                border: 1px solid {COLORS['warning']}40; border-radius: 7px;
                padding: 8px 14px; font-size: 12px;
            """)
            lay.addWidget(warn)

        # Camera feeds
        cam_row = QHBoxLayout()
        cam_row.setSpacing(14)

        self.entry_cam_lbl = self._camera_placeholder("ENTRY CAM", COLORS['success'])
        self.exit_cam_lbl  = self._camera_placeholder("EXIT CAM",  COLORS['primary'])

        self.entry_toggle = QPushButton("⏹ Stop Entry Cam")
        self.entry_toggle.setFixedHeight(32)
        self.entry_toggle.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['danger']}; color: white; border: none;
                border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
            QPushButton:hover {{ background: #DC2626; }}
        """)
        self.entry_toggle.clicked.connect(self._toggle_entry_cam)
        self._entry_cam_on = True

        self.exit_toggle = QPushButton("⏹ Stop Exit Cam")
        self.exit_toggle.setFixedHeight(32)
        self.exit_toggle.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['danger']}; color: white; border: none;
                border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
            QPushButton:hover {{ background: #DC2626; }}
        """)
        self.exit_toggle.clicked.connect(self._toggle_exit_cam)
        self._exit_cam_on = True

        entry_card = self._cam_card("Entry Camera", self.entry_cam_lbl, self.entry_toggle)
        exit_card  = self._cam_card("Exit Camera",  self.exit_cam_lbl,  self.exit_toggle)
        cam_row.addWidget(entry_card)
        cam_row.addWidget(exit_card)
        lay.addLayout(cam_row)

        # Summary row
        
        sum_row = QHBoxLayout()
        sum_row.setSpacing(14)

        self.entry_card = StatCard("ENTRIES TODAY", "0", accent=COLORS['success'])
        self.exit_card2  = StatCard("EXITS TODAY",   "0", accent=COLORS['primary'])
        sum_row.addWidget(self.entry_card)
        sum_row.addWidget(self.exit_card2)
        lay.addLayout(sum_row)

        # Recent lists
        lists_row = QHBoxLayout()
        lists_row.setSpacing(14)

        self.recent_entry_frame = self._build_recent_frame("Recent Entries", COLORS['success'])
        self.recent_exit_frame  = self._build_recent_frame("Recent Exits",  COLORS['primary'])
        lists_row.addWidget(self.recent_entry_frame['widget'])
        lists_row.addWidget(self.recent_exit_frame['widget'])
        lay.addLayout(lists_row)

        return page

    def _camera_placeholder(self, label, color):
        lbl = QLabel(f"📷  {label}\nCamera loading…")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedHeight(280)
        lbl.setStyleSheet(f"""
            background-color: {COLORS['bg']};
            color: {COLORS['text_muted']}; font-size: 13px;
            border-radius: 8px;
        """)
        return lbl

    def _cam_card(self, title, cam_lbl, toggle_btn=None):
        card = QFrame()
        card.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 12px;
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(8)

        hdr = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        hdr.addWidget(t)
        hdr.addStretch()
        if toggle_btn:
            hdr.addWidget(toggle_btn)
        cl.addLayout(hdr)
        cl.addWidget(cam_lbl)
        return card

    def _build_recent_frame(self, title, accent):
        card = QFrame()
        card.setStyleSheet(f"""
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 12px;
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        hdr = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        bar = QFrame(); bar.setFixedSize(12, 12)
        bar.setStyleSheet(f"background: {accent}; border-radius: 6px;")
        hdr.addWidget(bar); hdr.addWidget(t); hdr.addStretch()
        cl.addLayout(hdr)

        rows_widget = QWidget()
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)

        empty = QLabel("No vehicles yet")
        empty.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        rows_layout.addWidget(empty)

        cl.addWidget(rows_widget)
        return {'widget': card, 'layout': rows_layout}

    def _update_recent_list(self, frame_dict, items, is_exit=False):
        lay = frame_dict['layout']
        while lay.count():
            w = lay.takeAt(0).widget()
            if w: w.deleteLater()

        if not items:
            lbl = QLabel("No vehicles yet")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
            lay.addWidget(lbl)
            return

        for item in items[:3]:
            row = QFrame()
            row.setStyleSheet(f"""
                background: {COLORS['bg_input']}; border-radius: 7px;
                border: 1px solid {COLORS['border']};
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)

            plate = QLabel(item.get('plate_number', '—'))
            plate.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: 700;")
            rl.addWidget(plate)

            vtype = QLabel(item.get('vehicle_type', '—'))
            vtype.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
            rl.addWidget(vtype)
            rl.addStretch()

            ts_key = 'time_out' if is_exit else 'time_in'
            ts = item.get(ts_key)
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%H:%M")
            else:
                ts_str = str(ts)[:5] if ts else '—'
            ts_lbl = QLabel(ts_str)
            ts_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
            rl.addWidget(ts_lbl)

            lay.addWidget(row)

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2 — ACTIVE PARKING
    # ──────────────────────────────────────────────────────────────────────────

    def _build_active_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        t = QLabel("Active Parking List")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()
        ref_btn = QPushButton("↻  Refresh")
        ref_btn.setFixedSize(100, 34)
        ref_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; color: {COLORS['text']}; }}
        """)
        ref_btn.clicked.connect(self._load_active)
        hdr.addWidget(ref_btn)
        lay.addLayout(hdr)

        cols = ["Txn ID", "Plate", "Type", "Time In", "Date", "Staff (Entry)", "Flagged"]
        self.active_table = SearchableTable(cols)
        lay.addWidget(self.active_table)

        return page

    def _load_active(self):
        rows_raw = get_active_vehicles()
        rows = []
        for r in rows_raw:
            ti = r['time_in']
            ti_str = ti.strftime("%H:%M:%S") if isinstance(ti, datetime) else str(ti)
            di = r['date_in']
            di_str = di.strftime("%Y-%m-%d") if hasattr(di, 'strftime') else str(di)
            flag = "⚑ Flagged" if r.get('is_flagged') else ""
            rows.append([
                r['transaction_id'],
                r['plate_number'],
                r['vehicle_type'],
                ti_str, di_str,
                r.get('staff_name') or '—',
                flag
            ])
        self.active_table.load_data(rows)

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3 — COMPLETED TRANSACTIONS
    # ──────────────────────────────────────────────────────────────────────────

    def _build_completed_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        t = QLabel("Completed Transactions")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()
        lay.addLayout(hdr)

        cols = ["Txn ID", "Plate", "Date", "Time In", "Time Out", "Duration", "Staff (Exit)", "Total (₱)"]
        self.completed_table = SearchableTable(cols)
        lay.addWidget(self.completed_table)

        return page

    def _load_completed(self):
        rows_raw = get_completed_transactions()
        rows = []
        for r in rows_raw:
            ti = r['time_in']; to = r['time_out']
            ti_s = ti.strftime("%H:%M:%S") if isinstance(ti, datetime) else str(ti)
            to_s = to.strftime("%H:%M:%S") if isinstance(to, datetime) else str(to)
            di   = r['date_in']
            di_s = di.strftime("%Y-%m-%d") if hasattr(di, 'strftime') else str(di)
            mins = r.get('duration_minutes', 0) or 0
            h, m = divmod(mins, 60)
            dur  = f"{h}h {m}m"
            rows.append([
                r['transaction_id'], r['plate_number'],
                di_s, ti_s, to_s, dur,
                r.get('staff_exit_name') or '—',
                f"₱{r['total_charge']:.2f}" if r.get('total_charge') else '—'
            ])
        self.completed_table.load_data(rows)

    # ──────────────────────────────────────────────────────────────────────────
    # CAMERA WORKERS
    # ──────────────────────────────────────────────────────────────────────────

    def _start_cameras(self):
        # Both entry and exit use the same built-in camera (index 0)
        self.entry_worker = CameraWorker(camera_index=0, mode='entry')
        self.entry_worker.frame_ready.connect(self._update_entry_frame)
        self.entry_worker.vehicle_detected.connect(self._on_entry_detected)
        self.entry_worker.ocr_failed.connect(self._on_entry_ocr_failed)
        self.entry_worker.error_signal.connect(self._on_cam_error)

        self.exit_worker = CameraWorker(camera_index=0, mode='exit')
        self.exit_worker.frame_ready.connect(self._update_exit_frame)
        self.exit_worker.vehicle_detected.connect(self._on_exit_detected)
        self.exit_worker.ocr_failed.connect(lambda: None)  # exits just log unknown
        self.exit_worker.error_signal.connect(self._on_cam_error)

        self._entry_cam_on = False
        self._exit_cam_on = False


    @pyqtSlot(QImage)
    def _update_entry_frame(self, img):
        if self.stack.currentIndex() == 0:
            pix = QPixmap.fromImage(img).scaled(
                self.entry_cam_lbl.width(), self.entry_cam_lbl.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.entry_cam_lbl.setPixmap(pix)

    @pyqtSlot(QImage)
    def _update_exit_frame(self, img):
        if self.stack.currentIndex() == 0:
            pix = QPixmap.fromImage(img).scaled(
                self.exit_cam_lbl.width(), self.exit_cam_lbl.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.exit_cam_lbl.setPixmap(pix)

    @pyqtSlot(str, str)
    def _on_entry_detected(self, plate, vehicle_type):
        txn_id = log_vehicle_entry(plate, vehicle_type, self.user['user_id'])
        log_activity('staff', self.user['user_id'], self.user['username'],
                     'Vehicle Entry', f"{plate} ({vehicle_type}) — Txn: {txn_id}")
        self._entry_count += 1
        self.entry_card.set_value(self._entry_count)
        self._recent_entries.insert(0, {
            'plate_number': plate, 'vehicle_type': vehicle_type,
            'time_in': datetime.now()
        })
        self._update_recent_list(self.recent_entry_frame, self._recent_entries)

    @pyqtSlot()
    def _on_entry_ocr_failed(self):
        dlg = ManualInputDialog(self)
        if dlg.exec_() == ManualInputDialog.Accepted and dlg.result_data:
            d = dlg.result_data
            txn_id = log_vehicle_entry(d['plate_number'], d['vehicle_type'],
                                       self.user['user_id'])
            log_activity('staff', self.user['user_id'], self.user['username'],
                         'Manual Entry', f"{d['plate_number']} — Txn: {txn_id}")
            self._entry_count += 1
            self.entry_card.set_value(self._entry_count)
            self._recent_entries.insert(0, {
                'plate_number': d['plate_number'],
                'vehicle_type': d['vehicle_type'],
                'time_in': datetime.now()
            })
            self._update_recent_list(self.recent_entry_frame, self._recent_entries)
        else:
            # Log as unknown
            log_vehicle_entry("UNKNOWN", "Unknown", self.user['user_id'], is_unknown=True)

    @pyqtSlot(str, str)
    def _on_exit_detected(self, plate, vehicle_type):
        txn = find_active_vehicle_by_plate(plate)
        if not txn:
            return  # Not in system
        result = log_vehicle_exit(txn['transaction_id'], self.user['user_id'])
        if not result:
            return
        dlg = ExitConfirmDialog(result, self)
        if dlg.exec_() == ExitConfirmDialog.Accepted:
            log_activity('staff', self.user['user_id'], self.user['username'],
                         'Vehicle Exit',
                         f"{plate} — Duration {result['duration_minutes']}m — ₱{result['total_charge']:.2f}")
            self._exit_count += 1
            self.exit_card2.set_value(self._exit_count)
            self._recent_exits.insert(0, {
                'plate_number': plate, 'vehicle_type': vehicle_type,
                'time_out': result['time_out']
            })
            self._update_recent_list(self.recent_exit_frame, self._recent_exits, is_exit=True)

    def _on_cam_error(self, msg):
        if hasattr(self, 'entry_cam_lbl'):
            self.entry_cam_lbl.setText(f"⚠ {msg}")
        if hasattr(self, 'exit_cam_lbl'):
            self.exit_cam_lbl.setText(f"⚠ {msg}")

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _update_clock(self):
        self.clock_lbl.setText(datetime.now().strftime("%A, %d %B %Y  •  %H:%M:%S"))

    def _refresh_tables(self):
        if self.stack.currentIndex() == 1:
            self._load_active()
        elif self.stack.currentIndex() == 2:
            self._load_completed()

    def _toggle_entry_cam(self):
        if self._entry_cam_on:
            self.entry_worker.stop()
            self._entry_cam_on = False
            self.entry_cam_lbl.setText("📷  ENTRY CAM\nCamera stopped")
            self.entry_toggle.setText("▶ Start Entry Cam")
            self.entry_toggle.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['success']}; color: white; border: none;
                    border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
                QPushButton:hover {{ background: #059669; }}
            """)
        else:
            self.entry_worker = CameraWorker(camera_index=1, mode='entry')
            self.entry_worker.frame_ready.connect(self._update_entry_frame)
            self.entry_worker.vehicle_detected.connect(self._on_entry_detected)
            self.entry_worker.ocr_failed.connect(self._on_entry_ocr_failed)
            self.entry_worker.error_signal.connect(self._on_cam_error)
            self.entry_worker.start()
            self._entry_cam_on = True
            self.entry_toggle.setText("⏹ Stop Entry Cam")
            self.entry_toggle.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['danger']}; color: white; border: none;
                    border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
                QPushButton:hover {{ background: #DC2626; }}
            """)

    def _toggle_exit_cam(self):
        if self._exit_cam_on:
            self.exit_worker.stop()
            self._exit_cam_on = False
            self.exit_cam_lbl.setText("📷  EXIT CAM\nCamera stopped")
            self.exit_toggle.setText("▶ Start Exit Cam")
            self.exit_toggle.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['success']}; color: white; border: none;
                    border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
                QPushButton:hover {{ background: #059669; }}
            """)
        else:
            self.exit_worker = CameraWorker(camera_index=1, mode='exit')
            self.exit_worker.frame_ready.connect(self._update_exit_frame)
            self.exit_worker.vehicle_detected.connect(self._on_exit_detected)
            self.exit_worker.error_signal.connect(lambda: None)
            self.exit_worker.error_signal.connect(self._on_cam_error)
            self.exit_worker.start()
            self._exit_cam_on = True
            self.exit_toggle.setText("⏹ Stop Exit Cam")
            self.exit_toggle.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['danger']}; color: white; border: none;
                    border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
                QPushButton:hover {{ background: #DC2626; }}
            """)
            
    def _logout(self):
        dlg = BlindDropDialog(self)
        if dlg.exec_() != BlindDropDialog.Accepted or dlg.amount is None:
            return
        result = end_shift(self.user['user_id'], dlg.amount)
        if result:
            flag_msg = ""
            if result['is_flagged']:
                flag_msg = (f"\n\n⚠  Discrepancy detected!\n"
                            f"System total: ₱{result['system_revenue']:.2f}\n"
                            f"Your report:  ₱{result['reported_revenue']:.2f}\n\n"
                            f"This has been flagged for admin review.")
            else:
                flag_msg = f"\n\nRevenue matched ✓  (₱{result['system_revenue']:.2f})"

            QMessageBox.information(self, "Shift Ended",
                                    f"Shift ended for {self.user['full_name']}.{flag_msg}")
            log_activity('staff', self.user['user_id'], self.user['username'],
                         'Logout',
                         f"Reported ₱{dlg.amount:.2f} — System ₱{result['system_revenue']:.2f}"
                         + (" — FLAGGED" if result['is_flagged'] else ""))

        self._stop_cameras()
        if self.on_logout:
            self.on_logout()

    def _stop_cameras(self):
        if hasattr(self, 'entry_worker'):
            self.entry_worker.stop()
        if hasattr(self, 'exit_worker'):
            self.exit_worker.stop()

    def closeEvent(self, event):
        self._stop_cameras()
        super().closeEvent(event)
