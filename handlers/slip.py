import io
import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database.supabase_db import (
    check_duplicate, log_transaction, is_group_allowed, get_allowed_groups,
    is_maintenance_mode, get_amount_limits,
    get_slipok_config, get_merchant_names, get_allowed_accounts,
    get_slipok_credentials, update_slipok_credential_status,
    log_slip_log, check_duplicate_image_hash, check_admin_permission,
    count_sender_today, get_slip_log, get_group_config
)
from services.qr_decoder import decode_qr_from_bytes
from services.vision_ai import extract_slip_details
from services.risk_engine import assess_slip_risk, match_merchant_name
from services.bank_codes import get_bank_name
from services.slipok import verify_slip_via_slipok

logger = logging.getLogger("SlipBot.Handlers.Slip")
router = Router()

import time
import hashlib
import datetime
import secrets

def format_to_be_datetime(dt_str: str | None) -> str:
    """
    Formats an input date-time string into Buddhist Era (BE) format YYYY-MM-DD HH:MM:SS
    (e.g., 2026-07-15 14:46:00 -> 2569-07-15 14:46:00).
    If empty, returns the current Thai local date-time in BE.
    """
    tz_th = datetime.timezone(datetime.timedelta(hours=7))
    now_th = datetime.datetime.now(tz_th)
    
    if not dt_str or str(dt_str).strip() in ("", "null", "None", "ไม่ระบุ", "ไม่ระบุวันเวลา"):
        # Format current time to BE YYYY-MM-DD HH:MM:SS
        be_year = now_th.year + 543
        return f"{be_year}-{now_th.strftime('%m-%d %H:%M:%S')}"
        
    cleaned_dt = str(dt_str).strip()
    parsed_date = None

    # Try ISO 8601
    try:
        parsed_date = datetime.datetime.fromisoformat(cleaned_dt.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass

    if not parsed_date:
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ]
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.datetime.strptime(cleaned_dt[:len(fmt)], fmt)
                break
            except (ValueError, TypeError):
                continue

    if not parsed_date:
        # Fallback to returning string but trying to convert year if it starts with 20xx
        if len(cleaned_dt) >= 4 and cleaned_dt[:2] == "20" and cleaned_dt[2:4].isdigit():
            try:
                year_ad = int(cleaned_dt[:4])
                year_be = year_ad + 543
                return f"{year_be}{cleaned_dt[4:]}"
            except ValueError:
                pass
        return cleaned_dt

    # Ensure timezone aware
    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=tz_th)
    else:
        parsed_date = parsed_date.astimezone(tz_th)

    be_year = parsed_date.year + 543
    return f"{be_year}-{parsed_date.strftime('%m-%d %H:%M:%S')}"


import time
import hashlib
import datetime
import secrets

# Rate limiter cache: {user_id: [timestamps]}
_user_upload_timestamps = {}

def check_rate_limit(user_id: int, limit: int = 20, period: int = 60) -> bool:
    """Returns True if within limit, False if rate limited."""
    now = time.time()
    if user_id not in _user_upload_timestamps:
        _user_upload_timestamps[user_id] = [now]
        return True
    
    # Filter out older timestamps
    timestamps = [t for t in _user_upload_timestamps[user_id] if now - t < period]
    _user_upload_timestamps[user_id] = timestamps
    
    if len(timestamps) >= limit:
        return False
    
    _user_upload_timestamps[user_id].append(now)
    return True

def mask_name(name: str) -> str:
    """Masks middle characters of a name for privacy (e.g., 'Somchai S.' -> 'S***hai S.')"""
    if not name:
        return "ไม่ระบุชื่อ"
    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) > 2:
            masked_parts.append(part[0] + "***" + part[-1])
        else:
            masked_parts.append(part)
    return " ".join(masked_parts)


@router.message(Command("stats"))
async def stats_handler(message: types.Message):
    """Admin command to show bot statistics."""
    # Check if the user has stats permission
    has_perm = await check_admin_permission(message.from_user.id, "stats")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    from database.supabase_db import _supabase_client
    if not _supabase_client:
        await message.reply("❌ ระบบฐานข้อมูลไม่พร้อมใช้งาน")
        return

    try:
        # Run DB query synchronously in executor
        import asyncio
        def query_stats():
            response = _supabase_client.table("transactions").select("amount, created_at, sender_name, trans_ref").execute()
            return response.data
            
        data = await asyncio.to_thread(query_stats)
        
        from datetime import datetime, timezone, timedelta
        tz_th = timezone(timedelta(hours=7))
        now_th = datetime.now(tz_th)
        today_str = now_th.strftime("%Y-%m-%d")
        
        total_slips = len(data)
        total_amount = sum(float(row.get("amount") or 0) for row in data)
        
        today_slips = 0
        today_amount = 0.0
        max_amount = 0.0
        max_ref = "ไม่มี"
        senders = set()
        
        for row in data:
            amt = float(row.get("amount") or 0)
            created_str = row.get("created_at")
            sender = row.get("sender_name")
            
            # Count unique senders
            if sender:
                senders.add(sender)
                
            # Find maximum amount
            if amt > max_amount:
                max_amount = amt
                max_ref = row.get("trans_ref") or "ไม่ระบุ"
                
            # Check if transaction is from today
            if created_str:
                try:
                    dt = datetime.fromisoformat(created_str.replace("Z", "+00:00")).astimezone(tz_th)
                    if dt.strftime("%Y-%m-%d") == today_str:
                        today_slips += 1
                        today_amount += amt
                except Exception as parse_err:
                    logger.error(f"Error parsing created_at timestamp: {parse_err}")
                    
        average_amount = total_amount / total_slips if total_slips > 0 else 0.0
        unique_senders = len(senders)
        
        # Get active whitelisted groups count
        groups_list = await get_allowed_groups()
        active_groups = len(groups_list)
        
        stats_text = (
            "📊 **แดชบอร์ดสถิติระบบตรวจสอบสลิป:**\n\n"
            "🌐 **สถิติสะสมทั้งหมด (Overall Stats):**\n"
            f"  • จำนวนสลิปที่ตรวจสอบผ่าน: `{total_slips:,}` รายการ\n"
            f"  • ยอดโอนสะสมรวม: `{total_amount:,.2f} THB`\n\n"
            "📅 **สถิติวันนี้ (Today's Stats):**\n"
            f"  • จำนวนสลิปวันนี้: `{today_slips:,}` รายการ\n"
            f"  • ยอดเงินรวมวันนี้: `{today_amount:,.2f} THB`\n\n"
            "📈 **ข้อมูลวิเคราะห์เชิงลึก (Insights):**\n"
            f"  • ยอดเงินเฉลี่ยต่อรายการ: `{average_amount:,.2f} THB`\n"
            f"  • ยอดเงินโอนสูงสุด: `{max_amount:,.2f} THB` (รหัส: `{max_ref}`)\n"
            f"  • จำนวนลูกค้าโอนไม่ซ้ำชื่อ: `{unique_senders:,}` ราย\n\n"
            "👥 **ข้อมูลกลุ่มแชทที่ได้รับอนุญาต:**\n"
            f"  • จำนวนกลุ่มที่อนุญาตขณะนี้: `{active_groups:,}` กลุ่ม\n\n"
            "💡 ข้อมูลประมวลผลดึงมาจาก Supabase Database"
        )
        await message.reply(stats_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error executing stats command: {e}", exc_info=True)
        await message.reply("❌ เกิดข้อผิดพลาดในการดึงสถิติจากฐานข้อมูล")


@router.message(lambda message: message.photo is not None)
async def process_slip_image(message: types.Message, bot: Bot):
    """Processes any uploaded photo as a bank transfer slip."""
    start_time = time.time()
    
    # Generate Slip ID: SLIP-YYYYMMDD-HEX6
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    rand_hex = secrets.token_hex(3).upper()
    slip_id = f"SLIP-{date_str}-{rand_hex}"

    processing_msg = None


    # Helper function to send or edit messages with support for Inline Keyboard reply_markup
    async def reply_message(text: str, force_new=False, parse_mode="Markdown", reply_markup=None):
        nonlocal processing_msg
        if processing_msg and not force_new:
            try:
                return await processing_msg.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            except Exception as edit_err:
                logger.warning(f"Failed to edit message, sending new: {edit_err}")
                sent_msg = await message.reply(text, parse_mode=parse_mode, reply_markup=reply_markup)
                processing_msg = sent_msg
                return sent_msg
        else:
            sent_msg = await message.reply(text, parse_mode=parse_mode, reply_markup=reply_markup)
            if not processing_msg:
                processing_msg = sent_msg
            return sent_msg   # Rate Limiting Check (20 images/minute/user)
    if not check_rate_limit(message.from_user.id, limit=20, period=60):
        await reply_message(
            "🚨 **กรุณาอย่าส่งสแปมภาพสลิป!**\nจำกัดไม่เกิน 20 รูปต่อนาที กรุณารอ 1 นาทีแล้วลองใหม่อีกครั้ง",
            force_new=True
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        await log_slip_log({
            "slip_id": slip_id,
            "telegram_user_id": message.from_user.id,
            "telegram_username": message.from_user.username,
            "chat_id": message.chat.id,
            "telegram_file_id": None,
            "image_hash": "RATE_LIMIT_EXCEEDED",
            "reference": None,
            "amount": None,
            "qr_result": None,
            "ocr_result": None,
            "slipok_result": None,
            "risk_result": {"status": "ERROR", "error_code": "RATE_LIMIT"},
            "risk_score": 100,
            "status": "ERROR",
            "failure_reason": "Rate limit exceeded (spam protection)",
            "error_code": "RATE_LIMIT",
            "processing_time_ms": elapsed_ms
        })
        return

    # Check admin role once for maintenance and private chat lockdown bypass
    is_admin = await check_admin_permission(message.from_user.id)

    # Check maintenance mode first
    is_maint = await is_maintenance_mode()
    if is_maint and not is_admin:
        await message.reply(
            "🛠️ **ระบบตรวจสอบสลิปอยู่ในระหว่างการปิดปรับปรุงชั่วคราว**\nขออภัยในความไม่สะดวก กรุณาส่งสลิปเข้ามาใหม่อีกครั้งในภายหลัง",
            parse_mode="Markdown"
        )
        return

    is_group = message.chat.type in ["group", "supergroup"]
    group_config = None
    
    # Check access permission
    if is_group:
        group_config = await get_group_config(message.chat.id)
        if not group_config:
            await message.reply("⚠️ หากต้องการใช้งานระบบ Slip Verify ติดต่อ Florentino")
            try:
                await bot.leave_chat(message.chat.id)
            except Exception as leave_err:
                logger.error(f"Failed to leave chat {message.chat.id}: {leave_err}")
            return
    else:
        # Private chat: Lockdown for non-admins
        if not is_admin:
            await message.reply("⚠️ หากต้องการใช้งานระบบ Slip Verify ติดต่อ Florentino")
            return

    # Initialize logging variables
    photo = message.photo[-1]
    file_id = photo.file_id
    image_hash = "UNKNOWN"
    qr_data = None
    qr_ref = None
    ocr_data = None
    verify_res = None
    risk_score = 0
    provider_used = "NONE"
    audit_checks = {
        "qr_found": False,
        "reference_match": False,
        "amount_match": False,
        "receiver_match": False,
        "duplicate": False
    }
    
    async def save_audit_log(status_val, reason_val=None, code_val=None):
        elapsed_ms = int((time.time() - start_time) * 1000)
        # Safely compute reference and amount
        ref_val = qr_ref
        if not ref_val and ocr_data and not ocr_data.get("error"):
            ref_val = ocr_data.get("trans_ref")
        if not ref_val and verify_res and verify_res.get("success"):
            ref_val = verify_res.get("trans_ref")
            
        amt_val = None
        if ocr_data and not ocr_data.get("error"):
            amt_val = ocr_data.get("amount")
        if amt_val is None and verify_res and verify_res.get("success"):
            amt_val = verify_res.get("amount")
            
        log_data = {
            "slip_id": slip_id,
            "telegram_user_id": message.from_user.id,
            "telegram_username": message.from_user.username,
            "chat_id": message.chat.id,
            "telegram_file_id": file_id,
            "image_hash": image_hash,
            "reference": ref_val,
            "amount": amt_val,
            "qr_result": qr_data,
            "ocr_result": ocr_data,
            "slipok_result": verify_res,
            "risk_result": {
                "status": status_val,
                "risk_score": risk_score,
                "checks": audit_checks,
                "provider_used": provider_used
            },
            "risk_score": risk_score,
            "status": status_val,
            "failure_reason": reason_val,
            "error_code": code_val,
            "processing_time_ms": elapsed_ms
        }
        await log_slip_log(log_data)

    try:
        # 1. Fetch configurations from database with Group overrides
        slipok_config = await get_slipok_config()
        slipok_credentials = await get_slipok_credentials()
        
        # Override settings if group_config exists
        merchant_names = []
        allowed_accounts = []
        slipok_mode = slipok_config.get("mode", "off")
        
        if group_config:
            # 1.1 Merchant Name Override
            g_merchant = group_config.get("merchant_name")
            if g_merchant:
                sep = "|" if "|" in g_merchant else ","
                merchant_names = [n.strip() for n in g_merchant.split(sep) if n.strip()]
            else:
                merchant_names = await get_merchant_names()
                
            # 1.2 Allowed Accounts Override
            g_accounts = group_config.get("allowed_accounts")
            if g_accounts:
                sep = "|" if "|" in g_accounts else ","
                allowed_accounts = [a.strip() for a in g_accounts.split(sep) if a.strip()]
            else:
                allowed_accounts = await get_allowed_accounts()
                
            # 1.3 SlipOK Mode Override
            g_mode = group_config.get("slipok_mode")
            if g_mode and g_mode in ["smart", "always", "off"]:
                slipok_mode = g_mode
        else:
            merchant_names = await get_merchant_names()
            allowed_accounts = await get_allowed_accounts()
        
        # 2. Download photo from Telegram to memory
        photo_file = io.BytesIO()
        await bot.download(photo, destination=photo_file)
        image_bytes = photo_file.getvalue()
        
        # Calculate image_hash (SHA256)
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # Check duplicate image hash (Phase 3 Duplicate Protection)
        is_dup_hash = await check_duplicate_image_hash(image_hash)
        if is_dup_hash:
            dup_text = (
                "⚠️ **ตรวจพบการส่งรูปภาพสลิปซ้ำซ้อน!**\n\n"
                "ภาพสลิปใบนี้เคยได้รับการอนุมัติในระบบไปเรียบร้อยแล้ว ไม่สามารถส่งซ้ำได้เพื่อความปลอดภัย"
            )
            await reply_message(dup_text, force_new=True)
            audit_checks["duplicate"] = True
            risk_score = 100
            await save_audit_log("FAIL", "Duplicate image content (same image hash)", "DUPLICATE_HASH")
            return
        
        # 3. Local QR Code Scanning
        qr_data = decode_qr_from_bytes(image_bytes)
        qr_ref = qr_data.get("trans_ref") if qr_data else None
        
        if qr_data:
            audit_checks["qr_found"] = True
        
        # Determine if we should send a processing message
        if qr_ref:
            processing_msg = await message.reply("⏳ **กำลังดาวน์โหลดและประมวลผลสลิปโอนเงินของคุณ...**\nกรุณารอสักครู่")
            
            # Check duplicate
            is_dup = await check_duplicate(qr_ref)
            if is_dup:
                await reply_message(
                    f"⚠️ **ตรวจพบการใช้สลิปซ้ำ!**\n\n"
                    f"❌ รหัสอ้างอิง: `{qr_ref}`\n"
                    "สลิปใบนี้เคยได้รับการตรวจสอบและอนุมัติในระบบไปแล้ว ไม่สามารถใช้งานซ้ำได้เพื่อป้องกันการทุจริต"
                )
                audit_checks["duplicate"] = True
                risk_score = 100
                await save_audit_log("FAIL", f"Duplicate transaction reference: {qr_ref}", "DUPLICATE")
                return
        else:
            if is_group:
                if not Config.ENABLE_OCR_FALLBACK:
                    return
            else:
                processing_msg = await message.reply("⏳ **กำลังดาวน์โหลดและประมวลผลรูปภาพของคุณ...**\nกรุณารอสักครู่")

        # 4. Fallback or Vision OCR parsing
        ocr_data = None
        is_low_confidence = False
        
        if qr_ref or Config.ENABLE_OCR_FALLBACK:
            ocr_data = await extract_slip_details(image_bytes)
            
            # Check for Vision AI errors
            if ocr_data and "error" in ocr_data:
                logger.warning(f"Vision OCR failed: {ocr_data['error']} (code: {ocr_data.get('error_code')})")
            elif ocr_data:
                # Check AI confidence (Phase 6)
                amount_conf = ocr_data.get("amount_confidence", 1.0)
                receiver_conf = ocr_data.get("receiver_confidence", 1.0)
                ref_conf = ocr_data.get("reference_confidence", 1.0)
                
                threshold = getattr(Config, "AI_CONFIDENCE_THRESHOLD", 0.85)
                if amount_conf < threshold or receiver_conf < threshold or ref_conf < threshold:
                    is_low_confidence = True
                    logger.info(f"Low AI confidence detected: amount={amount_conf}, receiver={receiver_conf}, ref={ref_conf} (Threshold: {threshold}). Forcing SlipOK routing.")
            
            # In group chats, if no QR, verify if it's actually a slip before replying
            if is_group and not qr_ref:
                if not ocr_data or "error" in ocr_data:
                    return
                    
                text_to_check = f"{ocr_data.get('sender_name') or ''} {ocr_data.get('receiver_name') or ''} {ocr_data.get('trans_ref') or ''}"
                keywords = ["โอน", "สำเร็จ", "บาท", "thb", "transfer", "successful", "ref", "อ้างอิง"]
                is_slip = any(kw in text_to_check.lower() for kw in keywords) or (ocr_data.get("amount") is not None and ocr_data.get("amount") > 0)
                
                if not is_slip:
                    return
                    
                processing_msg = await message.reply("⏳ **กำลังตรวจสอบประมวลผลสลิปโอนเงิน...**")

            # Check duplicate against OCR trans_ref
            if ocr_data and not ocr_data.get("error") and ocr_data.get("trans_ref") and not qr_ref:
                ocr_ref = ocr_data["trans_ref"]
                is_dup = await check_duplicate(ocr_ref)
                if is_dup:
                    dup_text = (
                        f"⚠️ **ตรวจพบการใช้สลิปซ้ำ!**\n\n"
                        f"❌ รหัสอ้างอิง: `{ocr_ref}`\n"
                        "สลิปใบนี้เคยได้รับการอนุมัติในระบบไปแล้ว ไม่สามารถใช้งานซ้ำได้"
                    )
                    await reply_message(dup_text)
                    audit_checks["duplicate"] = True
                    risk_score = 100
                    await save_audit_log("FAIL", f"Duplicate transaction reference: {ocr_ref}", "DUPLICATE")
                    return

        # 5. Routing to SlipOK (Smart/Always/Off)
        use_slipok = False
        
        # Filter for active credentials in database
        active_credentials = [c for c in slipok_credentials if c.get("status") == "active"]
        
        # Assess risk for smart routing decisions
        ocr_clean = ocr_data if (ocr_data and "error" not in ocr_data) else None
        risk_eval = assess_slip_risk(qr_data, ocr_clean, merchant_names, allowed_accounts)
        risk_score = risk_eval.get("risk_score", 0)
        is_suspicious = not risk_eval.get("is_safe", True)
        
        if slipok_mode in ["smart", "always"] and active_credentials:
            if slipok_mode == "always":
                use_slipok = True
            elif slipok_mode == "smart":
                # Smart routing conditions:
                # 1. No QR code detected locally
                no_qr = qr_ref is None
                # 2. Risk engine flags warnings
                # 3. High value transfer
                is_high_value = False
                if ocr_clean and ocr_clean.get("amount") is not None:
                    is_high_value = ocr_clean["amount"] >= slipok_config.get("min_amount", 500.0)
                
                if no_qr or is_suspicious or is_high_value or is_low_confidence or (ocr_data and "error" in ocr_data):
                    use_slipok = True
                    logger.info(f"Smart Mode: Routing slip to SlipOK. (no_qr={no_qr}, is_suspicious={is_suspicious}, is_high_value={is_high_value}, is_low_confidence={is_low_confidence}, ocr_failed={bool(ocr_data and 'error' in ocr_data)})")

        slipok_failed_or_unavailable = False

        if use_slipok:
            logger.info("Calling SlipOK verification API with rotation support...")
            provider_used = "SLIPOK"
            
            # Loop through active credentials
            for cred in active_credentials:
                current_key = cred.get("api_key")
                current_branch = cred.get("branch_id")
                
                logger.info(f"Attempting SlipOK verification using key: {current_key[:10]}... (Branch: {current_branch})")
                verify_res = await verify_slip_via_slipok(
                    api_key=current_key,
                    branch_id=current_branch,
                    qr_payload=qr_data.get("raw_payload") if qr_data else None,
                    image_bytes=image_bytes
                )
                
                if verify_res is not None:
                    if verify_res.get("success"):
                        # Successful verification from bank! Break and process response.
                        break
                    else:
                        err_code = verify_res.get("error_code")
                        if err_code in [1021, 1022]:
                            # Quota exhausted (1022) or invalid API key (1021)
                            status_label = "exhausted" if err_code == 1022 else "invalid"
                            await update_slipok_credential_status(current_key, status_label)
                            
                            # Censor key for Telegram messages
                            censored_key = f"{current_key[:6]}...{current_key[-4:]}" if len(current_key) > 10 else current_key
                            alert_msg = (
                                f"⚠️ **แจ้งเตือน SlipOK API Key ขัดข้อง!**\n\n"
                                f"• Key: `{censored_key}` (Branch: `{current_branch}`)\n"
                                f"• สาเหตุ: `{'โควต้าหมด (Out of Quota)' if err_code == 1022 else 'คีย์ไม่ถูกต้อง/ปิดใช้งาน'}`\n"
                                f"• ระบบกำลังสลับใช้ API Key ลำดับถัดไปโดยอัตโนมัติ..."
                            )
                            for admin_id in Config.ADMIN_USER_IDS:
                                try:
                                    await bot.send_message(chat_id=admin_id, text=alert_msg, parse_mode="Markdown")
                                except Exception as e:
                                    logger.error(f"Failed to alert admin {admin_id}: {e}")
                            
                            # Try the next key
                            continue
                        else:
                            # Genuine verification failure (invalid slip, duplicate slip in SlipOK, wrong amount, etc.)
                            # Do NOT rotate key, this is a real user error. Break loop.
                            break
                else:
                    # Network / HTTP error. Try the next key.
                    continue

            if verify_res is not None:
                # If verify_res is not None, we process SlipOK response
                if verify_res.get("success"):
                    # Check receiver name and account safety after SlipOK success
                    if merchant_names:
                        match_found = False
                        for m_name in merchant_names:
                            if match_merchant_name(m_name, verify_res["receiver_name"]):
                                match_found = True
                                break
                        if not match_found:
                            error_text = (
                                f"🔴 **สลิปปลอม! ชื่อผู้รับไม่ตรง**\n\n"
                                f"ชื่อผู้รับบนสลิป: `{verify_res['receiver_name']}`\n"
                                f"ไม่ตรงกับชื่อที่ได้รับอนุญาต กรุณาตรวจสอบสลิปอีกครั้ง"
                            )
                            await reply_message(error_text)
                            risk_score = 100
                            await save_audit_log("FAIL", f"Receiver name mismatch: {verify_res['receiver_name']}", "RECEIVER_MISMATCH")
                            return
                        else:
                            audit_checks["receiver_match"] = True

                    if allowed_accounts and verify_res.get("receiver_account"):
                        match_found = False
                        for allowed_acc in allowed_accounts:
                            from services.risk_engine import match_account_number
                            if match_account_number(allowed_acc, verify_res["receiver_account"]):
                                match_found = True
                                break
                        if not match_found:
                            error_text = (
                                f"🔴 **สลิปปลอม! เลขที่บัญชีผู้รับไม่ตรง**\n\n"
                                f"เลขที่บัญชีผู้รับบนสลิป: `{verify_res['receiver_account']}`\n"
                                f"ไม่ตรงกับบัญชีที่ได้รับอนุญาต กรุณาตรวจสอบสลิปอีกครั้ง"
                            )
                            await reply_message(error_text)
                            risk_score = 100
                            await save_audit_log("FAIL", f"Receiver account mismatch: {verify_res['receiver_account']}", "ACCOUNT_MISMATCH")
                            return

                    # Success from bank! Check duplicate in database using SlipOK transRef
                    s_ref = verify_res["trans_ref"]
                    is_dup = await check_duplicate(s_ref)
                    if is_dup:
                        dup_text = (
                            f"⚠️ **ตรวจพบการใช้สลิปซ้ำ!**\n\n"
                            f"❌ รหัสอ้างอิง: `{s_ref}`\n"
                            "สลิปใบนี้เคยได้รับการอนุมัติในระบบไปแล้ว ไม่สามารถใช้งานซ้ำได้"
                        )
                        await reply_message(dup_text)
                        audit_checks["duplicate"] = True
                        risk_score = 100
                        await save_audit_log("FAIL", f"Duplicate reference check: {s_ref}", "DUPLICATE")
                        return

                    # Extract sender account from SlipOK raw response if possible
                    s_acc = None
                    if verify_res.get("raw") and isinstance(verify_res["raw"], dict):
                        s_acc = verify_res["raw"].get("data", {}).get("sender", {}).get("account", {}).get("value")

                    # Log to database
                    db_logged = await log_transaction(
                        trans_ref=s_ref,
                        sender_name=verify_res["sender_name"],
                        receiver_name=verify_res["receiver_name"],
                        amount=verify_res["amount"],
                        trans_date=verify_res["trans_date"],
                        raw_ocr={**(verify_res.get("raw") or {}), "sender_account": s_acc}
                    )
                    db_status = "⚙️💾✅" if db_logged else "⚙️💾❌"
                    
                    # Fetch sender stats for today
                    sender_count, _ = await count_sender_today(verify_res["sender_name"], s_acc)
                    
                    # Format BE date-time
                    be_date_str = format_to_be_datetime(verify_res["trans_date"])
                    
                    # Formatting only SlipOK data
                    s_bank = get_bank_name(verify_res["sending_bank"])
                    s_sender = mask_name(verify_res["sender_name"])
                    
                    # Compact message format
                    success_text = (
                        f"🟢 **สลิปจริง! (ยืนยันตรงกับระบบธนาคาร)** {db_status}\n\n"
                        f"👤 **ผู้โอน**: `{s_sender}`\n"
                        f"🏢 **ผู้รับ**: `{verify_res['receiver_name']}`\n"
                        f"💵 **ยอดเงิน**: `{verify_res['amount']:,.2f} THB`\n"
                        f"📅 **วันเวลา**: `{be_date_str}`\n"
                        f"🏦 **ธนาคาร**: `{s_bank}`\n"
                        f"📊 **วันนี้**: `{sender_count} ครั้ง` ⚠️\n\n"
                        f"⚠️ *ผลนี้ใช้สำหรับตรวจสอบความถูกต้องของสลิปเท่านั้น*\n"
                        f"*กรุณาให้ผู้ดูแลระบบยืนยันการรับเงินอีกครั้งก่อนดำเนินการ*"
                    )
                    
                    # Add inline button for details
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📋 ดูรายละเอียดทั้งหมด", callback_data=f"detail:{slip_id}")]
                    ])
                    
                    await reply_message(success_text, reply_markup=keyboard)
                    logger.info(f"Verified slip via SlipOK successfully: {s_ref} | Amount: {verify_res['amount']}")
                    
                    # Fill audit checks
                    audit_checks["reference_match"] = True
                    audit_checks["amount_match"] = True
                    await save_audit_log("PASS")
                    return
                else:
                    err_code = verify_res.get("error_code")
                    if err_code in [1010, 1021, 1022]:
                        logger.warning(f"SlipOK API issue (code {err_code}). Falling back to local OCR verification.")
                        slipok_failed_or_unavailable = True
                    else:
                        error_text = (
                            f"🔴 **สลิปไม่ผ่านการตรวจสอบจากธนาคาร!**\n\n"
                            f"**สาเหตุ:** {verify_res['message']}\n\n"
                            f"กรุณาส่งรูปภาพสลิปที่ถูกต้อง หรือติดต่อเจ้าหน้าที่หากมีข้อสงสัย"
                        )
                        await reply_message(error_text)
                        risk_score = 100
                        await save_audit_log("FAIL", f"SlipOK genuine failure: {verify_res['message']}", str(err_code) if err_code else "SLIPOK_FAILURE")
                        return
            else:
                logger.warning("SlipOK API returned empty response or HTTP error. Falling back to local verification.")
                slipok_failed_or_unavailable = True
        else:
            slipok_failed_or_unavailable = True

        # Enforce SlipOK fallback check
        if use_slipok and slipok_failed_or_unavailable:
            if (ocr_data and "error" in ocr_data) or is_low_confidence or is_suspicious:
                failure_reason = "SlipOK API is unavailable and local slip details are suspicious or unclear."
                error_code = "MANUAL_REVIEW_REQUIRED"
                err_text = (
                    "🚨 **ตรวจสอบสลิปไม่สำเร็จ (ต้องได้รับการตรวจสอบโดยเจ้าหน้าที่)**\n\n"
                    "เนื่องจากระบบยืนยันสลิปผ่านธนาคารอัตโนมัติไม่พร้อมใช้งานในขณะนี้ และสลิปโอนเงินไม่ชัดเจน/น่าสงสัย "
                    "กรุณารอเจ้าหน้าที่ตรวจสอบยอดเงินโอนเข้าโดยตรงเพื่อความถูกต้อง"
                )
                await reply_message(err_text)
                await save_audit_log("FAIL", failure_reason, error_code)
                return

        # 6. Fallback to Local QR + Vision AI OCR
        provider_used = "LOCAL"
        
        if ocr_data and "error" in ocr_data:
            err_text = (
                "🚨 **ตรวจสอบสลิปไม่สำเร็จ (ต้องได้รับการตรวจสอบโดยเจ้าหน้าที่)**\n\n"
                "ระบบไม่สามารถอ่านข้อความบนภาพสลิปได้ชั่วคราว กรุณารอเจ้าหน้าที่ตรวจสอบ หรือลองส่งสลิปใหม่อีกครั้ง"
            )
            await reply_message(err_text)
            await save_audit_log("FAIL", f"Local OCR failed: {ocr_data['error']}", ocr_data.get("error_code", "OCR_ERROR"))
            return

        risk_result = assess_slip_risk(qr_data, ocr_clean, merchant_names, allowed_accounts)
        disclaimer = (
            "\n\n⚠️ *ผลนี้เป็นการตรวจสอบเบื้องต้นจาก QR Code และ OCR เท่านั้น ยังไม่ได้ยืนยันกับธนาคารโดยตรง*\n"
            "*กรุณาให้ผู้ดูแลระบบยืนยันการรับเงินอีกครั้งก่อนดำเนินการ*"
        )

        if not risk_result["is_safe"]:
            warnings_text = "\n".join([f"• {w}" for w in risk_result["warnings"]])
            error_text = (
                f"🔴 **สลิปน่าสงสัย / อาจเป็นสลิปปลอม!**\n\n"
                f"**ระดับความเสี่ยง**: `{risk_result['risk_score']}/100`\n"
                f"**ปัญหาที่พบ:**\n{warnings_text}\n\n"
                "กรุณาตรวจสอบสลิปอีกครั้ง หรือติดต่อเจ้าหน้าที่หากข้อมูลดังกล่าวมีความผิดพลาด"
            )
            await reply_message(error_text)
            await save_audit_log("FAIL", f"Risk engine warnings: {', '.join(risk_result['warnings'])}", "SUSPICIOUS")
            return

        # Safe slip: Log and reply using local OCR/QR
        trans_ref = qr_ref or (ocr_clean.get("trans_ref") if ocr_clean else None) or "UNKNOWN_REF"
        sender_name = ocr_clean.get("sender_name") if ocr_clean else "ไม่ระบุผู้ส่ง"
        receiver_name = ocr_clean.get("receiver_name") if ocr_clean else "ไม่ระบุผู้รับ"
        amount = ocr_clean.get("amount") if ocr_clean else 0.0
        trans_date = ocr_clean.get("trans_date") if ocr_clean else None
        
        # Extract sender account from OCR if possible
        s_acc = ocr_clean.get("sender_account") if ocr_clean else None

        db_logged = await log_transaction(
            trans_ref=trans_ref,
            sender_name=sender_name,
            receiver_name=receiver_name,
            amount=amount,
            trans_date=trans_date,
            raw_ocr={**(ocr_clean or {}), "sender_account": s_acc}
        )
        
        db_status = "⚙️💾✅" if db_logged else "⚙️💾❌"
        
        # Fetch sender stats for today
        sender_count, _ = await count_sender_today(sender_name, s_acc)
        
        # Format BE date-time
        be_date_str = format_to_be_datetime(trans_date)
        
        if qr_data:
            qr_bank = get_bank_name(qr_data.get("sending_bank"))
            qr_ref_str = qr_data.get("trans_ref")
            qr_status_text = (
                f"🔎 **ผล QR Code**: `✅ พบ QR Code — เลขอ้างอิงตรงกับข้อมูลบนสลิป`\n"
                f"🏦 **ธนาคารต้นทาง**: `{qr_bank}`\n"
                f"🔑 **รหัสธุรกรรม**: `{qr_ref_str}`"
            )
            audit_checks["reference_match"] = True
        else:
            qr_status_text = (
                f"🔎 **ผล QR Code**: `⚠️ ไม่พบ QR Code — ตรวจสอบได้จาก OCR เท่านั้น ควรระวัง`"
            )

        amount_suffix = ""
        try:
            min_limit, max_limit = await get_amount_limits()
            amount_val = float(amount)
            if amount_val < min_limit or amount_val > max_limit:
                amount_suffix = " ⚠️ เช็คในบัญชีอีกครั้ง!"
        except Exception as limit_err:
            logger.error(f"Error checking amount limits: {limit_err}")

        # Set success audit checks
        if merchant_names:
            audit_checks["receiver_match"] = True
        audit_checks["amount_match"] = True

        # Mask sender name
        s_sender = mask_name(sender_name)

        success_text = (
            f"🟡 **สลิปน่าจะเป็นของจริง (ตรวจสอบเบื้องต้น)** {db_status}\n\n"
            f"👤 **ผู้โอน**: `{s_sender}`\n"
            f"🏢 **ผู้รับ**: `{receiver_name}`\n"
            f"💵 **ยอดเงิน**: `{amount:,.2f} THB`{amount_suffix}\n"
            f"📅 **วันเวลา**: `{be_date_str}`\n"
            f"📊 **วันนี้**: `{sender_count} ครั้ง` ⚠️\n\n"
            f"{disclaimer}"
        )
        
        # Add inline button for details
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 ดูรายละเอียดทั้งหมด", callback_data=f"detail:{slip_id}")]
        ])
        
        await reply_message(success_text, reply_markup=keyboard)
        logger.info(f"Verified slip successfully (local fallback): {trans_ref} | Amount: {amount}")
        await save_audit_log("PASS")

    except Exception as e:
        logger.error(f"Error processing slip upload: {e}", exc_info=True)
        err_text = "❌ **เกิดข้อผิดพลาดภายในระบบ**\nไม่สามารถประมวลผลรูปภาพได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"
        
        if is_group and not processing_msg:
            pass
        else:
            await reply_message(err_text)
                
        risk_score = 100
        await save_audit_log("ERROR", str(e), "INTERNAL_ERROR")


@router.callback_query(lambda c: c.data.startswith("detail:"))
async def process_detail_callback(callback_query: CallbackQuery):
    slip_id = callback_query.data.split(":")[1]
    
    # Retrieve slip log from database
    slip_log = await get_slip_log(slip_id)
    if not slip_log:
        await callback_query.answer("❌ ไม่พบข้อมูลสลิปนี้ในระบบ", show_alert=True)
        return
        
    ocr_res = slip_log.get("ocr_result") or {}
    slipok_res = slip_log.get("slipok_result") or {}
    qr_res = slip_log.get("qr_result") or {}
    risk_res = slip_log.get("risk_result") or {}
    provider = risk_res.get("provider_used", "LOCAL")
    
    sender_name = ocr_res.get("sender_name") or slipok_res.get("sender_name") or "ไม่ระบุ"
    sender_acc = ocr_res.get("sender_account") or (slipok_res.get("raw", {}).get("data", {}).get("sender", {}).get("account", {}).get("value") if slipok_res else None) or "ไม่ระบุ"
    
    receiver_name = ocr_res.get("receiver_name") or slipok_res.get("receiver_name") or "ไม่ระบุ"
    receiver_acc = ocr_res.get("receiver_account") or slipok_res.get("receiver_account") or "ไม่ระบุ"
    
    amount = slip_log.get("amount") or 0.0
    trans_date = ocr_res.get("trans_date") or slipok_res.get("trans_date")
    be_date_str = format_to_be_datetime(trans_date)
    
    trans_ref = slip_log.get("reference") or "ไม่ระบุ"
    sending_bank_code = qr_res.get("sending_bank") or (slipok_res.get("sending_bank") if slipok_res else None)
    bank_name = get_bank_name(sending_bank_code)
    
    # Fetch today stats
    sender_count, matched_txs = await count_sender_today(sender_name, sender_acc if sender_acc != "ไม่ระบุ" else None)
    
    # Build detailed text message
    detail_text = (
        f"📋 **รายละเอียดข้อมูลสลิปแบบเต็ม**\n"
        f"🆔 `Slip ID: {slip_id}`\n\n"
        f"🏦 **ธนาคาร**: `{bank_name}`\n"
        f"👤 **ผู้โอน**: `{sender_name}`\n"
        f"💳 **บัญชีผู้โอน**: `{sender_acc}`\n"
        f"🏢 **ผู้รับ**: `{receiver_name}`\n"
        f"💳 **บัญชีผู้รับ**: `{receiver_acc}`\n"
        f"💵 **ยอดเงิน**: `{amount:,.2f} THB`\n"
        f"📅 **วันเวลาโอน**: `{be_date_str}`\n"
        f"🔑 **รหัสอ้างอิง**: `{trans_ref}`\n\n"
    )
    
    if provider == "SLIPOK":
        detail_text += "🔎 **ผลตรวจสอบ**: ✅ ยืนยันตรงกับธนาคารผ่าน SlipOK\n"
    else:
        qr_status = "✅ พบ QR (ตรงกัน)" if qr_res else "⚠️ ไม่พบ QR Code"
        detail_text += f"🔎 **ผล QR**: `{qr_status}`\n🔎 **ผล OCR**: `✅ อ่านข้อความสำเร็จ`\n"
        
    detail_text += f"\n📊 **ประวัติการโอนวันนี้**:\n"
    detail_text += f"└─ ทั้งหมด: `{sender_count} ครั้ง`\n"
    
    # Show last 5 transaction records for this sender today
    for i, tx in enumerate(matched_txs[:5], 1):
        tx_amount = tx.get("amount") or 0.0
        tx_time = "ไม่ระบุ"
        tx_created = tx.get("created_at")
        if tx_created:
            try:
                from datetime import datetime, timezone, timedelta
                dt = datetime.fromisoformat(tx_created.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=7)))
                tx_time = dt.strftime("%H:%M:%S")
            except Exception:
                pass
        curr_mark = " (รายการนี้)" if tx.get("trans_ref") == trans_ref else ""
        detail_text += f"   {i}️⃣ {tx_amount:,.2f} THB ({tx_time}){curr_mark}\n"
        
    if len(matched_txs) > 5:
        detail_text += f"   ... และรายการอื่นอีก {len(matched_txs) - 5} รายการ\n"
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ ย่อข้อความ", callback_data=f"summary:{slip_id}")]
    ])
    
    try:
        await callback_query.message.edit_text(detail_text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Failed to edit callback detail message: {e}")
    await callback_query.answer()


@router.callback_query(lambda c: c.data.startswith("summary:"))
async def process_summary_callback(callback_query: CallbackQuery):
    slip_id = callback_query.data.split(":")[1]
    
    slip_log = await get_slip_log(slip_id)
    if not slip_log:
        await callback_query.answer("❌ ไม่พบข้อมูลสลิปนี้ในระบบ", show_alert=True)
        return
        
    ocr_res = slip_log.get("ocr_result") or {}
    slipok_res = slip_log.get("slipok_result") or {}
    qr_res = slip_log.get("qr_result") or {}
    risk_res = slip_log.get("risk_result") or {}
    provider = risk_res.get("provider_used", "LOCAL")
    
    sender_name = ocr_res.get("sender_name") or slipok_res.get("sender_name") or "ไม่ระบุ"
    sender_acc = ocr_res.get("sender_account") or (slipok_res.get("raw", {}).get("data", {}).get("sender", {}).get("account", {}).get("value") if slipok_res else None)
    
    receiver_name = ocr_res.get("receiver_name") or slipok_res.get("receiver_name") or "ไม่ระบุ"
    amount = slip_log.get("amount") or 0.0
    trans_date = ocr_res.get("trans_date") or slipok_res.get("trans_date")
    be_date_str = format_to_be_datetime(trans_date)
    
    sending_bank_code = qr_res.get("sending_bank") or (slipok_res.get("sending_bank") if slipok_res else None)
    bank_name = get_bank_name(sending_bank_code)
    
    sender_count, _ = await count_sender_today(sender_name, sender_acc)
    
    s_sender = mask_name(sender_name)
    
    if provider == "SLIPOK":
        success_text = (
            f"🟢 **สลิปจริง! (ยืนยันตรงกับระบบธนาคาร)** ⚙️💾✅\n\n"
            f"👤 **ผู้โอน**: `{s_sender}`\n"
            f"🏢 **ผู้รับ**: `{receiver_name}`\n"
            f"💵 **ยอดเงิน**: `{amount:,.2f} THB`\n"
            f"📅 **วันเวลา**: `{be_date_str}`\n"
            f"🏦 **ธนาคาร**: `{bank_name}`\n"
            f"📊 **วันนี้**: `{sender_count} ครั้ง` ⚠️\n\n"
            f"⚠️ *ผลนี้ใช้สำหรับตรวจสอบความถูกต้องของสลิปเท่านั้น*\n"
            f"*กรุณาให้ผู้ดูแลระบบยืนยันการรับเงินอีกครั้งก่อนดำเนินการ*"
        )
    else:
        disclaimer = (
            "\n\n⚠️ *ผลนี้เป็นการตรวจสอบเบื้องต้นจาก QR Code และ OCR เท่านั้น ยังไม่ได้ยืนยันกับธนาคารโดยตรง*\n"
            "*กรุณาให้ผู้ดูแลระบบยืนยันการรับเงินอีกครั้งก่อนดำเนินการ*"
        )
        
        success_text = (
            f"🟡 **สลิปน่าจะเป็นของจริง (ตรวจสอบเบื้องต้น)** ⚙️💾✅\n\n"
            f"👤 **ผู้โอน**: `{s_sender}`\n"
            f"🏢 **ผู้รับ**: `{receiver_name}`\n"
            f"💵 **ยอดเงิน**: `{amount:,.2f} THB`\n"
            f"📅 **วันเวลา**: `{be_date_str}`\n"
            f"📊 **วันนี้**: `{sender_count} ครั้ง` ⚠️\n\n"
            f"{disclaimer}"
        )
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 ดูรายละเอียดทั้งหมด", callback_data=f"detail:{slip_id}")]
    ])
    
    try:
        await callback_query.message.edit_text(success_text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Failed to edit callback summary message: {e}")
    await callback_query.answer()

