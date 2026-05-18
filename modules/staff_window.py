# modules/staff_window.py

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QStackedWidget, QFrame,
                              QScrollArea, QSizePolicy, QMessageBox, QSplitter,
                              QFileDialog, QInputDialog, QDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor

from utils.styles import COLORS
from utils.database import (log_vehicle_entry, log_vehicle_exit,
                             get_active_vehicles, get_completed_transactions,
                             find_active_vehicle_by_plate, log_activity, end_shift,
                             get_dashboard_summary, get_overstay_vehicles, is_blacklisted,
                             get_settings)
from utils.detection import CameraWorker, ModelLoader
from utils.worker import Worker
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

        self._model_errors = []
        self._model_loader = ModelLoader()
        self._model_loader.finished.connect(self._on_models_loaded)
        self._model_loader.start()

        self._entry_count = 0
        self._exit_count  = 0
        self._recent_entries = []
        self._recent_exits   = []

        self._build_ui()
        self._start_cameras()
        self._load_dashboard_summary()

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
        manual_entry_btn = QPushButton("+ Manual Entry")
        manual_entry_btn.setFixedHeight(34)
        manual_entry_btn.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['success']}; color: white; border: none;
                border-radius: 7px; font-size: 12px; font-weight: 600; padding: 0 14px; }}
            QPushButton:hover {{ background: #059669; }}
        """)
        manual_entry_btn.clicked.connect(self._on_manual_entry)
        hdr.addWidget(manual_entry_btn)
        self.clock_lbl = QLabel()
        self.clock_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        hdr.addWidget(self.clock_lbl)
        lay.addLayout(hdr)

        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(1000)
        self._update_clock()

        self._model_warn_label = QLabel()
        self._model_warn_label.setStyleSheet(f"""
            background: {COLORS['warning']}20; color: {COLORS['warning']};
            border: 1px solid {COLORS['warning']}40; border-radius: 7px;
            padding: 8px 14px; font-size: 12px;
        """)
        self._model_warn_label.hide()
        lay.addWidget(self._model_warn_label)

        # Camera feeds
        cam_row = QHBoxLayout()
        cam_row.setSpacing(14)

        self.entry_cam_lbl = self._camera_placeholder("ENTRY CAM", COLORS['success'])
        self.exit_cam_lbl  = self._camera_placeholder("EXIT CAM",  COLORS['primary'])

        self.entry_toggle = QPushButton("▶ Start Entry Cam")
        self.entry_toggle.setFixedHeight(32)
        self.entry_toggle.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['success']}; color: white; border: none;
                border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
            QPushButton:hover {{ background: #059669; }}
        """)
        self.entry_toggle.clicked.connect(self._toggle_entry_cam)
        self._entry_cam_on = False

        self.exit_toggle = QPushButton("▶ Start Exit Cam")
        self.exit_toggle.setFixedHeight(32)
        self.exit_toggle.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['success']}; color: white; border: none;
                border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
            QPushButton:hover {{ background: #059669; }}
        """)
        self.exit_toggle.clicked.connect(self._toggle_exit_cam)
        self._exit_cam_on = False

        self._cam_hint_lbl = QLabel("Click Start to activate cameras")
        self._cam_hint_lbl.setAlignment(Qt.AlignCenter)
        self._cam_hint_lbl.setStyleSheet(f"""
            color: {COLORS['text_muted']}; font-size: 12px;
            background: {COLORS['bg_input']}; border-radius: 6px;
            padding: 6px 0; border: 1px solid {COLORS['border']};
        """)
        lay.addWidget(self._cam_hint_lbl)

        entry_card = self._cam_card("Entry Camera", self.entry_cam_lbl, self.entry_toggle)
        exit_card  = self._cam_card("Exit Camera",  self.exit_cam_lbl,  self.exit_toggle)
        cam_row.addWidget(entry_card)
        cam_row.addWidget(exit_card)
        lay.addLayout(cam_row)

        # Summary row — entries, exits, capacity, overstays
        sum_row = QHBoxLayout()
        sum_row.setSpacing(14)

        self.entry_card        = StatCard("ENTRIES TODAY",     "0",   accent=COLORS['success'])
        self.exit_card2        = StatCard("EXITS TODAY",       "0",   accent=COLORS['primary'])
        self.capacity_card     = StatCard("PARKING CAPACITY",  "—/—", accent=COLORS['accent'])
        self.overstay_stat_card = StatCard("OVERSTAYS",        "0",   accent=COLORS['danger'])
        for c in [self.entry_card, self.exit_card2, self.capacity_card, self.overstay_stat_card]:
            sum_row.addWidget(c)
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
        lbl = QLabel(f"📷  {label}\nCamera stopped")
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
        card.setProperty("card", "true")
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
        card.setProperty("card", "true")
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
            row.setProperty("card", "inner")
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

    def _on_models_loaded(self, errors):
        self._model_errors = errors
        if errors:
            self._model_warn_label.setText("⚠  " + "  |  ".join(errors) + "  — detection limited")
            self._model_warn_label.show()

    def _load_dashboard_summary(self):
        if getattr(self, '_summary_worker', None) and self._summary_worker.isRunning():
            return
        self._summary_worker = Worker(get_dashboard_summary)
        self._summary_worker.result.connect(self._on_summary_loaded)
        self._summary_worker.start()

    def _on_summary_loaded(self, summary):
        if summary:
            try:
                capacity = int(summary.get('capacity') or 50)
                parked   = int(summary.get('currently_parked') or 0)
                self.capacity_card.set_value(f"{parked}/{capacity}")
                self.overstay_stat_card.set_value(summary.get('overstay_count', 0))
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2 — ACTIVE PARKING
    # ──────────────────────────────────────────────────────────────────────────

    def _build_active_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        t = QLabel("Active Parking List")
        t.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        hdr.addWidget(t)
        hdr.addStretch()

        overstay_legend = QLabel("⚑  Overstay")
        overstay_legend.setFixedSize(100, 34)
        overstay_legend.setAlignment(Qt.AlignCenter)
        overstay_legend.setStyleSheet(f"""
            background: {COLORS['warning']}18; color: {COLORS['warning']};
            border: 1px solid {COLORS['warning']}40; border-radius: 5px;
            font-size: 11px; font-weight: 600;
        """)
        hdr.addWidget(overstay_legend)

        ref_btn = QPushButton("↻  Refresh")
        ref_btn.setFixedHeight(34)
        ref_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; border-radius: 7px;
                font-size: 12px; padding: 0 12px; min-height: 0px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; color: {COLORS['text']}; }}
        """)
        ref_btn.clicked.connect(self._load_active)
        hdr.addWidget(ref_btn)

        manual_exit_btn = QPushButton("Manual Exit")
        manual_exit_btn.setFixedHeight(34)
        manual_exit_btn.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['primary']}; color: white; border: none;
                border-radius: 7px; font-size: 12px; font-weight: 600; padding: 0 14px; min-height: 0px; }}
            QPushButton:hover {{ background: {COLORS['primary_h']}; }}
        """)
        manual_exit_btn.clicked.connect(self._on_manual_exit)
        hdr.addWidget(manual_exit_btn)
        lay.addLayout(hdr)

        cols = ["Txn ID", "Plate", "Type", "Time In", "Date", "Staff (Entry)", "Flagged"]
        self.active_table = SearchableTable(cols)
        lay.addWidget(self.active_table)

        return page

    def _load_active(self):
        if getattr(self, '_active_worker', None) and self._active_worker.isRunning():
            return

        def fetch():
            vehicles = get_active_vehicles()
            try:
                overstay = {ov['transaction_id'] for ov in get_overstay_vehicles()}
            except Exception:
                overstay = set()
            return vehicles, overstay

        self._active_worker = Worker(fetch)
        self._active_worker.result.connect(self._on_active_loaded)
        self._active_worker.start()

    def _on_active_loaded(self, data):
        rows_raw, overstay_ids = data
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

        if overstay_ids:
            bg = QColor(COLORS['warning'])
            bg.setAlpha(45)
            for row_idx, r in enumerate(rows_raw):
                if r['transaction_id'] in overstay_ids:
                    for col in range(self.active_table.table.columnCount()):
                        item = self.active_table.table.item(row_idx, col)
                        if item:
                            item.setBackground(bg)
                            item.setForeground(QColor(COLORS['warning']))

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
        if getattr(self, '_completed_worker', None) and self._completed_worker.isRunning():
            return
        self._completed_worker = Worker(get_completed_transactions)
        self._completed_worker.result.connect(self._on_completed_loaded)
        self._completed_worker.start()

    def _on_completed_loaded(self, rows_raw):
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
        # Set defaults immediately so toggles work before settings load
        self._entry_cam_idx = 0
        self._exit_cam_idx = 1
        self._demo_video_path = None
        self._settings_worker = Worker(get_settings)
        self._settings_worker.result.connect(self._on_settings_loaded)
        self._settings_worker.start()

    def _on_settings_loaded(self, s):
        s = s or {}
        self._entry_cam_idx = int(s.get('entry_camera_index', 0))
        self._exit_cam_idx = int(s.get('exit_camera_index', 1))
        demo = s.get('demo_video_path', '') or ''
        self._demo_video_path = demo if demo else None


    @pyqtSlot(QImage)
    def _update_entry_frame(self, img):
        if self.stack.currentIndex() == 0:
            pix = QPixmap.fromImage(img).scaled(
                self.entry_cam_lbl.width(), self.entry_cam_lbl.height(),
                Qt.KeepAspectRatio, Qt.FastTransformation)
            self.entry_cam_lbl.setPixmap(pix)

    @pyqtSlot(QImage)
    def _update_exit_frame(self, img):
        if self.stack.currentIndex() == 0:
            pix = QPixmap.fromImage(img).scaled(
                self.exit_cam_lbl.width(), self.exit_cam_lbl.height(),
                Qt.KeepAspectRatio, Qt.FastTransformation)
            self.exit_cam_lbl.setPixmap(pix)

    @pyqtSlot(str, str)
    def _on_entry_detected(self, plate, vehicle_type):
        bl = is_blacklisted(plate)
        if bl:
            QMessageBox.warning(
                self, "Blacklisted Vehicle",
                f"⛔  Plate {plate} is BLACKLISTED\n\n"
                f"Reason: {bl.get('reason') or '—'}\n\nEntry has been denied."
            )
            return

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
            bl = is_blacklisted(d['plate_number'])
            if bl:
                QMessageBox.warning(
                    self, "Blacklisted Vehicle",
                    f"⛔  Plate {d['plate_number']} is BLACKLISTED\n\n"
                    f"Reason: {bl.get('reason') or '—'}\n\nEntry has been denied."
                )
                return
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

    def _on_manual_entry(self):
        dlg = ManualInputDialog(self)
        if dlg.exec_() == ManualInputDialog.Accepted and dlg.result_data:
            d = dlg.result_data
            bl = is_blacklisted(d['plate_number'])
            if bl:
                QMessageBox.warning(
                    self, "Blacklisted Vehicle",
                    f"⛔  Plate {d['plate_number']} is BLACKLISTED\n\n"
                    f"Reason: {bl.get('reason') or '—'}\n\nEntry has been denied."
                )
                return
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

    @pyqtSlot(str, str)
    def _on_exit_detected(self, plate, vehicle_type):
        txn = find_active_vehicle_by_plate(plate)
        if not txn:
            QMessageBox.warning(
                self, "Plate Not Found",
                f"No active parking record found for plate {plate}.\n"
                f"Please verify the plate number."
            )
            return
        result = log_vehicle_exit(txn['transaction_id'], self.user['user_id'])
        if not result:
            return

        is_reserved = result.get('is_reserved', False)
        dlg = ExitConfirmDialog(result, is_reserved=is_reserved, parent=self)
        if dlg.exec_() == ExitConfirmDialog.Accepted:
            log_activity('staff', self.user['user_id'], self.user['username'],
                         'Vehicle Exit',
                         f"{plate} — Duration {result['duration_minutes']}m — ₱{result['total_charge']:.2f}")
            self._exit_count += 1
            self.exit_card2.set_value(self._exit_count)
            self._recent_exits.insert(0, {
                'plate_number': plate,
                'vehicle_type': txn.get('vehicle_type', vehicle_type),
                'time_out': result['time_out']
            })
            self._update_recent_list(self.recent_exit_frame, self._recent_exits, is_exit=True)

            # Offer PDF receipt
            receipt_dlg = QDialog(self)
            receipt_dlg.setWindowTitle("Save Receipt")
            receipt_dlg.setFixedSize(400, 148)
            receipt_dlg.setStyleSheet(f"background: {COLORS['bg']}; color: {COLORS['text']};")
            rdl = QVBoxLayout(receipt_dlg)
            rdl.setContentsMargins(24, 24, 24, 20)
            rdl.setSpacing(20)
            msg_lbl = QLabel("Would you like to save a PDF receipt\nfor this transaction?")
            msg_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
            msg_lbl.setAlignment(Qt.AlignCenter)
            rdl.addWidget(msg_lbl)
            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)
            no_btn = QPushButton("No")
            no_btn.setFixedHeight(36)
            no_btn.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['bg_input']}; color: {COLORS['text']};
                    border: 1px solid {COLORS['border']}; border-radius: 8px; font-size: 13px; }}
                QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
            """)
            no_btn.clicked.connect(receipt_dlg.reject)
            yes_btn = QPushButton("Yes, Save Receipt")
            yes_btn.setFixedHeight(36)
            yes_btn.clicked.connect(receipt_dlg.accept)
            btn_row.addWidget(no_btn)
            btn_row.addWidget(yes_btn)
            rdl.addLayout(btn_row)
            if receipt_dlg.exec_() == QDialog.Accepted:
                from utils.export import export_receipt_pdf
                path, _ = QFileDialog.getSaveFileName(
                    self, "Save Receipt",
                    f"receipt_{result['transaction_id']}.pdf",
                    "PDF Files (*.pdf)"
                )
                if path:
                    try:
                        export_receipt_pdf(result, path)
                        QMessageBox.information(self, "Receipt Saved",
                                                f"Receipt saved to:\n{path}")
                    except Exception as e:
                        QMessageBox.warning(self, "Export Failed", str(e))

    def _on_exit_ocr_failed(self):
        dlg = ManualInputDialog(self)
        if dlg.exec_() == ManualInputDialog.Accepted and dlg.result_data:
            plate = dlg.result_data['plate_number']
            self._on_exit_detected(plate, dlg.result_data['vehicle_type'])

    def _on_manual_exit(self):
        plate, ok = QInputDialog.getText(self, "Manual Exit", "Enter plate number:")
        if ok and plate.strip():
            self._on_exit_detected(plate.strip().upper(), "")

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
        if self.stack.currentIndex() == 0:
            self._load_dashboard_summary()
        elif self.stack.currentIndex() == 1:
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
            self._cam_hint_lbl.show()
        else:
            self.entry_worker = CameraWorker(camera_index=self._entry_cam_idx, mode='entry',
                                             video_file=self._demo_video_path)
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
            self._check_hide_cam_hint()

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
            self._cam_hint_lbl.show()
        else:
            self.exit_worker = CameraWorker(camera_index=self._exit_cam_idx, mode='exit',
                                            video_file=self._demo_video_path)
            self.exit_worker.frame_ready.connect(self._update_exit_frame)
            self.exit_worker.vehicle_detected.connect(self._on_exit_detected)
            self.exit_worker.ocr_failed.connect(self._on_exit_ocr_failed)
            self.exit_worker.error_signal.connect(self._on_cam_error)
            self.exit_worker.start()
            self._exit_cam_on = True
            self.exit_toggle.setText("⏹ Stop Exit Cam")
            self.exit_toggle.setStyleSheet(f"""
                QPushButton {{ background: {COLORS['danger']}; color: white; border: none;
                    border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 12px; }}
                QPushButton:hover {{ background: #DC2626; }}
            """)
            self._check_hide_cam_hint()

    def _check_hide_cam_hint(self):
        if self._entry_cam_on and self._exit_cam_on:
            self._cam_hint_lbl.hide()

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
