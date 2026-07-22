# Telegram Slip Verification Bot
# Improvement Plan v1.1 Specification

## Project Context

ระบบปัจจุบัน:
- Telegram Bot (aiogram v3)
- Supabase Database
- QR Decoder
- Gemini Vision OCR
- Risk Engine
- SlipOK API
- Smart Routing
- Duplicate Detection
- Dynamic Configuration

## IMPORTANT

ห้าม Rewrite Project
ห้ามเปลี่ยน Architecture หลัก
แก้ไขจาก Codebase ปัจจุบันเท่านั้น

เป้าหมาย:
- เพิ่ม Audit Log
- เพิ่ม Debug ย้อนหลัง
- เพิ่ม Duplicate Protection
- เพิ่ม Reliability
- เพิ่ม Error Handling

---

# Phase 1: Slip ID System

สร้าง ID กลางสำหรับสลิปแต่ละรายการ

Example:
SLIP-20260713-A8F92D

ใช้เชื่อม:
- QR Result
- OCR Result
- SlipOK Result
- Risk Result
- Database Log

---

# Phase 2: Telegram File ID

ไม่เก็บรูปบน R2 หรือ Storage

เก็บ Telegram file_id แทน

Database:
telegram_file_id text

---

# Phase 3: Image Hash

เพิ่ม image_hash

ใช้ SHA256 image bytes

Optional:
perceptual hash

---

# Phase 4: Audit Database

เพิ่ม slip_logs:

- slip_id
- telegram_user_id
- telegram_username
- chat_id
- telegram_file_id
- image_hash
- reference
- amount
- qr_result
- ocr_result
- slipok_result
- risk_result
- risk_score
- status
- failure_reason
- created_at

---

# Phase 5: Verification Audit Result

เก็บเหตุผล ไม่เก็บแค่ PASS/FAIL

ตัวอย่าง:

{
 status:"PASS",
 risk_score:5,
 checks:{
   qr_found:true,
   reference_match:true,
   amount_match:true,
   receiver_match:true,
   duplicate:false
 },
 provider_used:"LOCAL"
}

---

# Phase 6: AI Confidence

Gemini เพิ่ม:
- amount_confidence
- receiver_confidence
- reference_confidence

ถ้าความมั่นใจต่ำ:
ส่ง SlipOK ตรวจสอบ

---

# Phase 7: Error Handling

Gemini:
- Timeout
- API Error
- Invalid JSON
- Rate Limit

ห้าม PASS ถ้าตรวจไม่ได้

SlipOK:
- Retry
- Timeout
- API unavailable

---

# Phase 8: Admin Debug

เพิ่ม:

/slipinfo <slip_id>

แสดง:
- QR Result
- OCR Result
- SlipOK
- Risk Score
- Final Result

---

# Phase 9: Rate Limit

ป้องกัน Spam

ตัวอย่าง:
20 images/minute/user

---

# Phase 10: Testing

ทดสอบ:
- Normal Slip
- Duplicate Slip
- Edited Amount
- Wrong Receiver
- Broken QR

---

# Final Architecture

Telegram
|
Receive Image
|
Generate Slip ID
|
Save Telegram File ID + Hash
|
QR Decoder
|
Gemini OCR
|
Risk Engine
|
Smart Routing
|
(Optional SlipOK)
|
Verification Result
|
Supabase Audit Log
|
Telegram Response

---

# Priority

MUST:
1. Slip ID
2. Telegram File ID
3. Image Hash
4. Audit Result JSON
5. Error Handling

SHOULD:
6. AI Confidence
7. /slipinfo
8. Rate Limit

NOT REQUIRED:
- Dashboard
- R2 Storage
- Frontend
- Microservice
- Full Bank Parser
- AI Fraud Model

---

# Final Instruction

แก้เฉพาะส่วนที่จำเป็น

รักษา Logic เดิม:
- QR First
- Smart Routing
- SlipOK fallback
- Supabase Config

หลังแก้ไขส่ง:
1. Modified files
2. SQL Migration
3. Environment variables
4. Testing steps
5. Telegram output examples
