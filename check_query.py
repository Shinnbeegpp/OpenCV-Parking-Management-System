from utils.database import get_connection

conn = get_connection()
cur = conn.cursor(dictionary=True)

# Test the exact query used in get_revenue_today
cur.execute("""
    SELECT COALESCE(SUM(total_charge), 0) as rev
    FROM transactions 
    WHERE DATE(time_out) = CURDATE() 
    AND status='completed'
""")
print("Revenue today:", cur.fetchone())

cur.close()
conn.close()