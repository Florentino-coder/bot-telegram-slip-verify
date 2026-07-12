import logging
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from config import Config
from database.supabase_db import add_allowed_group, remove_allowed_group, get_allowed_groups

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


@router.message(Command("groupid", "id"))
async def groupid_handler(message: types.Message):
    """Returns the current chat ID."""
    chat_type = message.chat.type
    chat_title = message.chat.title or "Private Chat"
    await message.reply(
        f"📊 **ข้อมูลแชทปัจจุบัน:**\n"
        f"• **ชื่อแชท**: `{chat_title}`\n"
        f"• **ประเภทแชท**: `{chat_type}`\n"
        f"• **Chat ID**: `{message.chat.id}`",
        parse_mode="Markdown"
    )


@router.message(Command("allowgroup"))
async def allowgroup_handler(message: types.Message):
    """Registers the current group as whitelisted in Supabase."""
    # Check if the user is an admin
    if message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    # Check if it is a group/supergroup
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ คำสั่งนี้สามารถใช้งานได้เฉพาะภายในกลุ่มแชทเท่านั้น")
        return

    group_id = message.chat.id
    group_name = message.chat.title or "Unnamed Group"
    added_by = message.from_user.id

    success = await add_allowed_group(group_id, group_name, added_by)
    if success:
        await message.reply(
            f"✅ **อนุญาตการใช้งานกลุ่มนี้เรียบร้อยแล้ว!**\n\n"
            f"• **ชื่อกลุ่ม**: `{group_name}`\n"
            f"• **Group ID**: `{group_id}`\n"
            f"• **ผู้เพิ่มสิทธิ์**: `{message.from_user.full_name}`",
            parse_mode="Markdown"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการลงทะเบียนกลุ่มในฐานข้อมูล")


@router.message(Command("disallowgroup"))
async def disallowgroup_handler(message: types.Message):
    """Removes a group from the whitelist in Supabase."""
    # Check if the user is an admin
    if message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("💡 **วิธีใช้งาน:** `/disallowgroup <group_id>`")
        return

    try:
        target_group_id = int(args[1])
    except ValueError:
        await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลข")
        return

    success = await remove_allowed_group(target_group_id)
    if success:
        await message.reply(f"✅ **ยกเลิกการอนุญาตกลุ่ม ID `{target_group_id}` เรียบร้อยแล้ว!**", parse_mode="Markdown")
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการนำกลุ่มออกจากฐานข้อมูล")


@router.message(Command("groups"))
async def groups_handler(message: types.Message):
    """Lists all whitelisted groups."""
    # Check if the user is an admin
    if message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    groups_list = await get_allowed_groups()
    if not groups_list:
        await message.reply("👥 **ไม่พบกลุ่มแชทที่ได้รับอนุญาตในฐานข้อมูล**")
        return

    text = "👥 **รายชื่อกลุ่มแชทที่ได้รับอนุญาต:**\n\n"
    for i, g in enumerate(groups_list, 1):
        g_name = g.get("group_name") or "กลุ่มไม่ระบุชื่อ"
        g_id = g.get("group_id")
        text += f"{i}. `{g_name}` (ID: `{g_id}`)\n"

    await message.reply(text, parse_mode="Markdown")
