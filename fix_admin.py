import sys
sys.path.insert(0, '.')
from utils.database import hash_password, get_connection

password = "admin123"
hashed = hash_password(password)
print(f"Hash: {hashed}")

conn = get_connection()
cur = conn.cursor()
cur.execute("USE parkease;")
cur.execute("DELETE FROM admins WHERE username = 'admin';")
cur.execute(
    "INSERT INTO admins (username, password_hash, full_name) VALUES (%s, %s, %s)",
    ('admin', hashed, 'System Administrator')
)
conn.commit()
print("Admin account reset successfully. Login with admin / admin123")
cur.close()
conn.close()