
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def inspect_users_table():
    # Attempt to get connection string from env or use known one
    conn_str = os.environ.get('DATABASE_URL', "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb")
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("Inspecting 'users' table column defaults and types...")
        cur.execute("""
            SELECT column_name, column_default, is_nullable, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"Column: {col['column_name']}, Default: {col['column_default']}, Nullable: {col['is_nullable']}, Type: {col['data_type']}")
            
        cur.execute("SELECT count(*) FROM users;")
        count = cur.fetchone()['count']
        print(f"Current user count: {count}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error inspecting database: {e}")

if __name__ == "__main__":
    inspect_users_table()
