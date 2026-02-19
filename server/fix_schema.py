
import psycopg2
from psycopg2.extras import RealDictCursor

def fix_admin():
    conn_str = "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb"
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("Updating admin user with user_id='U001'...")
        cur.execute("UPDATE users SET user_id = 'U001' WHERE username = 'admin';")
        print("Admin user updated successfully.")
        
        cur.execute("SELECT id, user_id, username, email, is_admin FROM users WHERE username = 'admin';")
        print(cur.fetchone())
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_admin()
