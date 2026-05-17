from utils.database import get_connection

conn = get_connection()
cur = conn.cursor(dictionary=True)
cur.execute("SELECT status, COUNT(*) as cnt, SUM(total_charge) as total FROM transactions WHERE DATE(time_out) = CURDATE() GROUP BY status")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()