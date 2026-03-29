import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SQLITE_DB = "foreks.db"
PG_URL = os.getenv("DATABASE_URL")

if not PG_URL or "postgresql" not in PG_URL:
    print("❌ DATABASE_URL is not set to PostgreSQL. Check your .env.")
    exit(1)

# Simple regex to parse PG URL: postgresql+asyncpg://user:pass@host:port/dbname
# Better way: use dsn
import re
match = re.search(r"postgresql\+asyncpg://(.*?):(.*?)@(.*?):(.*?)/(.*)", PG_URL)
if not match:
    # Try alternate format: postgresql://
    match = re.search(r"postgresql://(.*?):(.*?)@(.*?):(.*?)/(.*)", PG_URL)

if not match:
    print(f"❌ Could not parse PG_URL: {PG_URL}")
    exit(1)

user, password, host, port, dbname = match.groups()

def migrate():
    print(f"🔄 Migrating from {SQLITE_DB} to PostgreSQL ({host})...")
    
    try:
        sl_conn = sqlite3.connect(SQLITE_DB)
        sl_conn.row_factory = sqlite3.Row
        sl_cur = sl_conn.cursor()
        
        pg_conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        pg_cur = pg_conn.cursor()
        
        # Tables to migrate
        tables = ["trades", "decisions", "signals", "account_snapshots", "trading_hours"]
        
        for table in tables:
            print(f"  - Table: {table}...")
            
            # 1. Get Boolean columns in PG for this table to handleSQLite conversion
            pg_cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND data_type = 'boolean'
            """)
            bool_cols = [r[0] for r in pg_cur.fetchall()]
            
            # 2. Get data from SQLite
            sl_cur.execute(f"SELECT * FROM {table}")
            rows = sl_cur.fetchall()
            
            if not rows:
                print(f"    (Empty)")
                continue
                
            # 3. Prepare PG Insert
            columns = rows[0].keys()
            col_list = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            
            insert_query = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            
            # 4. Insert into PG with type conversion
            for row in rows:
                row_data = dict(row)
                # Convert 0/1 to True/False for boolean columns
                for col in bool_cols:
                    if col in row_data and row_data[col] is not None:
                        row_data[col] = bool(row_data[col])
                        
                pg_cur.execute(insert_query, tuple(row_data.values()))
                
            print(f"    Done. ({len(rows)} rows)")
            
        pg_conn.commit()
        print("✅ Migration successful!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        if 'sl_conn' in locals(): sl_conn.close()
        if 'pg_conn' in locals(): pg_conn.close()

if __name__ == "__main__":
    migrate()
