# ParkEase — Computer Vision Parking Management System

A full-stack parking management system built with PyQt5, MySQL, YOLOv8, and EasyOCR.

---

## Features

### Staff Account
- **Live Monitoring Dashboard** — dual camera POV with YOLO bounding boxes + OCR plate overlays
- **Active Parking List** — searchable/filterable table of all currently parked vehicles
- **Completed Transactions** — full exit history with duration and charges (₱10/hour)
- **Manual Entry Popup** — triggered when OCR fails (tailgating, muddy plate)
- **Exit Confirmation Popup** — shows plate, duration, and total charge before logging
- **Blind Drop on Logout** — staff submits cash total without seeing the system total; flags mismatch

### Admin Account
- **Revenue Dashboard** — today / yesterday / last month / this year stats + revenue graph
- **Vehicle Parking History** — full searchable transaction history
- **Staff Management** — create, view, and monitor staff (flags shown in red)
- **Activity Logs** — every action timestamped in real time

---

## Setup Instructions

### 1. Install MySQL
Download and install [MySQL Community Server](https://dev.mysql.com/downloads/mysql/).
Also install **MySQL Workbench** if you don't have it.

### 2. Create the Database
Open MySQL Workbench, connect to your server, then run `schema.sql`:
```sql
-- In MySQL Workbench: File > Open SQL Script > schema.sql > Execute
```
This creates the `parkease` database and a default admin account:
- **Username:** `admin`
- **Password:** `admin123`

> **Important:** Change this password after your first login, or create a new admin directly in MySQL.

### 3. Configure Database Connection
Edit `utils/database.py` and update `DB_CONFIG`:
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'parkease',
    'user': 'root',        # ← your MySQL username
    'password': 'your_password',  # ← your MySQL password
}
```

### 4. Install Python Dependencies
Requires **Python 3.9+**.

```bash
pip install -r requirements.txt
```

> **Note on PyQtChart:** If `pip install PyQtChart` fails, try:
> ```bash
> pip install PyQt5 PyQt5-Qt5 PyQt5-sip
> pip install PyQtChart
> ```
> On some systems you may need: `pip install PyQt5-Charts`

> **Note on YOLO:** `ultralytics` will automatically download `yolov8n.pt` (~6MB) on first run.

> **Note on EasyOCR:** First run downloads language models (~200MB). Ensure internet access.

### 5. Run the Application
```bash
cd parkease
python main.py
```

---

## Project Structure
```
parkease/
├── main.py                  # Entry point
├── requirements.txt
├── schema.sql               # MySQL database schema
│
├── modules/
│   ├── login_window.py      # Login screen
│   ├── staff_window.py      # Staff panel (3 pages + camera)
│   ├── admin_window.py      # Admin panel (3 pages + chart)
│   └── widgets.py           # Shared UI components
│
└── utils/
    ├── database.py          # All MySQL queries
    ├── detection.py         # YOLO + OCR + camera thread
    └── styles.py            # Global dark theme stylesheet
```

---

## Camera Setup
- The system uses your **built-in laptop webcam** (index `0`) for both entry and exit feeds.
- In production, connect two separate cameras and set:
  - Entry worker: `camera_index=0`
  - Exit worker: `camera_index=1`
  These can be changed in `modules/staff_window.py` inside `_start_cameras()`.

---

## Parking Rates
- **₱10 per hour** (minimum ₱10 for any duration)
- Configurable in `utils/database.py` → `log_vehicle_exit()` function

---

## Admin Account Creation (Manual)
To create additional admin accounts directly in MySQL Workbench:
```sql
USE parkease;
INSERT INTO admins (username, password_hash, full_name)
VALUES ('newadmin', SHA2('yourpassword', 256), 'Admin Name');
```
> Note: The app uses `bcrypt` for hashing. If you use `SHA2` here, the login will fail.
> Use the app's default admin to create staff. For new admins, use Python:
> ```python
> from utils.database import hash_password
> print(hash_password('yourpassword'))
> # Then INSERT that hash into MySQL manually
> ```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Database connection failed` | Check MySQL is running; verify DB_CONFIG credentials |
| `Cannot open camera 0` | Check webcam permissions; try `camera_index=1` |
| `YOLO not loading` | Run `pip install ultralytics --upgrade` |
| `EasyOCR error` | Run `pip install easyocr --upgrade`; check internet for model download |
| `PyQtChart not found` | Install separately: `pip install PyQtChart` |
| Camera shows on one feed only | Both entry and exit share camera index 0; this is expected in single-camera mode |
