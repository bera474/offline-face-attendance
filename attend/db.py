import sqlite3
import uuid
from .config import CFG

SCHEMA_SQL = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS students(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class TEXT,
    roll TEXT,
    status TEXT DEFAULT 'active',
    version INTEGER DEFAULT 0,
    updated_at TEXT,
    deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS embeddings(
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    model TEXT,
    quality REAL,
    vec BLOB NOT NULL,
    created_at TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS attendance(
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    device_id TEXT,
    ts TEXT,
    method TEXT,
    confidence REAL,
    synced INTEGER DEFAULT 0,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS devices(
    id TEXT PRIMARY KEY,
    school_id TEXT,
    room TEXT,
    version INTEGER DEFAULT 0
);
"""


def connect():
    conn = sqlite3.connect(CFG.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(school_id: str = "", room: str = ""):
    conn = connect()
    with conn:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute("SELECT value FROM meta WHERE key='device_id'").fetchone()
        if row is None:
            did = str(uuid.uuid4())
            conn.execute("INSERT INTO meta(key,value) VALUES('device_id',?)", (did,))
            conn.execute("INSERT OR IGNORE INTO devices(id, school_id, room, version) VALUES(?,?,?,0)",
                        (did, school_id, room))
            print(f"[db] Created device_id={did}")
        else:
            print(f"[db] device_id={row[0]}")
    print(f"[db] Ready at {CFG.DB_PATH}")


def get_device_id(conn) -> str:
    return conn.execute("SELECT value FROM meta WHERE key='device_id'").fetchone()[0]