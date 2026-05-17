from utils.database import get_connection

conn = get_connection()
cur = conn.cursor()

migrations = [
    "ALTER TABLE shifts ADD COLUMN is_resolved BOOLEAN DEFAULT FALSE",
]

for sql in migrations:
    try:
        cur.execute(sql)
        print('OK:', sql[:60])
    except Exception as e:
        print('Skipped:', e)

conn.commit()
cur.close()
conn.close()
print('Done!')