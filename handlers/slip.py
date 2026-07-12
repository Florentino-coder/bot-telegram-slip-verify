import io
import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from config import Config
from database.supabase_db import (
    check_duplicate, log_transaction, is_group_allowed, get_allowed_groups,
    is_maintenance_mode, get_amount_limits
)
from services.qr_decoder import decode_qr_from_bytes
from services.vision_ai import extract_slip_details
from services.risk_engine import assess_slip_risk
from services.bank_codes import get_bank_name

logger = logging.getLogger("SlipBot.Handlers.Slip")
router = Router()

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
    # Check if the user is an admin
    if message.from_user.id not in Config.ADMIN_USER_IDS:
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
    # Check maintenance mode first
    is_maint = await is_maintenance_mode()
    if is_maint and message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply(
            "🛠️ **ระบบตรวจสอบสลิปอยู่ในระหว่างการปิดปรับปรุงชั่วคราว**\nขออภัยในความไม่สะดวก กรุณาส่งสลิปเข้ามาใหม่อีกครั้งในภายหลัง",
            parse_mode="Markdown"
        )
        return

    is_group = message.chat.type in ["group", "supergroup"]
    
    # Check access permission
    if is_group:
        allowed = await is_group_allowed(message.chat.id)
        if not allowed:
            await message.reply("⚠️ หากต้องการใช้งานระบบ Slip Verify ติดต่อ Florentino")
            try:
                await bot.leave_chat(message.chat.id)
            except Exception as leave_err:
                logger.error(f"Failed to leave chat {message.chat.id}: {leave_err}")
            return
    else:
        # Private chat: Lockdown for non-admins
        if message.from_user.id not in Config.ADMIN_USER_IDS:
            await message.reply("⚠️ หากต้องการใช้งานระบบ Slip Verify ติดต่อ Florentino")
            return

    processing_msg = None
    
    try:
        # 1. Download photo from Telegram to memory
        photo_file = io.BytesIO()
        # Grab the highest resolution photo
        photo = message.photo[-1]
        await bot.download(photo, destination=photo_file)
        image_bytes = photo_file.getvalue()
        
        # 2. Local QR Code Scanning
        qr_data = decode_qr_from_bytes(image_bytes)
        qr_ref = qr_data.get("trans_ref") if qr_data else None
        
        # Determine if we should send a processing message
        if qr_ref:
            # If QR is detected, it is definitely a slip. Send processing message.
            processing_msg = await message.reply("⏳ **กำลังดาวน์โหลดและประมวลผลสลิปโอนเงินของคุณ...**\nกรุณารอสักครู่")
            
            # Check duplicate
            is_dup = await check_duplicate(qr_ref)
            if is_dup:
                await processing_msg.edit_text(
                    f"⚠️ **ตรวจพบการใช้สลิปซ้ำ!**\n\n"
                    f"❌ รหัสอ้างอิง: `{qr_ref}`\n"
                    "สลิปใบนี้เคยได้รับการตรวจสอบและอนุมัติในระบบไปแล้ว ไม่สามารถใช้งานซ้ำได้เพื่อป้องกันการทุจริต",
                    parse_mode="Markdown"
                )
                return
        else:
            # If QR is not detected:
            if is_group:
                # In group chats, if no QR, check if OCR is enabled. If not, silently ignore.
                if not Config.ENABLE_OCR_FALLBACK:
                    return
            else:
                # In DM, send processing message immediately
                processing_msg = await message.reply("⏳ **กำลังดาวน์โหลดและประมวลผลรูปภาพของคุณ...**\nกรุณารอสักครู่")

        # 3. Fallback or Vision OCR parsing
        ocr_data = None
        if qr_ref or Config.ENABLE_OCR_FALLBACK:
            ocr_data = await extract_slip_details(image_bytes)
            
            # In group chats, if no QR, verify if it's actually a slip before replying
            if is_group and not qr_ref:
                if not ocr_data:
                    # Silently ignore unreadable photos in group chats
                    return
                    
                # Check for slip indicator keywords in the extracted text
                text_to_check = f"{ocr_data.get('sender_name') or ''} {ocr_data.get('receiver_name') or ''} {ocr_data.get('trans_ref') or ''}"
                keywords = ["โอน", "สำเร็จ", "บาท", "thb", "transfer", "successful", "ref", "อ้างอิง"]
                is_slip = any(kw in text_to_check.lower() for kw in keywords) or (ocr_data.get("amount") is not None and ocr_data.get("amount") > 0)
                
                if not is_slip:
                    # Silently ignore general photos in group chats
                    return
                    
                # It's a slip! Send a processing message now that we want to reply
                processing_msg = await message.reply("⏳ **กำลังตรวจสอบประมวลผลสลิปโอนเงิน...**")

            # Double check duplicate against OCR trans_ref if QR was missing but OCR found it
            if ocr_data and ocr_data.get("trans_ref") and not qr_ref:
                ocr_ref = ocr_data["trans_ref"]
                is_dup = await check_duplicate(ocr_ref)
                if is_dup:
                    dup_text = (
                        f"⚠️ **ตรวจพบการใช้สลิปซ้ำ!**\n\n"
                        f"❌ รหัสอ้างอิง: `{ocr_ref}`\n"
                        "สลิปใบนี้เคยได้รับการอนุมัติในระบบไปแล้ว ไม่สามารถใช้งานซ้ำได้"
                    )
                    if processing_msg:
                        await processing_msg.edit_text(dup_text, parse_mode="Markdown")
                    else:
                        await message.reply(dup_text, parse_mode="Markdown")
                    return

        # 4. Risk Assessment (Cross-checking details)
        risk_result = assess_slip_risk(qr_data, ocr_data)
        
        # If the risk analysis suggests unsafe
        disclaimer = (
            "\n\n📢 **คำแนะนำ**: ระบบนี้สร้างขึ้นเพื่อตรวจสอบว่า QR Code สามารถใช้งานได้หรือไม่ "
            "(มีโอกาสเป็นสลิปจริงประมาณ 70%) โปรดตรวจสอบบัญชีธนาคารเพื่อความถูกต้อง"
        )

        if not risk_result["is_safe"]:
            warnings_text = "\n".join([f"• {w}" for w in risk_result["warnings"]])
            error_text = (
                f"🚨 **ตรวจสอบสลิปไม่ผ่าน / น่าสงสัย!**\n\n"
                f"**ความเสี่ยงระดับ**: `{risk_result['risk_score']}/100`\n"
                f"**ปัญหาที่พบ:**\n{warnings_text}\n\n"
                "กรุณาส่งรูปภาพสลิปที่ถูกต้อง หรือติดต่อเจ้าหน้าที่หากข้อมูลดังกล่าวมีความผิดพลาด"
                f"{disclaimer}"
            )
            if processing_msg:
                await processing_msg.edit_text(error_text, parse_mode="Markdown")
            else:
                await message.reply(error_text, parse_mode="Markdown")
            return

        # At this point, slip is valid and safe. Let's log it.
        trans_ref = qr_ref or (ocr_data.get("trans_ref") if ocr_data else None) or "UNKNOWN_REF"
        sender_name = ocr_data.get("sender_name") if ocr_data else "ไม่ระบุผู้ส่ง"
        receiver_name = ocr_data.get("receiver_name") if ocr_data else "ไม่ระบุผู้รับ"
        amount = ocr_data.get("amount") if ocr_data else 0.0
        trans_date = ocr_data.get("trans_date") if ocr_data else None
        
        # Log to Supabase Database
        db_logged = await log_transaction(
            trans_ref=trans_ref,
            sender_name=sender_name,
            receiver_name=receiver_name,
            amount=amount,
            trans_date=trans_date,
            raw_ocr=ocr_data
        )
        
        db_status = "⚙️💾✅" if db_logged else "⚙️💾❌"
        masked_sender = mask_name(sender_name)
        
        # 5. Response Message
        if qr_data:
            qr_bank = get_bank_name(qr_data.get("sending_bank"))
            qr_ref_str = qr_data.get("trans_ref")
            qr_status_text = (
                f"🔎 **การตรวจสอบ QR**: `อาจจะเป็นสลิปจริง - ตรวจพบ QR Code`\n"
                f"🏦 **ธนาคารต้นทาง (QR)**: `{qr_bank}`\n"
                f"🔑 **รหัสธุรกรรม (QR)**: `{qr_ref_str}`"
            )
        else:
            qr_status_text = (
                f"🔎 **การตรวจสอบ QR**: `⚠️ น่าสงสัย / อาจจะปลอมแปลง - ตรวจไม่พบ QR Code`"
            )

        # Check amount limits warning
        amount_warning = ""
        try:
            min_limit, max_limit = await get_amount_limits()
            amount_val = float(amount)
            if amount_val < min_limit or amount_val > max_limit:
                amount_warning = (
                    f"\n\n⚠️ **คำเตือนยอดเงินโอน!**\n"
                    f"• ยอดเงินโอน: **{amount_val:,.2f} THB** (อยู่นอกช่วงควบคุมปกติ `{min_limit:,.2f} - {max_limit:,.2f} THB`)\n"
                    f"👉 **กรุณาตรวจสอบยอดเงินในบัญชีอีกครั้ง เพื่อความชัวร์**"
                )
        except Exception as limit_err:
            logger.error(f"Error checking amount limits: {limit_err}")

        success_text = (
            "✅ **สลิปผ่านเกณฑ์ สแกน QR Code ได้**\n\n"
            f"👤 **ผู้โอน**: `{masked_sender}`\n"
            f"🏢 **ผู้รับโอน**: `{receiver_name}`\n"
            f"💵 **จำนวนเงิน**: `{amount:,.2f} THB`\n"
            f"📅 **วันเวลา**: `{trans_date or 'ไม่ระบุ'}`\n"
            f"🔑 **รหัสอ้างอิง (OCR)**: `{trans_ref}`\n\n"
            f"{qr_status_text}\n\n"
            f"{db_status}"
            f"{amount_warning}"
            f"{disclaimer}"
        )
        
        if processing_msg:
            await processing_msg.edit_text(success_text, parse_mode="Markdown")
        else:
            await message.reply(success_text, parse_mode="Markdown")
            
        logger.info(f"Verified slip successfully: {trans_ref} | Amount: {amount}")
        
    except Exception as e:
        logger.error(f"Error processing slip upload: {e}", exc_info=True)
        err_text = "❌ **เกิดข้อผิดพลาดภายในระบบ**\nไม่สามารถประมวลผลรูปภาพได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"
        
        # In group chats, if no processing message was sent, fail silently to avoid spam
        if is_group and not processing_msg:
            return
            
        if processing_msg:
            await processing_msg.edit_text(err_text, parse_mode="Markdown")
        else:
            await message.reply(err_text, parse_mode="Markdown")
