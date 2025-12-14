# Offline Face Attendance System - Simple User Guide

**Version:** 1.0.0  
**Status:** ✅ Ready to Use

---

## What You Can Do

1. **Initialize** - Setup the system (first time only)
2. **Enroll Students** - Add students and capture their face
3. **Update Photo** - Change a student's face image
4. **Delete Student** - Remove a student from system
5. **Mark Attendance** - Students come, system recognizes and marks present
6. **View Attendance** - See who came today and export to Excel

---

## Installation (One Time)

### Step 1: Open Command Prompt
- **Windows:** Press `Win + R`, type `cmd`, press Enter
- **Mac/Linux:** Open Terminal

### Step 2: Go to Project Folder
```bash
cd offline_attendance
```

### Step 3: Install Requirements
```bash
pip install -r requirements.txt
```

Done! ✅

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
1. Command opens webcam
2. **Press SPACE** to capture face (8 times)
3. **Press ESC** when done
4. System saves student face
5. Repeat for each student

**Good tips:**
- Good lighting (near window)
- Face centered in camera
- Different angles (left, right, straight)

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

### 5️⃣ Mark Attendance (Live)
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

### 6️⃣ View Attendance
```bash
python view_attendance.py
```

**Shows:**
- All students marked today
- Time and confidence score
- Summary (Present/Absent)

**Create Excel File:**
```bash
python view_attendance.py --excel
```

Creates: `attendance_report.xlsx` - Open in Excel/Google Sheets

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

---

## File Locations

- **Database:** `attendance.db` (in same folder)
- **Excel Report:** `attendance_report.xlsx` (same folder)
- **CSV Report:** `attendance_report.csv` (same folder)

---

## Summary

**6 Simple Steps:**

1. **Setup** → `python main.py init --school-id "School" --room "Room"`
2. **Enroll** → `python main.py enroll --name "Student Name"`
3. **Update Photo** → `python main.py update --name "Student Name"` (if needed)
4. **Delete** → `python main.py delete --name "Student Name"` (if needed)
5. **Mark** → `python main.py run`
6. **View** → `python view_attendance.py --excel`

That's it! ���

For help:
```bash
python main.py --help
```

---

**Happy attendance tracking!** ���
