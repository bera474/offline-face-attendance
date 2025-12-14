import os
import glob
import uuid
import cv2
import numpy as np
from .embeddings import Embedder
from .db import connect
from .utils import now_utc_iso
from .config import CFG

MODEL_TAG = CFG.PACK_MODEL_TAG


def enroll_from_dataset(dataset_dir: str):
    """
    Enroll students from a dataset directory with structure:
    dataset_dir/
        student1/
            img1.jpg
            img2.jpg
            ...
        student2/
            img1.jpg
            ...
    """
    emb = Embedder()
    conn = connect()
    now = now_utc_iso()

    for student_folder in glob.glob(os.path.join(dataset_dir, "*")):
        if not os.path.isdir(student_folder):
            continue

        name = os.path.basename(student_folder)
        print(f"[enroll] Processing {name}")

        vecs = []
        for img_path in glob.glob(os.path.join(student_folder, "*.jpg")):
            frame = cv2.imread(img_path)
            if frame is None:
                continue
            faces = emb.detect_and_embed(frame)
            if faces:
                vecs.append(faces[0]["embedding"])

        if not vecs:
            print(f"[enroll] No faces found for {name}; skipping")
            continue

        centroid = (np.mean(vecs, axis=0)).astype(np.float32)

        with conn:
            # Check if student already exists
            cursor = conn.execute(
                "SELECT id FROM students WHERE name = ?",
                (name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing student
                sid = existing[0]
                conn.execute("DELETE FROM embeddings WHERE student_id = ?", (sid,))
                conn.execute(
                    """
                    INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), sid, MODEL_TAG, 1.0, centroid.tobytes(), now),
                )
                print(f"[enroll] Updated: {name} with {len(vecs)} shots")
            else:
                # Insert new student
                sid = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO students(id, name, status, updated_at)
                    VALUES(?, ?, 'active', ?)
                    """,
                    (sid, name, now),
                )
                conn.execute(
                    """
                    INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), sid, MODEL_TAG, 1.0, centroid.tobytes(), now),
                )
                print(f"[enroll] New: {name} with {len(vecs)} shots")

    print("[enroll] done")
    conn.close()


def enroll_from_webcam(student_id: str | None = None, name: str | None = None, device: int = 0, n_shots: int = 8):
    """
    Enroll a student via webcam.
    Press SPACE to capture, ESC to finish.
    """
    emb = Embedder()
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"[enroll-cam] cannot open camera {device}")
        return

    nm = name or student_id or str(uuid.uuid4())
    
    # Check if student already exists
    conn = connect()
    cursor = conn.execute(
        "SELECT id FROM students WHERE name = ?",
        (nm,)
    )
    existing = cursor.fetchone()
    
    if existing:
        sid = existing[0]
        print(f"[enroll-cam] Student '{nm}' already exists. Updating enrollment...")
    else:
        sid = student_id or str(uuid.uuid4())
        print(f"[enroll-cam] New student: {nm}")
    
    conn.close()
    
    print(f"[enroll-cam] Enrolling {nm} ({sid}). SPACE to capture, ESC to finish.")

    vecs = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            disp = frame.copy()
            cv2.putText(
                disp,
                f"Captures: {len(vecs)} / {n_shots}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.imshow("Enroll", disp)
            k = cv2.waitKey(1) & 0xFF
            if k == 27:  # ESC
                break
            if k == 32:  # SPACE
                faces = emb.detect_and_embed(frame)
                if faces:
                    vecs.append(faces[0]["embedding"])  # first face
                    print(f"[enroll-cam] captured {len(vecs)}")
                    if len(vecs) >= n_shots:
                        break
                else:
                    print("[enroll-cam] no face detected; try again")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not vecs:
        print("[enroll-cam] no captures; aborted")
        return

    centroid = (np.mean(vecs, axis=0)).astype(np.float32)

    conn = connect()
    now = now_utc_iso()
    with conn:
        # Check if student already exists
        cursor = conn.execute(
            "SELECT id FROM students WHERE name = ?",
            (nm,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing student - delete old embedding and add new one
            existing_id = existing[0]
            conn.execute("DELETE FROM embeddings WHERE student_id = ?", (existing_id,))
            conn.execute(
                """
                INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), existing_id, MODEL_TAG, 1.0, centroid.tobytes(), now),
            )
            print(f"[enroll-cam] Updated: {nm} ({existing_id}) with {len(vecs)} shots")
        else:
            # Insert new student
            conn.execute(
                """
                INSERT INTO students(id, name, status, updated_at)
                VALUES(?, ?, 'active', ?)
                """,
                (sid, nm, now),
            )
            conn.execute(
                """
                INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), sid, MODEL_TAG, 1.0, centroid.tobytes(), now),
            )
            print(f"[enroll-cam] New: {nm} ({sid}) with {len(vecs)} shots")
    conn.close()


def update_student_image(name: str, device: int = 0, n_shots: int = 8):
    """
    Update an existing student's face image.
    Deletes old image and captures new one.
    """
    conn = connect()
    cursor = conn.execute("SELECT id FROM students WHERE name = ?", (name,))
    student = cursor.fetchone()
    conn.close()
    
    if not student:
        print(f"[update] Student '{name}' not found")
        return
    
    sid = student[0]
    print(f"[update] Updating {name}. SPACE to capture, ESC to finish.")
    
    emb = Embedder()
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"[update] Cannot open camera {device}")
        return
    
    vecs = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            disp = frame.copy()
            cv2.putText(
                disp,
                f"New captures: {len(vecs)} / {n_shots}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.imshow("Update Face", disp)
            k = cv2.waitKey(1) & 0xFF
            if k == 27:  # ESC
                break
            if k == 32:  # SPACE
                faces = emb.detect_and_embed(frame)
                if faces:
                    vecs.append(faces[0]["embedding"])
                    print(f"[update] Captured {len(vecs)}")
                    if len(vecs) >= n_shots:
                        break
                else:
                    print("[update] No face detected; try again")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    if not vecs:
        print("[update] No captures; aborted")
        return
    
    centroid = (np.mean(vecs, axis=0)).astype(np.float32)
    now = now_utc_iso()
    
    conn = connect()
    with conn:
        # Delete old embedding
        conn.execute("DELETE FROM embeddings WHERE student_id = ?", (sid,))
        # Insert new embedding
        conn.execute(
            """
            INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), sid, MODEL_TAG, 1.0, centroid.tobytes(), now),
        )
        # Update student timestamp
        conn.execute(
            "UPDATE students SET updated_at = ? WHERE id = ?",
            (now, sid),
        )
    conn.close()
    
    print(f"[update] ✓ Updated {name} with {len(vecs)} new shots")


def delete_student(name: str):
    """
    Delete a student and their enrollment data.
    """
    conn = connect()
    cursor = conn.execute("SELECT id FROM students WHERE name = ?", (name,))
    student = cursor.fetchone()
    
    if not student:
        print(f"[delete] Student '{name}' not found")
        conn.close()
        return
    
    sid = student[0]
    
    with conn:
        # Delete attendance records
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (sid,))
        # Delete embeddings
        conn.execute("DELETE FROM embeddings WHERE student_id = ?", (sid,))
        # Delete student
        conn.execute("DELETE FROM students WHERE id = ?", (sid,))
    
    conn.close()
    print(f"[delete] ✓ Deleted student '{name}' and all records")