import os
import glob
import uuid
import cv2
import numpy as np
from .embeddings import Embedder
from .db import connect
from .utils import now_utc_iso, cosine_sim
from .config import CFG
from .quality import overall_quality_score

MODEL_TAG = CFG.PACK_MODEL_TAG


def enroll_from_dataset(dataset_dir: str, class_name: str | None = None, roll: str | None = None):
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
        qualities = []
        for img_path in glob.glob(os.path.join(student_folder, "*.jpg")):
            frame = cv2.imread(img_path)
            if frame is None:
                continue
            faces = emb.detect_and_embed(frame)
            if faces:
                face = faces[0]
                quality_result = overall_quality_score(face["bbox"], face["kps"], frame)

                if quality_result["passed"]:
                    vecs.append(face["embedding"])
                    qualities.append(quality_result["score"])
                    print(f"  ✓ {os.path.basename(img_path)} - Quality: {quality_result['percentage']}%")
                else:
                    print(f"  ✗ {os.path.basename(img_path)} - Rejected: {', '.join(quality_result['issues'])}")

        if not vecs:
            print(f"[enroll] No quality faces found for {name}; skipping")
            continue

        centroid = (np.mean(vecs, axis=0)).astype(np.float32)
        avg_quality = np.mean(qualities) if qualities else 0.5

        with conn:
            cursor = conn.execute(
                "SELECT id FROM students WHERE name = ?",
                (name,)
            )
            existing = cursor.fetchone()

            if existing:
                sid = existing[0]
                conn.execute("DELETE FROM embeddings WHERE student_id = ?", (sid,))
                # Update class/roll if provided
                if class_name is not None or roll is not None:
                    updates, params = [], []
                    if class_name is not None:
                        updates.append("class = ?")
                        params.append(class_name)
                    if roll is not None:
                        updates.append("roll = ?")
                        params.append(roll)
                    updates.append("updated_at = ?")
                    params.append(now)
                    params.append(sid)
                    conn.execute(f"UPDATE students SET {', '.join(updates)} WHERE id = ?", params)
                conn.execute(
                    """
                    INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), sid, MODEL_TAG, avg_quality, centroid.tobytes(), now),
                )
                print(f"[enroll] Updated: {name} with {len(vecs)} quality shots (avg quality: {avg_quality:.2f})")
            else:
                sid = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO students(id, name, class, roll, status, updated_at)
                    VALUES(?, ?, ?, ?, 'active', ?)
                    """,
                    (sid, name, class_name, roll, now),
                )
                conn.execute(
                    """
                    INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), sid, MODEL_TAG, avg_quality, centroid.tobytes(), now),
                )
                print(f"[enroll] New: {name} with {len(vecs)} quality shots (avg quality: {avg_quality:.2f})")

    print("[enroll] done")
    conn.close()


def enroll_from_webcam(student_id: str | None = None, name: str | None = None, device: int = 0, n_shots: int = 8, class_name: str | None = None, roll: str | None = None):
    """
    Enroll a student via webcam with quality validation.
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
    print(f"[enroll-cam] Required: {n_shots} quality faces (quality >= {CFG.QUALITY_ACCEPT_THRESHOLD*100:.0f}%)")

    vecs = []
    qualities = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            disp = frame.copy()

            # Display counter
            cv2.putText(
                disp,
                f"Captures: {len(vecs)} / {n_shots}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )

            # Try to detect face and show quality
            faces = emb.detect_and_embed(frame)
            if faces:
                face = faces[0]
                bbox = face["bbox"]
                quality_result = overall_quality_score(bbox, face["kps"], frame)

                # Draw bbox
                x1, y1, x2, y2 = bbox
                color = (0, 255, 0) if quality_result["passed"] else (0, 165, 255)
                cv2.rectangle(disp, (x1, y1), (x2, y2), color, 2)

                # Show quality score
                quality_text = f"Quality: {quality_result['percentage']}%"
                cv2.putText(
                    disp,
                    quality_text,
                    (x1, y1 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

                # Show status
                if quality_result["issues"]:
                    issues_text = " | ".join(quality_result["issues"][:2])
                    cv2.putText(
                        disp,
                        issues_text,
                        (x1, y1 - 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 165, 255),
                        1,
                    )

                # Show instruction for SPACE
                instruction = "SPACE to capture" if quality_result["passed"] else "Face too low quality"
                cv2.putText(
                    disp,
                    instruction,
                    (10, disp.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0) if quality_result["passed"] else (0, 0, 255),
                    2,
                )

            cv2.imshow("Enroll", disp)
            k = cv2.waitKey(1) & 0xFF

            if k == 27:  # ESC
                break

            if k == 32:  # SPACE
                faces = emb.detect_and_embed(frame)
                if faces:
                    face = faces[0]
                    quality_result = overall_quality_score(face["bbox"], face["kps"], frame)

                    if quality_result["passed"]:
                        vecs.append(face["embedding"])
                        qualities.append(quality_result["score"])
                        print(f"[enroll-cam] ✓ Captured {len(vecs)}/{n_shots} (Quality: {quality_result['percentage']}%)")
                        if len(vecs) >= n_shots:
                            break
                    else:
                        print(f"[enroll-cam] ✗ Rejected (Quality: {quality_result['percentage']}%) - {', '.join(quality_result['issues'][:2])}")
                else:
                    print("[enroll-cam] No face detected; try again")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not vecs:
        print("[enroll-cam] No captures; aborted")
        return

    avg_quality = np.mean(qualities) if qualities else 0.5
    centroid = (np.mean(vecs, axis=0)).astype(np.float32)

    conn = connect()
    now = now_utc_iso()
    with conn:
        cursor = conn.execute(
            "SELECT id FROM students WHERE name = ?",
            (nm,)
        )
        existing = cursor.fetchone()

        if existing:
            existing_id = existing[0]
            conn.execute("DELETE FROM embeddings WHERE student_id = ?", (existing_id,))
            # Update class/roll if provided
            if class_name is not None or roll is not None:
                updates, params = [], []
                if class_name is not None:
                    updates.append("class = ?")
                    params.append(class_name)
                if roll is not None:
                    updates.append("roll = ?")
                    params.append(roll)
                updates.append("updated_at = ?")
                params.append(now)
                params.append(existing_id)
                conn.execute(f"UPDATE students SET {', '.join(updates)} WHERE id = ?", params)
            conn.execute(
                """
                INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), existing_id, MODEL_TAG, avg_quality, centroid.tobytes(), now),
            )
            print(f"[enroll-cam] ✓ Updated: {nm} ({existing_id}) with {len(vecs)} quality shots (avg quality: {avg_quality:.2f})")
        else:
            conn.execute(
                """
                INSERT INTO students(id, name, class, roll, status, updated_at)
                VALUES(?, ?, ?, ?, 'active', ?)
                """,
                (sid, nm, class_name, roll, now),
            )
            conn.execute(
                """
                INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), sid, MODEL_TAG, avg_quality, centroid.tobytes(), now),
            )
            print(f"[enroll-cam] ✓ New: {nm} ({sid}) with {len(vecs)} quality shots (avg quality: {avg_quality:.2f})")
    conn.close()


def update_student_image(name: str, device: int = 0, n_shots: int = 8):
    """
    Update an existing student's face image with quality validation.
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
    print(f"[update] Required: {n_shots} quality faces (quality >= {CFG.QUALITY_ACCEPT_THRESHOLD*100:.0f}%)")

    emb = Embedder()
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"[update] Cannot open camera {device}")
        return

    vecs = []
    qualities = []
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

            # Show quality feedback
            faces = emb.detect_and_embed(frame)
            if faces:
                face = faces[0]
                bbox = face["bbox"]
                quality_result = overall_quality_score(bbox, face["kps"], frame)

                x1, y1, x2, y2 = bbox
                color = (0, 255, 0) if quality_result["passed"] else (0, 165, 255)
                cv2.rectangle(disp, (x1, y1), (x2, y2), color, 2)

                quality_text = f"Quality: {quality_result['percentage']}%"
                cv2.putText(
                    disp,
                    quality_text,
                    (x1, y1 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

            cv2.imshow("Update Face", disp)
            k = cv2.waitKey(1) & 0xFF
            if k == 27:  # ESC
                break
            if k == 32:  # SPACE
                faces = emb.detect_and_embed(frame)
                if faces:
                    face = faces[0]
                    quality_result = overall_quality_score(face["bbox"], face["kps"], frame)

                    if quality_result["passed"]:
                        vecs.append(face["embedding"])
                        qualities.append(quality_result["score"])
                        print(f"[update] ✓ Captured {len(vecs)}/{n_shots} (Quality: {quality_result['percentage']}%)")
                        if len(vecs) >= n_shots:
                            break
                    else:
                        print(f"[update] ✗ Rejected (Quality: {quality_result['percentage']}%) - {', '.join(quality_result['issues'][:2])}")
                else:
                    print("[update] No face detected; try again")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not vecs:
        print("[update] No captures; aborted")
        return

    avg_quality = np.mean(qualities) if qualities else 0.5
    centroid = (np.mean(vecs, axis=0)).astype(np.float32)
    now = now_utc_iso()

    conn = connect()
    with conn:
        conn.execute("DELETE FROM embeddings WHERE student_id = ?", (sid,))
        conn.execute(
            """
            INSERT INTO embeddings(id, student_id, model, quality, vec, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), sid, MODEL_TAG, avg_quality, centroid.tobytes(), now),
        )
        conn.execute(
            "UPDATE students SET updated_at = ? WHERE id = ?",
            (now, sid),
        )
    conn.close()

    print(f"[update] ✓ Updated {name} with {len(vecs)} quality shots (avg quality: {avg_quality:.2f})")


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