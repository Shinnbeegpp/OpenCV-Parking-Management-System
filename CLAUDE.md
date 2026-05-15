# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ParkEase is a desktop parking management system using PyQt5 for the UI, MySQL for storage, YOLOv8 for vehicle detection, and EasyOCR for license plate recognition. It supports two roles: **staff** (entry/exit monitoring) and **admin** (revenue analytics, staff management).

## Setup

**Database:**
```bash
mysql -u root -p < schema.sql
```
Creates the `parkease` database with 6 tables and a default admin (`admin` / `admin123`).

**Environment variables** — create a `.env` file in the project root:
```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=parkease
DB_USER=root
DB_PASSWORD=your_password
```

**Dependencies:**
```bash
pip install -r requirements.txt
pip install python-dotenv   # currently missing from requirements.txt
```
On first run, YOLO downloads `yolov8n.pt` (~6 MB) and EasyOCR downloads language models (~200 MB).

**Run the app:**
```bash
python main.py
```

**Reset admin account:**
```bash
python fix_admin.py
```

## Architecture

```
main.py (ParkEaseApp)
  └─ forces torch import before PyQt5 (Windows DLL conflict workaround)
  └─ loads YOLO + EasyOCR models in background thread
  └─ checks DB connection, then shows LoginWindow

LoginWindow  ──────────────────────────────────────────────────┐
  └─ role-based routing                                         │
       ├─ StaffWindow   (entry/exit monitoring, active vehicles)│
       └─ AdminWindow   (revenue dashboard, staff management)  ─┘
```

### Key modules

| File | Responsibility |
|------|---------------|
| `utils/database.py` | All MySQL queries, bcrypt auth, shift/transaction/audit logic |
| `utils/detection.py` | `CameraWorker` (QThread): YOLO vehicle detection → EasyOCR plate recognition |
| `utils/styles.py` | Dark-theme stylesheet; `COLORS` dict is the single source of truth for palette |
| `modules/widgets.py` | Shared components: `SideNav`, `StatCard`, `SearchableTable`, `ManualInputDialog`, `ExitConfirmDialog`, `BlindDropDialog` |
| `modules/staff_window.py` | Dual-camera live feed, active parking table, shift management |
| `modules/admin_window.py` | Revenue charts (PyQtChart), staff oversight, activity logs; writes crashes to `crash_log.txt` |

### Detection pipeline (`utils/detection.py`)

`CameraWorker` (QThread) → captures frame → YOLO detects vehicle class (Car/Motorcycle/Bus/Truck) → EasyOCR reads plate text → emits `vehicle_detected` signal. A 30-second per-vehicle cooldown prevents duplicate detections; after 3 seconds without OCR result it emits `ocr_failed` to trigger `ManualInputDialog`.

**Known issue:** `detection.py` line ~148 has a hardcoded video file path for testing. Switch back to `cv2.VideoCapture(self.camera_index)` for production/webcam use.

### Blind drop feature

Staff end their shift by submitting their cash total without seeing the system total. Any mismatch sets `shifts.is_flagged = 1` and `staff.is_flagged = 1`. Admin can view and resolve discrepancies.

## Database schema (6 tables)

`admins`, `staff`, `transactions` (status: `active`/`completed`/`unknown`, `is_flagged`), `shifts` (`is_flagged`, `is_resolved`), `activity_logs`. Parking rate: ₱10/hour, ₱10 minimum. SSL CA cert is `utils/ca.pem`.

## Notes

- No test suite or linting configuration exists.
