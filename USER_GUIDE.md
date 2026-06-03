# Offline Face Attendance System - Simple User Guide

**Version:** 1.0.0  
**Status:** ✅ Ready to Use

---

## What You Can Do

1. **Initialize** - Setup the system (first time only)
2. **Enroll Students** - Add students and capture their face
3. **Update Photo** - Change a student's face image
4. **Delete Student** - Remove a student from system
5. **Delete Attendance** - Remove attendance records for a specific date
6. **Mark Attendance** - Students come, system recognizes and marks present
7. **View Attendance** - See who came today and export to Excel

---

## Installation (One Time)

### Step 1: Open Command Prompt
- **Windows:** Press `Win + R`, type `cmd`, press Enter
- **Mac/Linux:** Open Terminal

### Step 2: Go to Project Folder
```bash
cd offline-face-attendance
```

### Step 3: Install Requirements
```bash
pip install -r requirements.txt
```

### Step 4: Pre-download Models (Crucial for Offline Setup)
Before disconnecting from the internet, run the download command to fetch the face detection and anti-spoof models:
```bash
python main.py download-models --antispoof
```

Done! System is ready for fully offline use. ✅

---

## How to Use

### 1️⃣ Initialize System (First Time Only)
```bash
python main.py init --school-id "Your School" --room "Class A"
```

**What it does:**
- Creates database file
- Generates device ID
- System ready to use

**Run this ONCE at the beginning.**

---

### 2️⃣ Enroll a Student
```bash
python main.py enroll --name "John Doe"
```

**Steps:**
1. Command opens webcam.
2. The system checks face quality (size, blur, lighting, and head rotation) in real-time.
   * **Orange Box**: Face is low quality. Look at the on-screen messages (e.g., "Face too blurry, hold still", "Too dark", or "Head rotated") and adjust.
   * **Green Box**: Face quality is good. **Press SPACE** to capture a snapshot.
3. Capture **8 shots** from different angles (look straight, slightly left, slightly right, tilt up/down) to ensure high recognition accuracy.
4. **Press ESC** when done (or wait for 8 shots to finish).
5. The system calculates and registers the averaged face signature in the database.

**Good tips:**
- Good lighting (facing a light source or window) is highly recommended.
- Avoid extreme angles or heavy shadows on the face.
- Remove caps or dark glasses during enrollment.

---

### 3️⃣ Update Student's Photo
```bash
python main.py update --name "John Doe"
```

**What it does:**
1. Finds student in database
2. Deletes old face image
3. Opens webcam for new captures
4. **Press SPACE** to capture (8 times)
5. **Press ESC** when done
6. System saves new photo

**Use when:** Student's appearance changed or photo quality was poor

---

### 4️⃣ Delete a Student
```bash
python main.py delete --name "John Doe"
```

**What it does:**
- Removes student from database
- Deletes all face images
- Deletes all attendance records

**Use when:** Student left the class or school

---

### 5️⃣ Delete Attendance for a Date
```bash
python main.py delete-attendance --date 2026-06-02
```

**What it does:**
- Deletes ALL attendance records for the given date
- Asks for confirmation before deleting
- Shows how many records were deleted

**Options:**
- `--date YYYY-MM-DD` — Date to delete (defaults to today if not given)
- `--yes` or `-y` — Skip the confirmation prompt

**Examples:**
```bash
# Delete today's attendance
python main.py delete-attendance

# Delete a specific date
python main.py delete-attendance --date 2025-12-13

# Delete without confirmation
python main.py delete-attendance --date 2025-12-13 --yes
```

**Use when:** Attendance was marked by mistake or you need to redo a day

---

### 6️⃣ Mark Attendance (Live)
```bash
python main.py run
```

**What happens:**
1. Webcam opens showing live video
2. Students come in front of camera
3. System recognizes them automatically
4. Shows "✓ Name (confidence)" in green box
5. Attendance is marked
6. Press **Q** to stop

**Counter shows:** "Present Today: 5" (number of students)

---

### 7️⃣ View & Export Attendance
```bash
python view_attendance.py
```

**Shows:**
- Detailed list of students marked on the latest date in the database.
- Marks timestamp, roll number, class, and recognition confidence score.
- A summary table counting total registered students, present students, and absent students.

**Advanced Options:**
```bash
# Export to Excel (generates formatted report with color coding)
python view_attendance.py --excel

# Export to CSV (flat spreadsheet)
python view_attendance.py --csv

# Create both Excel and CSV
python view_attendance.py --all

# View attendance for a specific date
python view_attendance.py --date 2026-06-03

# Filter details by student name
python view_attendance.py --name "John"

# Output report to custom filename
python view_attendance.py --excel --output my_custom_report
```

---

## Summary of Commands

```bash
# First time setup
python main.py init --school-id "School Name" --room "Room"

# Enroll students
python main.py enroll --name "Student Name"

# Update student's photo
python main.py update --name "Student Name"

# Delete student
python main.py delete --name "Student Name"

# Delete attendance for a date
python main.py delete-attendance --date 2026-06-02

# Mark attendance (run during class)
python main.py run

# View today's attendance
python view_attendance.py

# Create Excel report
python view_attendance.py --excel
```

---

## Keyboard Controls

| Key | What it does | When to use |
|-----|--------------|------------|
| SPACE | Capture face | During enrollment |
| ESC | Finish enrollment | During enrollment |
| Q | Stop attendance | During attendance marking |

---

## Troubleshooting

### Problem: Webcam won't open
**Solution:** Try different camera:
```bash
python main.py enroll --name "John" --device 1
```
(Try device 0, 1, 2...)

### Problem: Face not detected during enrollment
**Solution:** 
- Move closer to camera
- Make sure face is visible
- Improve lighting

### Problem: Wrong person recognized
**Solution:** Re-enroll with more captures:
```bash
python main.py enroll --name "John Doe" --shots 12
```

### Problem: Person not recognized
**Solution:** Same as above - enroll again with better lighting

### Problem: Face marked as "SPOOF" (rejected during attendance)
**Explanation:** The system detected the face is not live (likely a photo, screen, or mask)

**Solution:**
- Make sure the student is physically present (not showing a photo)
- Ensure good lighting and face is clearly visible
- Try moving closer to the camera
- If you need to disable liveness detection temporarily:
```bash
ATTEND_LIVENESS=0 python main.py run
```

### Problem: Liveness detection too strict
**Solution:** Lower the liveness threshold:
```bash
# On Windows PowerShell:
$env:ATTEND_LIVENESS_THRESHOLD="0.60"; python main.py run

# On Windows Command Prompt:
set ATTEND_LIVENESS_THRESHOLD=0.60 && python main.py run

# On Linux/macOS:
ATTEND_LIVENESS_THRESHOLD=0.60 python main.py run
```
(Lower = more lenient, Higher = more strict. Default is 0.80)

---

## File Locations

- **Database:** `attendance.db` (in same folder)
- **Excel Report:** `attendance_report.xlsx` (same folder)
- **CSV Report:** `attendance_report.csv` (same folder)

---

## Summary

**7 Simple Steps:**

1. **Setup** → `python main.py init --school-id "School" --room "Room"`
2. **Enroll** → `python main.py enroll --name "Student Name"`
3. **Update Photo** → `python main.py update --name "Student Name"` (if needed)
4. **Delete Student** → `python main.py delete --name "Student Name"` (if needed)
5. **Delete Attendance** → `python main.py delete-attendance --date YYYY-MM-DD` (if needed)
6. **Mark** → `python main.py run`
7. **View** → `python view_attendance.py --excel`

That's it! ���

For help:
```bash
python main.py --help
```

---

**Happy attendance tracking!** ���
