import psycopg2
from psycopg2.extras import RealDictCursor
import os

def reset_sequences():
    # Connection string for live environment
    conn_str = os.environ.get('DATABASE_URL', "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb")
    
    print(f"Connecting to database to reset sequences...")
    
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # List of tables with auto-incrementing ID sequences
        tables = ['users', 'roles', 'permissions', 'menus', 'audit_log', 'user_password_history']
        
        for table in tables:
            try:
                # Check if table and sequence exist
                cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                if not cur.fetchone()['exists']:
                    print(f"Table '{table}' does not exist, skipping.")
                    continue
                
                # Get max ID
                cur.execute(f"SELECT MAX(id) FROM {table}")
                max_id = cur.fetchone()['max']
                
                if max_id is not None:
                    seq_name = f"{table}_id_seq"
                    # Reset sequence
                    cur.execute(f"SELECT setval('{seq_name}', %s, true)", (max_id,))
                    print(f"Successfully reset sequence '{seq_name}' to {max_id}.")
                else:
                    print(f"Table '{table}' is empty, skipping.")
                    
            except Exception as table_err:
                print(f"Note: Could not reset sequence for table '{table}': {table_err}")
                
        cur.close()
        conn.close()
        print("\nAll sequences have been synchronized with the current data.")
        print("You should now be able to save new users without IntegrityErrors.")
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    reset_sequences()
