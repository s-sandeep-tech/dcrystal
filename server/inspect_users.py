
import psycopg2
from psycopg2.extras import RealDictCursor

def inspect_users():
    conn_str = "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb"
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("Checking for 'admin' user...")
        cur.execute("SELECT id, user_id, username, email, is_admin FROM users WHERE username = 'admin';")
        admin = cur.fetchone()
        if admin:
            print(f"Found admin: {admin}")
        else:
            print("Admin user NOT found by username='admin'.")
            
        print("\nChecking for user_id='U001'...")
        cur.execute("SELECT id, user_id, username, email, is_admin FROM users WHERE user_id = 'U001';")
        u001 = cur.fetchone()
        if u001:
            print(f"Found U001: {u001}")
        else:
            print("User with user_id='U001' NOT found.")

        print("\nTotal user count:")
        cur.execute("SELECT count(*) FROM users;")
        print(cur.fetchone())
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_users()
