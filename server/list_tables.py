
import psycopg2

def list_tables():
    conn_str = "postgresql://meetaccess:meetpass@localhost:5433/dcrystaldb"
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        print("Listing tables...")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cur.fetchall()
        for table in tables:
            print(table[0])
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables()
