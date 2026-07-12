import io
import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from config import Config
from database.supabase_db import check_duplicate, log_transaction
from services.qr_decoder import decode_qr_from_bytes
from services.vision_ai import extract_slip_details
from services.risk_engine import assess_slip_risk

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
            response = _supabase_client.table("transactions").select("amount, created_at").execute()
            return response.data
            
        data = await asyncio.to_thread(query_stats)
        
        total_slips = len(data)
        total_amount = sum(float(row.get("amount") or 0) for row in data)
        
        stats_text = (
            "📊 **สถิติการตรวจสอบสลิปของระบบ:**\n\n"
            f"🔹 จำนวนสลิปที่ตรวจสอบผ่านทั้งหมด: `{total_slips}` รายการ\n"
            f"🔹 ยอดเงินสะสมรวม: `{total_amount:,.2f} THB`\n\n"
            "💡 ข้อมูลดึงมาจาก Supabase Database"
        )
        await message.reply(stats_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error executing stats command: {e}")
        await message.reply("❌ เกิดข้อผิดพลาดในการดึงสถิติจากฐานข้อมูล")


@router.message(lambda message: message.photo is not None)
async def process_slip_image(message: types.Message, bot: Bot):
    """Processes any uploaded photo as a bank transfer slip."""
    is_group = message.chat.type in ["group", "supergroup"]
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
        if not risk_result["is_safe"]:
            warnings_text = "\n".join([f"• {w}" for w in risk_result["warnings"]])
            error_text = (
                f"🚨 **ตรวจสอบสลิปไม่ผ่าน / น่าสงสัย!**\n\n"
                f"**ความเสี่ยงระดับ**: `{risk_result['risk_score']}/100`\n"
                f"**ปัญหาที่พบ:**\n{warnings_text}\n\n"
                "กรุณาส่งรูปภาพสลิปที่ถูกต้อง หรือติดต่อเจ้าหน้าที่หากข้อมูลดังกล่าวมีความผิดพลาด"
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
        
        db_status = "บันทึกในฐานข้อมูลแล้ว" if db_logged else "เกิดข้อผิดพลาดในการบันทึกข้อมูล"
        masked_sender = mask_name(sender_name)
        
        # 5. Response Message
        success_text = (
            "✅ **ยืนยันสลิปโอนเงินสำเร็จ!**\n\n"
            f"👤 **ผู้โอน**: `{masked_sender}`\n"
            f"🏢 **ผู้รับโอน**: `{receiver_name}`\n"
            f"💵 **จำนวนเงิน**: `{amount:,.2f} THB`\n"
            f"📅 **วันเวลา**: `{trans_date or 'ไม่ระบุ'}`\n"
            f"🔑 **รหัสอ้างอิง**: `{trans_ref}`\n\n"
            f"🛡️ **สถานะระบบ**: ผ่านเกณฑ์ความปลอดภัย ({db_status})"
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
