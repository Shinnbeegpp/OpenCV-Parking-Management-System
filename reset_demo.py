import os
import sys
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'connection_timeout': 10,
    'ssl_ca': 'utils/ca.pem',
}

TABLES_TO_CLEAR = ['activity_logs', 'transactions', 'shifts']

def reset_demo():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        counts = {}
        for table in TABLES_TO_CLEAR:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

        confirm = input(
            f"\nThis will permanently delete:\n"
            + "\n".join(f"  {table}: {counts[table]} record(s)" for table in TABLES_TO_CLEAR)
            + "\n\nProceed? (yes/no): "
        ).strip().lower()

        if confirm != 'yes':
            print("Reset cancelled.")
            return

        for table in TABLES_TO_CLEAR:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  Cleared {table} ({counts[table]} record(s) removed)")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        print("\nDemo reset complete. Staff, admins, settings, blacklist, and reserved vehicles are intact.")

    except Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'cursor' in dir():
            cursor.close()
        if 'conn' in dir() and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    reset_demo()
