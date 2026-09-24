# Customer Data Hub (Siamchai & TrueCorp Unified Extractor)

ระบบดึงและตรวจสอบข้อมูลอัตโนมัติแบบรวมศูนย์ (Unified Intelligence Hub) รวมการทำงานของ **สยามชัย (Siamchai SecureStock)** และ **ทรู (TrueCorp Pre-Verify)** เข้าไว้ในหน้าแดชบอร์ดเดียว พร้อมระบบ **จำกัดสิทธิ์การใช้งาน (Web Login Authentication)** และการส่งออกผลลัพธ์เป็นไฟล์ Excel รวม 3 Sheets ในคลิกเดียว

---

## 🌟 ฟีเจอร์เด่น (Key Features)

1. **ระบบ Login จำกัดสิทธิ์การใช้งาน (Authentication & Security)**
   * ป้องกันผู้ไม่มีสิทธิ์เข้าใช้งาน มีหน้าจอลงชื่อเข้าใช้งานที่สวยงามและปลอดภัย
   * บันทึก Session ปลอดภัย และสามารถเปลี่ยนรหัสผ่านได้ผ่านเมนูการตั้งค่า

2. **รวมศูนย์ 2 ระบบไว้ในไฟล์เดียว (All-in-One File Upload)**
   * อัปโหลดไฟล์ Excel (.xlsx, .csv) แค่ 1 ไฟล์ หรือพิมพ์/วางเลขบัตรประชาชน
   * เลือกโหมดการค้นหาได้อิสระ:
     - 🟣 ค้นหาสยามชัย (ดึงข้อมูลสัญญา 17 คอลัมน์: เบอร์โทร, ที่อยู่, ที่ทำงาน, ผู้ค้ำ ฯลฯ)
     - 🔴 ค้นหาทรู (ตรวจเบอร์ที่เปิดใช้งานอยู่ Active Numbers และสถานะทุกเบอร์)
     - ⚡ **ค้นหาทั้ง 2 ระบบพร้อมกัน (Concurrent Processing)** ประหยัดเวลา 50%

3. **หน้าจอถ่ายทอดสดแบบคู่ (Dual Live Browser View)**
   * สลับดูหน้าจอการทำงานของบอทได้แบบเรียลไทม์: จอสยามชัย และ จอทรู
   * แสดงความคืบหน้า (Progress Bar) และ System Terminal Logs ละเอียดทุกวินาที

4. **ส่งออก Excel รวม 3 Sheets (Multi-Sheet Excel Export)**
   * **Sheet 1: สรุปรวม (Unified Summary)** รวมเลขบัตร, ชื่อ, สถานะสยามชัย, เบอร์สยามชัย, เบอร์ทรู (Active), ข้อมูลผู้ค้ำ
   * **Sheet 2: สยามชัย (17 คอลัมน์)** รายละเอียดสัญญาเช่าซื้อสยามชัยฉบับเต็ม
   * **Sheet 3: ทรู (True Pre-Verify)** รายละเอียดเบอร์โทรศัพท์ทรูและสถานะทั้งหมด

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```text
siamchai_true_hub/
├── backend/
│   ├── app.py                # FastAPI Web Server & REST Endpoints
│   ├── auth.py               # Token & Cookie Authentication
│   ├── siamchai_crawler.py   # บอทดึงข้อมูลสยามชัย (17 คอลัมน์)
│   ├── true_crawler.py       # บอทดึงข้อมูลทรู (Pre-Verify)
│   ├── storage.py            # จัดการไฟล์ Excel & Config
│   └── unified_engine.py     # ตัวควบคุมการรันทั้ง 2 ระบบพร้อมกัน
├── static/
│   ├── index.html            # หน้าแดชบอร์ดหลัก
│   ├── login.html            # หน้าเข้าสู่ระบบ
│   ├── app.js                # Logic ควบคุมหน้าเว็บ & WebSocket
│   ├── placeholder_siamchai.png
│   └── placeholder_true.png
├── data/                     # เก็บข้อมูลการตั้งค่า (config.json)
├── results/                  # โฟลเดอร์เก็บผลลัพธ์ Excel
├── config.example.json       # ตัวอย่างไฟล์ตั้งค่า
├── requirements.txt          # รายการ Library ที่ต้องติดตั้ง
├── run.py                    # สคริปต์เริ่มเซิร์ฟเวอร์
├── start.bat                 # ดับเบิลคลิกเริ่มโปรแกรมบน Windows
├── .gitignore                # ป้องกันการอัปโหลดรหัสผ่านขึ้น GitHub
└── README.md                 # คู่มือการใช้งาน
```

---

## 🚀 วิธีติดตั้งและเริ่มใช้งาน (Quick Start)

### 1. ติดตั้ง Library ที่จำเป็น
เปิด PowerShell หรือ Command Prompt ในโฟลเดอร์โปรเจกต์ แล้วรันคำสั่ง:
```bash
pip install -r requirements.txt
```

### 2. เริ่มต้นโปรแกรม
สามารถเลือกวิธีใดวิธีหนึ่ง:
* **วิธีที่ 1:** ดับเบิลคลิกไฟล์ `start.bat`
* **วิธีที่ 2:** พิมพ์คำสั่ง:
  ```bash
  python run.py
  ```

ระบบจะเปิดหน้าต่างเบราว์เซอร์ [http://localhost:8000](http://localhost:8000) ให้อัตโนมัติ

### 3. ข้อมูลเข้าสู่ระบบเริ่มต้น
* **ชื่อผู้ใช้งาน (Username):** `admin`
* **รหัสผ่าน (Password):** `password123`

*(สามารถกดไอคอนฟันเฟือง ⚙️ ด้านบนขวาเพื่อเปลี่ยนรหัสผ่าน และกรอก Username/Password ของสยามชัยและทรูได้ทันที)*

---

## 🐙 วิธีนำโปรเจกต์ขึ้น GitHub (Push to GitHub)

ทำตามขั้นตอนด้านล่างนี้ได้เลยครับ:

### ขั้นตอนที่ 1: ตรวจสอบและสร้าง Git Repository ภายในเครื่อง
เปิด PowerShell ในโฟลเดอร์ `siamchai_true_hub` แล้วรัน:
```bash
# 1. กำหนดค่าเริ่มต้น Git
git init

# 2. เพิ่มไฟล์ทั้งหมดเข้าสู่ Staging (ไฟล์รหัสผ่าน config.json จะถูกข้ามอัตโนมัติตาม .gitignore)
git add .

# 3. บันทึก Commit แรก
git commit -m "Initial commit: Siamchai and TrueCorp Unified Extractor v2.0"

# 4. ตั้งชื่อ Branch หลักเป็น main
git branch -M main
```

### ขั้นตอนที่ 2: เชื่อมต่อไปยัง GitHub Repository ของคุณ
1. ไปที่เว็บไซต์ [GitHub.com](https://github.com) แล้วสร้าง Repository ใหม่ (New Repository) เช่น ตั้งชื่อว่า `siamchai-true-extractor`
2. คัดลอก URL ของ Repository มา แล้วรันคำสั่ง:
```bash
git remote add origin https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git
git push -u origin main
```

---

## 🔒 ความปลอดภัย (Security Note)
* ไฟล์ `.gitignore` ได้รับการตั้งค่าไว้ล่วงหน้าแล้ว เพื่อ**ไม่ให้อัปโหลด**ไฟล์ `config.json` (ที่มีรหัสผ่านจริง) และไฟล์ผลลัพธ์ `results/*.xlsx` ขึ้น GitHub จึงมั่นใจได้ในความปลอดภัยของบัญชี
