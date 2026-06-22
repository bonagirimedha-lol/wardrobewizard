# backend/services/db_service.py
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'wardrobewizard.db')

def setup_sqlite_db(conn):
    """Create tables in SQLite if they don't exist and seed default user"""
    cur = conn.cursor()
    
    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")
    
    # Create Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        style_preferences TEXT DEFAULT '{"casual": 5, "formal": 3, "athletic": 2}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create Clothing Items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS clothing_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        name TEXT,
        category TEXT NOT NULL,
        subcategory TEXT,
        color_primary TEXT,
        color_secondary TEXT,
        pattern TEXT DEFAULT 'solid',
        style TEXT,
        season TEXT, -- JSON array of seasons
        image_url TEXT,
        image_processed BOOLEAN DEFAULT FALSE,
        brand TEXT,
        purchase_date TEXT,
        times_worn INTEGER DEFAULT 0,
        last_worn TEXT,
        favorite BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create Outfits
    cur.execute("""
    CREATE TABLE IF NOT EXISTS outfits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        name TEXT,
        occasion TEXT,
        season TEXT,
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        times_worn INTEGER DEFAULT 0,
        last_worn TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create Outfit Items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS outfit_items (
        outfit_id INTEGER REFERENCES outfits(id) ON DELETE CASCADE,
        item_id INTEGER REFERENCES clothing_items(id) ON DELETE CASCADE,
        position INTEGER,
        PRIMARY KEY (outfit_id, item_id)
    );
    """)
    
    # Create Weather Preferences
    cur.execute("""
    CREATE TABLE IF NOT EXISTS weather_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        weather_condition TEXT,
        preference TEXT
    );
    """)
    
    # Create Shopping Suggestions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shopping_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        category TEXT,
        reason TEXT,
        priority INTEGER DEFAULT 3,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create Feedbacks
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        image_path TEXT,
        predicted_category TEXT,
        corrected_category TEXT,
        predicted_color TEXT,
        corrected_color TEXT,
        rating INTEGER,
        comment TEXT,
        used_for_training BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Seed default user with ID = 1 if no users exist
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        # Default password is 'password' hashed or similar, let's just insert a demo user
        # Note: We hardcode id=1 so that FOREIGN KEY constraints match the frontend's default user_id=1
        cur.execute("""
        INSERT INTO users (id, username, email, password_hash)
        VALUES (1, 'demo_user', 'demo@wardrobewizard.com', 'pbkdf2:sha256:260000$default_password_hash')
        """)
        
    conn.commit()
    cur.close()

class DBCursorWrapper:
    def __init__(self, raw_cursor, is_sqlite=False):
        self.raw_cursor = raw_cursor
        self.is_sqlite = is_sqlite

    def execute(self, query, params=None):
        if self.is_sqlite:
            # Replace %s with ?
            query = query.replace('%s', '?')
            
            # Remove Postgres-specific RETURNING id if it's there
            returning_id = False
            if 'RETURNING id' in query:
                query = query.replace('RETURNING id', '')
                returning_id = True
            
            # Map parameters
            processed_params = []
            if params:
                for p in params:
                    if isinstance(p, (list, dict)):
                        processed_params.append(json.dumps(p))
                    else:
                        processed_params.append(p)
                processed_params = tuple(processed_params)
            else:
                processed_params = ()
                
            self.raw_cursor.execute(query, processed_params)
            
            # If query was an INSERT with RETURNING id, we simulate RETURNING id output
            if returning_id:
                # Store last inserted id
                self._lastrowid = self.raw_cursor.lastrowid
        else:
            self.raw_cursor.execute(query, params)
            
    def fetchall(self):
        rows = self.raw_cursor.fetchall()
        if self.is_sqlite:
            return [self._row_to_dict(r) for r in rows]
        return rows

    def fetchone(self):
        row = self.raw_cursor.fetchone()
        if self.is_sqlite:
            if hasattr(self, '_lastrowid'):
                # Simulate returning ID
                val = self._lastrowid
                delattr(self, '_lastrowid')
                return {'id': val}
            return self._row_to_dict(row) if row else None
        return row

    def close(self):
        self.raw_cursor.close()

    def _row_to_dict(self, row):
        if row is None:
            return None
        res = dict(row)
        # Parse season from JSON string if present
        if 'season' in res and isinstance(res['season'], str):
            try:
                res['season'] = json.loads(res['season'])
            except Exception:
                pass
        return res

class DBConnectionWrapper:
    def __init__(self, raw_conn, is_sqlite=False):
        self.raw_conn = raw_conn
        self.is_sqlite = is_sqlite

    def cursor(self, cursor_factory=None):
        if self.is_sqlite:
            # Configure sqlite to return rows that act like dictionaries
            self.raw_conn.row_factory = sqlite3.Row
            return DBCursorWrapper(self.raw_conn.cursor(), is_sqlite=True)
        else:
            return DBCursorWrapper(self.raw_conn.cursor(cursor_factory=cursor_factory), is_sqlite=False)

    def commit(self):
        self.raw_conn.commit()

    def close(self):
        self.raw_conn.close()

def get_db_connection():
    """Get database connection, falling back to SQLite if PostgreSQL fails"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Try PostgreSQL first
    if database_url or os.environ.get('DB_HOST'):
        try:
            if database_url:
                conn = psycopg2.connect(database_url)
            else:
                conn = psycopg2.connect(
                    host=os.environ.get('DB_HOST', 'localhost'),
                    database=os.environ.get('DB_NAME', 'wardrobewizard'),
                    user=os.environ.get('DB_USER', 'postgres'),
                    password=os.environ.get('DB_PASSWORD', 'password'),
                    connect_timeout=3 # fail fast
                )
            return DBConnectionWrapper(conn, is_sqlite=False)
        except Exception as e:
            print(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
            
    # Fallback to SQLite
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    setup_sqlite_db(conn)
    return DBConnectionWrapper(conn, is_sqlite=True)
