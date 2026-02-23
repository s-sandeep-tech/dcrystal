import psycopg2
from psycopg2.extras import RealDictCursor
import os
import re

def get_conn_str():
    # 1. Try SQLALCHEMY_DATABASE_URI (used by the Flask app)
    sqlalchemy_uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
    if sqlalchemy_uri:
        # Convert sqlalchemy format (postgresql+psycopg2://) to psycopg2 format (postgresql://)
        return sqlalchemy_uri.replace('postgresql+psycopg2://', 'postgresql://')

    # 2. Try DATABASE_URL
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url

    # 3. Fallback to common defaults for this project
    # We will return a list of potential connection strings to try
    return [
        "postgresql://meetaccess:meetpass@db:5432/dcrystaldb",      # Docker internal
        "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb", # Host mapped
        "postgresql://meetaccess:meetpass@localhost:5432/dcrystaldb"  # Standard local
    ]

def reset_sequences():
    conn_configs = get_conn_str()
    if isinstance(conn_configs, str):
        conn_configs = [conn_configs]

    conn = None
    for config in conn_configs:
        try:
            # Mask password for logging
            masked_config = re.sub(r':([^/@]+)@', ':****@', config)
            print(f"Trying to connect to: {masked_config}")
            
            conn = psycopg2.connect(config, connect_timeout=3)
            print("Successfully connected to the database!")
            break
        except Exception as e:
            print(f"Failed to connect using this config: {e}")
            continue

    if not conn:
        print("\nERROR: Could not connect to the database using any known configuration.")
        print("Please ensure your database is running and check your connection settings.")
        print("Tip: If using Docker, try: docker-compose exec server python3 scripts/reset_sequences_live.py")
        return

    try:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # List of tables with auto-incrementing ID sequences
        tables = ['users', 'roles', 'permissions', 'menus', 'audit_log', 'user_password_history']
        
        print("\nSynchronizing sequences...")
        for table in tables:
            try:
                # Check if table exists
                cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table,))
                if not cur.fetchone()['exists']:
                    continue
                
                # Get max ID
                cur.execute(f"SELECT MAX(id) FROM {table}")
                max_id = cur.fetchone()['max']
                
                if max_id is not None:
                    seq_name = f"{table}_id_seq"
                    # Reset sequence
                    cur.execute(f"SELECT setval(%s, %s, true)", (seq_name, max_id))
                    print(f"  - {table}: set to {max_id}")
                else:
                    print(f"  - {table}: empty, skipping")
                    
            except Exception as table_err:
                # Some tables might not have id or id sequence
                pass
                
        cur.close()
        conn.close()
        print("\nAll sequences have been synchronized with the current data.")
        print("The IntegrityError (duplicate key) should now be resolved.")
        
    except Exception as e:
        print(f"Error during sequence reset: {e}")

if __name__ == "__main__":
    reset_sequences()
