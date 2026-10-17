import sqlite3

DB = "shop.db"

def init_db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        username TEXT,
        role TEXT DEFAULT 'buyer',
        balance REAL DEFAULT 0,
        login TEXT UNIQUE,
        password_hash TEXT,
        is_superadmin INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS superadmin_balance (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS balance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER,
        target_id INTEGER,
        amount REAL,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    con.commit()
    con.close()