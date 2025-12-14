import uuid
from datetime import datetime
from .db import connect
from .utils import now_utc_iso


def mark_attendance(student_id: str, device_id: str, method: str = "face", confidence: float = 0.0):
    """
    Mark attendance for a student.
    """
    conn = connect()
    now = now_utc_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO attendance(id, student_id, device_id, ts, method, confidence, synced)
            VALUES(?, ?, ?, ?, ?, ?, 0)
            """,
            (str(uuid.uuid4()), student_id, device_id, now, method, confidence),
        )
    conn.close()


def get_attendance_today(student_id: str | None = None, device_id: str | None = None) -> list:
    """
    Get attendance records for today.
    """
    conn = connect()
    query = "SELECT id, student_id, device_id, ts, method, confidence FROM attendance WHERE ts LIKE ?"
    today = datetime.utcnow().strftime("%Y-%m-%d")
    params = [f"{today}%"]

    if student_id:
        query += " AND student_id = ?"
        params.append(student_id)
    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_student_count_today(device_id: str | None = None) -> int:
    """
    Get count of unique students marked present today.
    """
    conn = connect()
    query = "SELECT COUNT(DISTINCT student_id) FROM attendance WHERE ts LIKE ?"
    today = datetime.utcnow().strftime("%Y-%m-%d")
    params = [f"{today}%"]

    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)

    count = conn.execute(query, params).fetchone()[0]
    conn.close()
    return count
