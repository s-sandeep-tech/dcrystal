
import psycopg2
from psycopg2.extras import RealDictCursor

def find_test_user():
    conn_str = "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb"
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("Finding a user who is also an 'owner' in the summary table...")
        # Check column names first
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='owner_wise_order_summary_snapshot';")
        cols = [c['column_name'] for c in cur.fetchall()]
        print(f"Columns: {cols}")
        
        make_owner_col = "Make Owner" if "Make Owner" in cols else "make_owner"
        
        cur.execute(f'SELECT DISTINCT "{make_owner_col}" as owner FROM owner_wise_order_summary_snapshot LIMIT 10;')
        owners = cur.fetchall()
        print(f"Sample owners: {[o['owner'] for o in owners]}")
        
        # Look for these owners in the users table
        for owner in owners:
            owner_name = owner['owner']
            if not owner_name: continue
            
            # Simple match
            cur.execute("SELECT id, user_id, username FROM users WHERE username ILIKE %s;", (f"%{owner_name}%",))
            user = cur.fetchone()
            if user:
                print(f"Suggested test user: {user} (matches owner '{owner_name}')")
                break
        else:
            print("No direct match found.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_test_user()
