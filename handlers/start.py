import logging
from aiogram import Router, types
from aiogram.filters import CommandStart, Command

logger = logging.getLogger("SlipBot.Handlers.Start")
router = Router()

@router.message(CommandStart())
async def start_handler(message: types.Message):
    """Handles the /start command."""
    welcome_text = (
        "👋 **ยินดีต้อนรับสู่บอทตรวจสอบสลิปโอนเงิน!**\n\n"
        "บอทนี้จะช่วยตรวจสอบความถูกต้องของสลิปโอนเงินธนาคารของไทยโดยอัตโนมัติ เพื่อป้องกันการปลอมแปลงสลิปและการใช้สลิปซ้ำ (Double-spending)\n\n"
        "💡 **วิธีใช้งาน:**\n"
        "เพียงส่งภาพถ่ายหรือรูปสกรีนช็อตของสลิปโอนเงินเข้ามาในแชทนี้ บอทจะทำการสแกน QR Code และตรวจสอบเนื้อหาด้วยระบบ AI ในทันที\n\n"
        "ส่งรูปภาพสลิปของคุณเข้ามาได้เลยครับ!"
    )
    try:
        await message.reply(welcome_text, parse_mode="Markdown")
        logger.info(f"User {message.from_user.id} started the bot.")
    except Exception as e:
        logger.error(f"Error sending start message to user {message.from_user.id}: {e}")


@router.message(Command("help"))
async def help_handler(message: types.Message):
    """Handles the /help command."""
    help_text = (
        "ℹ️ **วิธีใช้งานระบบตรวจสอบสลิป:**\n\n"
        "1. **ส่งรูปภาพสลิป**: ส่งภาพสลิปธนาคารที่มี QR Code ชัดเจนเข้ามาในแชท\n"
        "2. **รอประมวลผล**: ระบบจะตรวจสอบข้อมูลสลิปด้วย:\n"
        "   - การถอดรหัส QR Code (Mini QR) ท้องถิ่น\n"
        "   - การอ่านข้อความด้วย Vision AI ผ่าน OpenRouter\n"
        "   - การเปรียบเทียบข้อมูลความปลอดภัย (Risk Engine)\n"
        "   - การตรวจสอบการใช้สลิปซ้ำจากระบบฐานข้อมูล Supabase\n"
        "3. **ผลลัพธ์**: บอทจะแจ้งผลเป็น ✅ ผ่าน / ⚠️ น่าสงสัย / ❌ ไม่ผ่าน หรือ ซ้ำทันที\n\n"
        "ต้องการสอบถามข้อมูลเพิ่มเติมสามารถติดต่อผู้ดูแลระบบได้ครับ"
    )
    try:
        await message.reply(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error sending help message to user {message.from_user.id}: {e}")
