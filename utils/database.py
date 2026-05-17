# utils/database.py
# Database connection and query utilities

import mysql.connector
from mysql.connector import Error
import bcrypt
from datetime import datetime, date
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'autocommit': True,
    'connection_timeout': 10,
    'ssl_ca': 'utils/ca.pem',
}

def get_connection():
    """Return a new MySQL connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        raise ConnectionError(f"Database connection failed: {e}")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def generate_transaction_id() -> str:
    now = datetime.now()
    return f"TXN-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

# ─── AUTH ────────────────────────────────────────────────────────────────────

def login(username: str, password: str):
    """
    Returns dict with keys: success, role, user_id, full_name, username
    role is 'admin' or 'staff'
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Check admin
        cur.execute("SELECT * FROM admins WHERE username = %s", (username,))
        row = cur.fetchone()
        if row and verify_password(password, row['password_hash']):
            return {'success': True, 'role': 'admin',
                    'user_id': row['id'], 'full_name': row['full_name'],
                    'username': row['username'],
                    'theme': row.get('theme', 'dark') or 'dark'}

        # Check staff
        cur.execute("SELECT * FROM staff WHERE username = %s AND is_active = 1", (username,))
        row = cur.fetchone()
        if row and verify_password(password, row['password_hash']):
            return {'success': True, 'role': 'staff',
                    'user_id': row['id'], 'full_name': row['full_name'],
                    'username': row['username'],
                    'theme': row.get('theme', 'dark') or 'dark'}

        return {'success': False, 'message': 'Invalid username or password.'}
    finally:
        cur.close(); conn.close()

# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

def log_vehicle_entry(plate_number, vehicle_type, staff_id, is_unknown=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        txn_id = generate_transaction_id()
        now = datetime.now()
        status = 'unknown' if is_unknown else 'active'
        cur.execute("""
            INSERT INTO transactions
            (transaction_id, plate_number, vehicle_type, time_in, date_in, staff_entry_id, status, is_flagged)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (txn_id, plate_number, vehicle_type, now, now.date(), staff_id, status, is_unknown))
        conn.commit()
        return txn_id
    finally:
        cur.close(); conn.close()

def log_vehicle_exit(transaction_id, staff_id):
    """Returns dict with transaction details including charge."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM transactions WHERE transaction_id = %s", (transaction_id,))
        txn = cur.fetchone()
        if not txn:
            return None

        # Check if reserved vehicle (no charge)
        reserved = is_reserved_vehicle(txn['plate_number'])

        now = datetime.now()
        duration_minutes = max(1, int((now - txn['time_in']).total_seconds() / 60))
        hours = duration_minutes / 60

        if reserved:
            total_charge = 0.00
        else:
            # Get settings for pricing
            cur.execute("SELECT * FROM settings WHERE id = 1")
            s = cur.fetchone()
            rate_type    = s['rate_type']
            min_charge   = float(s['minimum_charge'])
            if rate_type == 'hourly':
                total_charge = round(max(min_charge, hours * float(s['rate_per_hour'])), 2)
            elif rate_type == 'flat':
                total_charge = float(s['flat_rate'])
            elif rate_type == 'daily_max':
                days = max(1, -(-int(hours) // 24))  # ceiling division
                total_charge = round(min(days * float(s['daily_max_rate']),
                                        hours * float(s['rate_per_hour'])), 2)
                total_charge = max(min_charge, total_charge)

        cur.execute("""
            UPDATE transactions SET time_out=%s, staff_exit_id=%s,
            duration_minutes=%s, total_charge=%s, status='completed'
            WHERE transaction_id=%s
        """, (now, staff_id, duration_minutes, total_charge, transaction_id))
        conn.commit()
        return {
            'transaction_id': transaction_id,
            'plate_number': txn['plate_number'],
            'vehicle_type': txn['vehicle_type'],
            'time_in': txn['time_in'],
            'time_out': now,
            'duration_minutes': duration_minutes,
            'total_charge': total_charge,
            'is_reserved': reserved is not None
        }
    finally:
        cur.close(); conn.close()   

def get_active_vehicles():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT t.transaction_id, t.plate_number, t.vehicle_type,
                   t.time_in, t.date_in, t.is_flagged,
                   s.full_name AS staff_name
            FROM transactions t
            LEFT JOIN staff s ON t.staff_entry_id = s.id
            WHERE t.status IN ('active','unknown')
            ORDER BY t.time_in DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_completed_transactions(limit=500):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT t.transaction_id, t.plate_number, t.date_in,
                   t.time_in, t.time_out, t.duration_minutes,
                   t.total_charge, se.full_name AS staff_exit_name
            FROM transactions t
            LEFT JOIN staff se ON t.staff_exit_id = se.id
            WHERE t.status = 'completed'
            ORDER BY t.time_out DESC
            LIMIT %s
        """, (limit,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_all_transactions_admin():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT t.transaction_id, t.plate_number, t.vehicle_type, t.date_in,
                   sen.full_name AS staff_entry_name, t.time_in,
                   sex.full_name AS staff_exit_name, t.time_out,
                   t.duration_minutes, t.total_charge, t.status, t.is_flagged
            FROM transactions t
            LEFT JOIN staff sen ON t.staff_entry_id = sen.id
            LEFT JOIN staff sex ON t.staff_exit_id = sex.id
            ORDER BY t.time_in DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def find_active_vehicle_by_plate(plate_number):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT * FROM transactions
            WHERE plate_number = %s AND status IN ('active','unknown')
            ORDER BY time_in DESC LIMIT 1
        """, (plate_number,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

# ─── REVENUE ──────────────────────────────────────────────────────────────────

def get_revenue_today():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0)
            FROM transactions WHERE DATE(time_out) = CURDATE() AND status='completed'
        """)
        return float(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()

def get_revenue_yesterday():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0)
            FROM transactions WHERE DATE(time_out) = DATE_SUB(CURDATE(),INTERVAL 1 DAY) AND status='completed'
        """)
        return float(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()

def get_revenue_last_7_days():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0)
            FROM transactions
            WHERE time_out >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            AND time_out < NOW() AND status='completed'
        """)
        return float(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()

def get_revenue_last_month():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0) FROM transactions
            WHERE MONTH(time_out)=MONTH(DATE_SUB(CURDATE(),INTERVAL 1 MONTH))
            AND YEAR(time_out)=YEAR(DATE_SUB(CURDATE(),INTERVAL 1 MONTH))
            AND status='completed'
        """)
        return float(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()

def get_revenue_this_year():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0) FROM transactions
            WHERE YEAR(time_out)=YEAR(CURDATE()) AND status='completed'
        """)
        return float(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()

def get_revenue_over_time(period='7d'):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        if period == '7d':
            q = "SELECT DATE(time_out) as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' AND time_out >= DATE_SUB(NOW(), INTERVAL 7 DAY) GROUP BY DATE(time_out) ORDER BY d"
        elif period == 'month':
            q = "SELECT DATE(time_out) as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' AND MONTH(time_out)=MONTH(NOW()) AND YEAR(time_out)=YEAR(NOW()) GROUP BY DATE(time_out) ORDER BY d"
        elif period == '3m':
            q = "SELECT DATE(time_out) as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' AND time_out >= DATE_SUB(NOW(), INTERVAL 3 MONTH) GROUP BY DATE(time_out) ORDER BY d"
        elif period == '6m':
            q = "SELECT DATE(time_out) as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' AND time_out >= DATE_SUB(NOW(), INTERVAL 6 MONTH) GROUP BY DATE(time_out) ORDER BY d"
        elif period == 'year':
            q = "SELECT DATE_FORMAT(time_out,'%Y-%m') as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' AND YEAR(time_out)=YEAR(NOW()) GROUP BY DATE_FORMAT(time_out,'%Y-%m') ORDER BY d"
        else:
            q = "SELECT DATE_FORMAT(time_out,'%Y-%m') as d, SUM(total_charge) as rev FROM transactions WHERE status='completed' GROUP BY DATE_FORMAT(time_out,'%Y-%m') ORDER BY d LIMIT 24"
        cur.execute(q)
        rows = cur.fetchall()
        return [(str(r['d']), float(r['rev'])) for r in rows]
    finally:
        cur.close(); conn.close()

# ─── STAFF ────────────────────────────────────────────────────────────────────

def get_all_staff():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT s.id, s.username, s.full_name, s.is_active, s.is_flagged,
                   s.created_at, a.full_name AS created_by_name,
                   (SELECT COUNT(*) FROM shifts sh
                    WHERE sh.staff_id = s.id
                    AND sh.shift_end IS NOT NULL
                    AND sh.staff_reported_revenue IS NOT NULL) AS total_shifts,
                   (SELECT COUNT(*) FROM shifts sh
                    WHERE sh.staff_id = s.id
                    AND sh.is_flagged = TRUE
                    AND sh.shift_end IS NOT NULL
                    AND sh.staff_reported_revenue IS NOT NULL) AS total_discrepancies,
                   (SELECT COUNT(*) FROM shifts sh
                    WHERE sh.staff_id = s.id
                    AND sh.is_flagged = TRUE
                    AND sh.is_resolved = FALSE
                    AND sh.shift_end IS NOT NULL
                    AND sh.staff_reported_revenue IS NOT NULL) AS unresolved_discrepancies
            FROM staff s LEFT JOIN admins a ON s.created_by = a.id
            ORDER BY s.created_at DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def create_staff(full_name, username, password, admin_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        hashed = hash_password(password)
        cur.execute("""
            INSERT INTO staff (full_name, username, password_hash, created_by)
            VALUES (%s, %s, %s, %s)
        """, (full_name, username, hashed, admin_id))
        conn.commit()
        return cur.lastrowid
    except mysql.connector.IntegrityError:
        raise ValueError("Username already exists.")
    finally:
        cur.close(); conn.close()

def get_current_shift_staff():
    """Returns staff whose latest shift is still open (properly logged in)."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT s.full_name, sh.shift_start FROM shifts sh
            JOIN staff s ON sh.staff_id = s.id
            WHERE sh.shift_end IS NULL
            AND sh.id = (
                SELECT id FROM shifts WHERE staff_id = sh.staff_id
                ORDER BY shift_start DESC LIMIT 1
            )
            ORDER BY sh.shift_start DESC LIMIT 1
        """)
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

def start_shift(staff_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        now = datetime.now()
        # Close any abandoned open shifts (e.g. from a previous session that crashed)
        cur.execute("""
            UPDATE shifts SET shift_end = %s
            WHERE staff_id = %s AND shift_end IS NULL
        """, (now, staff_id))
        conn.commit()
        cur.execute("INSERT INTO shifts (staff_id, shift_start) VALUES (%s, %s)", (staff_id, now))
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close(); conn.close()

def end_shift(staff_id, reported_revenue):
    conn = get_connection()
    # buffered=True ensures the first result set is fully consumed before the
    # next query runs — avoids "Unread result found" silent data loss
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("""
            SELECT id, shift_start FROM shifts
            WHERE staff_id = %s AND shift_end IS NULL
            ORDER BY shift_start DESC LIMIT 1
        """, (staff_id,))
        row = cur.fetchone()
        if not row:
            return None
        shift_id    = row['id']
        shift_start = row['shift_start']   # pass as param, not subquery
        cur.execute("""
            SELECT COALESCE(SUM(total_charge), 0) AS rev FROM transactions
            WHERE staff_exit_id = %s
            AND time_out IS NOT NULL
            AND time_out >= %s
        """, (staff_id, shift_start))
        rev_row    = cur.fetchone()
        system_rev = float(rev_row['rev']) if rev_row else 0.0
        is_flagged = abs(system_rev - reported_revenue) > 0.01
        now = datetime.now()
        cur.execute("""
            UPDATE shifts SET shift_end = %s, system_revenue = %s,
            staff_reported_revenue = %s, is_flagged = %s WHERE id = %s
        """, (now, system_rev, reported_revenue, is_flagged, shift_id))
        if is_flagged:
            cur.execute("UPDATE staff SET is_flagged = TRUE WHERE id = %s", (staff_id,))
        conn.commit()
        return {'system_revenue': system_rev, 'reported_revenue': reported_revenue, 'is_flagged': is_flagged}
    finally:
        cur.close(); conn.close()

# ─── LOGS ─────────────────────────────────────────────────────────────────────

def log_activity(user_type, user_id, username, action, details=''):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO activity_logs (user_type, user_id, username, action, details)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_type, user_id, username, action, details))
        conn.commit()
    finally:
        cur.close(); conn.close()

def get_recent_activity_logs(limit=50):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT log_time, username, action, details
            FROM activity_logs ORDER BY log_time DESC LIMIT %s
        """, (limit,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()


def get_staff_shift_history(staff_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT 
                sh.id, sh.shift_start, sh.shift_end,
                sh.system_revenue, sh.staff_reported_revenue, sh.is_flagged,
                COUNT(t.id) AS vehicles_handled
            FROM shifts sh
            LEFT JOIN transactions t 
                ON t.staff_exit_id = sh.staff_id
                AND t.time_out BETWEEN sh.shift_start AND IFNULL(sh.shift_end, NOW())
            WHERE sh.staff_id = %s
            GROUP BY sh.id
            ORDER BY sh.shift_start DESC
        """, (staff_id,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_all_staff_with_current_shift():
    """Returns only staff who are currently logged in (latest open shift only)."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT s.id, s.full_name, s.username, s.is_active, s.is_flagged,
                sh.shift_start,
                (SELECT COALESCE(SUM(total_charge),0) FROM transactions
                 WHERE staff_exit_id = s.id
                 AND time_out >= sh.shift_start) AS current_collected
            FROM staff s
            INNER JOIN shifts sh ON sh.id = (
                SELECT id FROM shifts
                WHERE staff_id = s.id
                ORDER BY shift_start DESC LIMIT 1
            )
            WHERE sh.shift_end IS NULL
            ORDER BY s.full_name
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()


def get_staff_login_logout_history(staff_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                sh.id,
                sh.shift_start,
                sh.shift_end,
                sh.system_revenue,
                sh.staff_reported_revenue,
                sh.is_flagged,
                sh.is_resolved,
                (SELECT COUNT(*) FROM transactions t
                 WHERE t.staff_exit_id = %s
                 AND t.time_out >= sh.shift_start
                 AND t.time_out <= sh.shift_end
                 AND t.status = 'completed') AS vehicles_handled
            FROM shifts sh
            WHERE sh.staff_id = %s
            AND sh.shift_end IS NOT NULL
            AND sh.staff_reported_revenue IS NOT NULL
            ORDER BY sh.shift_start DESC
        """, (staff_id, staff_id))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def resolve_staff_flag(staff_id, shift_id=None):
    """Marks discrepancy as resolved but keeps the record. Only clears staff flag if no more unresolved shifts."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        if shift_id:
            cur.execute("UPDATE shifts SET is_resolved = TRUE WHERE id = %s", (shift_id,))
        # Check if any unresolved flagged shifts remain
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM shifts
            WHERE staff_id = %s AND is_flagged = TRUE AND is_resolved = FALSE
            AND shift_end IS NOT NULL AND staff_reported_revenue IS NOT NULL
        """, (staff_id,))
        remaining = cur.fetchone()['cnt']
        if remaining == 0:
            cur.execute("UPDATE staff SET is_flagged = FALSE WHERE id = %s", (staff_id,))
        conn.commit()
        return remaining
    finally:
        cur.close(); conn.close()

# ─── SETTINGS ─────────────────────────────────────────────────────────────────

def get_settings():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM settings WHERE id = 1")
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

def update_settings(**kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    try:
        cols = ', '.join(f"{k}=%s" for k in kwargs)
        vals = list(kwargs.values())
        cur.execute(f"UPDATE settings SET {cols} WHERE id = 1", vals)
        conn.commit()
    finally:
        cur.close(); conn.close()

# ─── BLACKLIST ────────────────────────────────────────────────────────────────

def get_blacklist():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT b.*, a.full_name AS added_by_name
            FROM blacklist b
            JOIN admins a ON b.added_by = a.id
            WHERE b.is_active = TRUE
            ORDER BY b.added_at DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def add_to_blacklist(plate_number, reason, admin_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO blacklist (plate_number, reason, added_by)
            VALUES (%s, %s, %s)
        """, (plate_number.upper(), reason, admin_id))
        conn.commit()
    except mysql.connector.IntegrityError:
        raise ValueError("Plate is already blacklisted.")
    finally:
        cur.close(); conn.close()

def remove_from_blacklist(plate_number):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE blacklist SET is_active = FALSE WHERE plate_number = %s",
                    (plate_number.upper(),))
        conn.commit()
    finally:
        cur.close(); conn.close()

def is_blacklisted(plate_number):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT * FROM blacklist
            WHERE plate_number = %s AND is_active = TRUE
        """, (plate_number.upper(),))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

# ─── RESERVED VEHICLES ────────────────────────────────────────────────────────

def get_reserved_vehicles():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT * FROM reserved_vehicles
            WHERE is_active = TRUE
            ORDER BY expiry_date ASC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def add_reserved_vehicle(plate_number, owner_name, contact_number,
                          monthly_fee, start_date, expiry_date,
                          added_by_type, added_by):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO reserved_vehicles
            (plate_number, owner_name, contact_number, monthly_fee,
             start_date, expiry_date, added_by_type, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (plate_number.upper(), owner_name, contact_number,
              monthly_fee, start_date, expiry_date, added_by_type, added_by))
        conn.commit()
    except mysql.connector.IntegrityError:
        raise ValueError("Plate is already registered as reserved.")
    finally:
        cur.close(); conn.close()

def is_reserved_vehicle(plate_number):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT * FROM reserved_vehicles
            WHERE plate_number = %s AND is_active = TRUE
            AND expiry_date >= CURDATE()
        """, (plate_number.upper(),))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

def remove_reserved_vehicle(plate_number):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE reserved_vehicles SET is_active = FALSE WHERE plate_number = %s",
                    (plate_number.upper(),))
        conn.commit()
    finally:
        cur.close(); conn.close()

# ─── ANALYTICS ────────────────────────────────────────────────────────────────

def get_peak_hours():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT HOUR(time_in) AS hour, COUNT(*) AS vehicle_count
            FROM transactions
            WHERE status IN ('completed', 'active')
            GROUP BY HOUR(time_in)
            ORDER BY hour
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_vehicle_type_breakdown():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT vehicle_type, COUNT(*) AS count,
                   COALESCE(SUM(total_charge), 0) AS revenue
            FROM transactions
            WHERE status = 'completed'
            GROUP BY vehicle_type
            ORDER BY count DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_revenue_per_staff():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT s.full_name, s.username,
                   COUNT(t.id) AS transactions,
                   COALESCE(SUM(t.total_charge), 0) AS revenue
            FROM staff s
            LEFT JOIN transactions t ON t.staff_exit_id = s.id
            AND t.status = 'completed'
            GROUP BY s.id
            ORDER BY revenue DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_dashboard_summary():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM transactions
                 WHERE DATE(time_in) = CURDATE()) AS entries_today,
                (SELECT COUNT(*) FROM transactions
                 WHERE DATE(time_out) = CURDATE()
                 AND status = 'completed') AS exits_today,
                (SELECT COUNT(*) FROM transactions
                 WHERE status IN ('active','unknown')) AS currently_parked,
                (SELECT COALESCE(SUM(total_charge), 0)
                 FROM transactions
                 WHERE DATE(time_out) = CURDATE()
                 AND status = 'completed') AS revenue_today,
                (SELECT COUNT(*) FROM transactions t
                 JOIN settings se ON se.id = 1
                 WHERE t.status IN ('active','unknown')
                 AND TIMESTAMPDIFF(HOUR, t.time_in, NOW()) >= se.overstay_hours
                ) AS overstay_count,
                (SELECT parking_capacity FROM settings WHERE id = 1) AS capacity
        """)
        return cur.fetchone()
    finally:
        cur.close(); conn.close()

def get_overstay_vehicles():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT t.transaction_id, t.plate_number, t.vehicle_type,
                   t.time_in, t.date_in,
                   TIMESTAMPDIFF(HOUR, t.time_in, NOW()) AS hours_parked,
                   s.full_name AS staff_name
            FROM transactions t
            LEFT JOIN staff s ON t.staff_entry_id = s.id
            JOIN settings se ON se.id = 1
            WHERE t.status IN ('active','unknown')
            AND TIMESTAMPDIFF(HOUR, t.time_in, NOW()) >= se.overstay_hours
            ORDER BY t.time_in ASC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def get_notifications():
    """Returns recent flagged events for the notifications panel."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT 'shift' AS type, s.full_name AS name,
                   sh.shift_end AS event_time,
                   CONCAT('Cash discrepancy: reported P',
                   sh.staff_reported_revenue, ' vs system P',
                   sh.system_revenue) AS message
            FROM shifts sh
            JOIN staff s ON sh.staff_id = s.id
            WHERE sh.is_flagged = TRUE AND sh.is_resolved = FALSE

            UNION ALL

            SELECT 'overstay' AS type, t.plate_number AS name,
                   t.time_in AS event_time,
                   CONCAT('Overstay: parked for ',
                   TIMESTAMPDIFF(HOUR, t.time_in, NOW()), ' hours') AS message
            FROM transactions t
            JOIN settings se ON se.id = 1
            WHERE t.status IN ('active','unknown')
            AND TIMESTAMPDIFF(HOUR, t.time_in, NOW()) >= se.overstay_hours

            ORDER BY event_time DESC
            LIMIT 20
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()
# ─── EXPORT & REPORTS ─────────────────────────────────────────────────────────

def get_transactions_for_export(period='today'):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        if period == 'today':
            where = "WHERE DATE(t.time_in) = CURDATE()"
        elif period == 'yesterday':
            where = "WHERE DATE(t.time_in) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
        elif period == 'weekly':
            where = "WHERE t.time_in >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif period == 'monthly':
            where = "WHERE MONTH(t.time_in) = MONTH(CURDATE()) AND YEAR(t.time_in) = YEAR(CURDATE())"
        else:
            where = ""

        cur.execute(f"""
            SELECT t.transaction_id, t.plate_number, t.vehicle_type,
                   t.date_in, t.time_in, t.time_out,
                   t.duration_minutes, t.total_charge, t.status,
                   sen.full_name AS staff_entry, sex.full_name AS staff_exit
            FROM transactions t
            LEFT JOIN staff sen ON t.staff_entry_id = sen.id
            LEFT JOIN staff sex ON t.staff_exit_id = sex.id
            {where}
            ORDER BY t.time_in DESC
        """)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

# ─── TRANSACTION MANAGEMENT ───────────────────────────────────────────────────

def manually_close_transaction(transaction_id, admin_id, total_charge_override=None):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM transactions WHERE transaction_id = %s", (transaction_id,))
        txn = cur.fetchone()
        if not txn:
            return None
        now = datetime.now()
        duration_minutes = max(1, int((now - txn['time_in']).total_seconds() / 60))
        hours = duration_minutes / 60

        if total_charge_override is not None:
            total_charge = float(total_charge_override)
        else:
            cur.execute("SELECT * FROM settings WHERE id = 1")
            s = cur.fetchone()
            min_charge = float(s['minimum_charge'])
            total_charge = round(max(min_charge, hours * float(s['rate_per_hour'])), 2)

        cur.execute("""
            UPDATE transactions SET time_out=%s,
            duration_minutes=%s, total_charge=%s, status='completed'
            WHERE transaction_id=%s
        """, (now, duration_minutes, total_charge, transaction_id))
        conn.commit()
        return {
            'transaction_id': transaction_id,
            'plate_number': txn['plate_number'],
            'duration_minutes': duration_minutes,
            'total_charge': total_charge
        }
    finally:
        cur.close(); conn.close()

def edit_transaction(transaction_id, plate_number=None, vehicle_type=None,
                     total_charge=None, admin_id=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        updates = {}
        if plate_number: updates['plate_number'] = plate_number.upper()
        if vehicle_type: updates['vehicle_type'] = vehicle_type
        if total_charge is not None: updates['total_charge'] = total_charge
        if not updates:
            return
        cols = ', '.join(f"{k}=%s" for k in updates)
        vals = list(updates.values()) + [transaction_id]
        cur.execute(f"UPDATE transactions SET {cols} WHERE transaction_id=%s", vals)
        conn.commit()
    finally:
        cur.close(); conn.close()

# ─── STAFF MANAGEMENT ─────────────────────────────────────────────────────────

def set_staff_active(staff_id, is_active):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE staff SET is_active=%s WHERE id=%s", (is_active, staff_id))
        conn.commit()
    finally:
        cur.close(); conn.close()