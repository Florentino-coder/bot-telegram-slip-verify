import logging
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from config import Config
from database.supabase_db import (
    add_allowed_group, remove_allowed_group, get_allowed_groups,
    set_maintenance_mode, is_maintenance_mode,
    get_amount_limits, set_amount_limits,
    get_slipok_config, set_slipok_mode, set_slipok_api_key,
    set_slipok_branch_id, set_slipok_min_amount,
    get_merchant_name, set_merchant_name,
    get_merchant_names, add_merchant_name, remove_merchant_name, clear_merchant_names,
    get_allowed_accounts, add_allowed_account, remove_allowed_account, clear_allowed_accounts,
    get_slipok_credentials, add_slipok_credential, remove_slipok_credential, reset_all_slipok_credentials,
    get_slip_log, check_admin_permission, get_bot_admins, add_bot_admin, remove_bot_admin,
    get_group_config, update_group_config
)

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
    # Check if user is an admin to show admin commands manual
    is_admin = await check_admin_permission(message.from_user.id)
    
    if is_admin:
        help_text = (
            "ℹ️ **คู่มือคำสั่งผู้ดูแลระบบ (Admin Command Manual):**\n\n"
            "🔑 **การจัดการสิทธิ์แอดมิน (Super Admin Only):**\n"
            "• `/admin list` : แสดงรายชื่อแอดมินทั้งหมด\n"
            "• `/admin add <user_id> <permissions> [username]` : แต่งตั้งแอดมินรอง\n"
            "• `/admin remove <user_id>` : ยกเลิกสิทธิ์แอดมินรอง\n\n"
            "🏦 **คำสั่งตรวจสอบและสถิติ:**\n"
            "• `/stats` : ดูสถิติและผลประเมินยอดรวมของระบบ\n"
            "• `/slipinfo <slip_id>` : ค้นหารายละเอียดการตรวจสลิปเชิงลึก\n"
            "• `/myid` หรือ `/id` : ตรวจสอบ User ID ของคุณ\n"
            "• `/groupid` : ตรวจสอบ ID ของแชทกลุ่มปัจจุบัน\n\n"
            "👥 **การจัดการกลุ่มแชททั่วไป:**\n"
            "• `/allowgroup` : อนุญาตการใช้งานบอทในกลุ่มปัจจุบัน (พิมพ์ในกลุ่ม)\n"
            "• `/disallowgroup <group_id>` : ยกเลิกสิทธิ์กลุ่ม\n"
            "• `/groups` : แสดงรายชื่อกลุ่มแชทและการตั้งค่าทั้งหมด\n"
            "• `/groupinfo` : แสดงการตั้งค่าเฉพาะของกลุ่มนี้เท่านั้น (พิมพ์ในกลุ่ม)\n\n"
            "📢 **คำสั่งตั้งค่ารายกลุ่มแชท (Group Overrides):**\n"
            "• `/setmerchant <ชื่อ>` : ตั้งร้านผู้รับโอนเฉพาะกลุ่มนี้ใหม่ทั้งหมด\n"
            "• `/addmerchant <ชื่อ>` : เพิ่มร้านค้าต่อท้ายชื่อเดิมเฉพาะกลุ่มนี้\n"
            "• `/delmerchant <ชื่อ>` : ลบเฉพาะชื่อร้านนี้ออกจากกลุ่มนี้\n"
            "• `/setaccount <เลข>` : ตั้งเลขบัญชีเฉพาะกลุ่มนี้ใหม่ทั้งหมด\n"
            "• `/addaccount <เลข>` : เพิ่มเลขบัญชีต่อท้ายบัญชีเดิมเฉพาะกลุ่มนี้\n"
            "• `/delaccount <เลข>` : ลบเฉพาะเลขบัญชีนี้ออกจากกลุ่มนี้\n"
            "• `/setmode <smart/always/off>` : ตั้งโหมด SlipOK เฉพาะกลุ่มนี้\n\n"
            "⚙️ **การตั้งค่าบอทหลัก (Global Config):**\n"
            "• `/maintenance <on/off>` : เปิด/ปิดระบบปิดปรับปรุงบอท\n"
            "• `/limit <min> <max>` : กำหนดช่วงยอดเงินปกติในการโอน\n"
            "• `/merchant` : ดู/เพิ่ม/ลบชื่อร้านผู้รับโอนเริ่มต้นระบบ\n"
            "• `/account` : ดู/เพิ่ม/ลบเลขบัญชีผู้รับโอนเริ่มต้นระบบ\n"
            "• `/slipok` : ดู/ตั้งค่า/เปิดปิด API SlipOK เริ่มต้นระบบ"
        )
    else:
        help_text = (
            "ℹ️ **วิธีใช้งานระบบตรวจสอบสลิป:**\n\n"
            "1. **ส่งรูปภาพสลิป**: ส่งภาพสลิปธนาคารที่มี QR Code ชัดเจนเข้ามาในแชท\n"
            "2. **รอประมวลผล**: ระบบจะตรวจสอบข้อมูลสลิปด้วย:\n"
            "   - การถอดรหัส QR Code (Mini QR) ท้องถิ่น\n"
            "   - การอ่านข้อความด้วย Vision AI OCR ท้องถิ่น\n"
            "   - การเปรียบเทียบข้อมูลความปลอดภัย (Risk Engine)\n"
            "   - การตรวจสอบการใช้สลิปซ้ำจากระบบฐานข้อมูล Supabase\n"
            "3. **ผลลัพธ์**: บอทจะแจ้งผลเป็น ✅ ผ่าน / ⚠️ น่าสงสัย / ❌ ไม่ผ่าน หรือ ซ้ำทันที\n\n"
            "ต้องการสอบถามข้อมูลเพิ่มเติมสามารถติดต่อผู้ดูแลระบบได้ครับ"
        )
        
    try:
        await message.reply(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error sending help message to user {message.from_user.id}: {e}")


@router.message(Command("groupid"))
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


@router.message(Command("myid", "id"))
async def user_id_handler(message: types.Message):
    """Returns the user ID of the sender, or the replied-to user."""
    # Check if this is a reply to another message
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user:
            u_name = f"@{target_user.username}" if target_user.username else "ไม่มี"
            await message.reply(
                f"👤 **ข้อมูลผู้ใช้ที่คุณตอบกลับ:**\n"
                f"• **ชื่อ**: `{target_user.full_name}`\n"
                f"• **Username**: `{u_name}`\n"
                f"• **User ID**: `{target_user.id}`",
                parse_mode="Markdown"
            )
            return
            
    # Default: Return sender's own info
    user = message.from_user
    u_name = f"@{user.username}" if user.username else "ไม่มี"
    await message.reply(
        f"👤 **ข้อมูลผู้ใช้ของคุณ:**\n"
        f"• **ชื่อ**: `{user.full_name}`\n"
        f"• **Username**: `{u_name}`\n"
        f"• **User ID**: `{user.id}`",
        parse_mode="Markdown"
    )


@router.message(Command("allowgroup"))
async def allowgroup_handler(message: types.Message):
    """Registers the current group as whitelisted in Supabase."""
    # Check if the user has groups permission
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
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
    # Check if the user has groups permission
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
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
    """Lists all whitelisted groups with detailed config info."""
    # Check if the user has groups permission
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    groups_list = await get_allowed_groups()
    if not groups_list:
        await message.reply("👥 **ไม่พบกลุ่มแชทที่ได้รับอนุญาตในฐานข้อมูล**")
        return

    text = "👥 **รายชื่อกลุ่มแชทที่ได้รับอนุญาตและการตั้งค่า:**\n\n"
    for i, g in enumerate(groups_list, 1):
        g_name = g.get("group_name") or "กลุ่มไม่ระบุชื่อ"
        g_id = g.get("group_id")
        
        # Query group detailed config
        g_config = await get_group_config(g_id) or {}
        g_merchant = g_config.get("merchant_name") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"
        g_mode = g_config.get("slipok_mode") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"
        g_accounts = g_config.get("allowed_accounts") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"
        
        text += (
            f"{i}. **{g_name}** (ID: `{g_id}`)\n"
            f"   • ร้านค้าผู้รับ: `{g_merchant}`\n"
            f"   • เลขบัญชีรับโอน: `{g_accounts}`\n"
            f"   • โหมดตรวจสอบ: `{g_mode.upper() if g_mode != 'ใช้ค่าเริ่มต้นของระบบ (Global Fallback)' else g_mode}`\n\n"
        )

    await message.reply(text, parse_mode="Markdown")


@router.message(Command("setmerchant"))
async def set_group_merchant_handler(message: types.Message):
    """Admin command to configure merchant name for a specific group."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    merchant_name = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในห้องกลุ่มแชท):**\n"
                "• `/setmerchant <ชื่อร้าน>` : กำหนดชื่อร้านผู้รับโอนเฉพาะกลุ่มนี้\n"
                "• `/setmerchant default` : รีเซ็ตกลับไปใช้ค่าเริ่มต้นหลักของบอท"
            )
            return
        merchant_name = message.text.split(maxsplit=1)[1].strip()
    else:
        # PM chat: must provide group_id
        if len(args) < 3:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในแชทบอทส่วนตัว):**\n"
                "• `/setmerchant <group_id> <ชื่อร้าน>` : กำหนดร้านผู้รับของกลุ่มนี้\n"
                "• `/setmerchant <group_id> default` : รีเซ็ตเป็นค่าเริ่มต้นระบบ"
            )
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลขเชิงลบ")
            return
        merchant_name = args[2].strip()

    # Check if group is whitelisted
    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ หรือกลุ่มนี้ยังไม่ได้รับการอนุญาต")
        return

    success = await update_group_config(group_id, merchant_name=merchant_name)
    if success:
        display_name = f"`{merchant_name}`" if merchant_name.lower() != "default" else "ค่าเริ่มต้นส่วนกลาง (Global Fallback)"
        await message.reply(
            f"✅ **อัปเดตชื่อร้านค้าเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}** (ID: `{group_id}`)\n"
            f"• ชื่อผู้รับโอนที่ยอมรับ: {display_name}"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลลงฐานข้อมูล")


@router.message(Command("setmode"))
async def set_group_mode_handler(message: types.Message):
    """Admin command to configure SlipOK verification mode for a specific group."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split()
    
    group_id = None
    mode = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในห้องกลุ่มแชท):**\n"
                "• `/setmode <smart|always|off>` : เลือกโหมดตรวจสลิปเฉพาะกลุ่มนี้\n"
                "• `/setmode default` : รีเซ็ตเป็นค่าเริ่มต้นระบบ"
            )
            return
        mode = args[1].lower()
    else:
        if len(args) < 3:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในแชทบอทส่วนตัว):**\n"
                "• `/setmode <group_id> <smart|always|off>`\n"
                "• `/setmode <group_id> default`"
            )
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลขเชิงลบ")
            return
        mode = args[2].lower()

    if mode not in ["smart", "always", "off", "default"]:
        await message.reply("❌ โหมดไม่ถูกต้อง กรุณาระบุ: `smart`, `always`, `off` หรือ `default`")
        return

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ หรือกลุ่มนี้ยังไม่ได้รับการอนุญาต")
        return

    success = await update_group_config(group_id, slipok_mode=mode)
    if success:
        display_mode = f"`{mode.upper()}`" if mode != "default" else "ค่าเริ่มต้นส่วนกลาง (Global Fallback)"
        await message.reply(
            f"✅ **อัปเดตโหมด SlipOK เฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}** (ID: `{group_id}`)\n"
            f"• โหมดการประมวลผล: {display_mode}"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลลงฐานข้อมูล")


@router.message(Command("setaccount"))
async def set_group_account_handler(message: types.Message):
    """Admin command to configure allowed accounts for a specific group."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    accounts = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในห้องกลุ่มแชท):**\n"
                "• `/setaccount <เลขบัญชี1 | เลขบัญชี2>` : กำหนดบัญชีรับโอนเฉพาะกลุ่มนี้\n"
                "• `/setaccount default` : รีเซ็ตเป็นค่าเริ่มต้นระบบ"
            )
            return
        accounts = message.text.split(maxsplit=1)[1].strip()
    else:
        if len(args) < 3:
            await message.reply(
                "💡 **วิธีใช้งาน (พิมพ์ในแชทบอทส่วนตัว):**\n"
                "• `/setaccount <group_id> <เลขบัญชี1 | เลขบัญชี2>`\n"
                "• `/setaccount <group_id> default`"
            )
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลขเชิงลบ")
            return
        accounts = args[2].strip()

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ หรือกลุ่มนี้ยังไม่ได้รับการอนุญาต")
        return

    success = await update_group_config(group_id, allowed_accounts=accounts)
    if success:
        display_accs = f"`{accounts}`" if accounts.lower() != "default" else "ค่าเริ่มต้นส่วนกลาง (Global Fallback)"
        await message.reply(
            f"✅ **อัปเดตเลขบัญชีผู้รับโอนเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}** (ID: `{group_id}`)\n"
            f"• รายชื่อบัญชีที่ยอมรับ: {display_accs}"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลลงฐานข้อมูล")


@router.message(Command("maintenance"))
async def maintenance_handler(message: types.Message):
    """Admin command to toggle maintenance mode (เปิด/ปิด บอท)."""
    # Check if the user has maintenance permission
    has_perm = await check_admin_permission(message.from_user.id, "maintenance")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split()
    if len(args) < 2:
        # Show current maintenance status
        is_maint = await is_maintenance_mode()
        status_str = "🛠️ **เปิดใช้งานอยู่ (ปิดปรับปรุงระบบชั่วคราว)**" if is_maint else "✅ **ปิดใช้งานอยู่ (ระบบเปิดทำงานปกติ)**"
        await message.reply(
            f"🛠️ **สถานะระบบปิดปรับปรุง (Maintenance Mode):**\n"
            f"• สถานะปัจจุบัน: {status_str}\n\n"
            f"💡 **วิธีตั้งค่า:**\n"
            f"• `/maintenance on` : เพื่อสั่งปิดปรับปรุงระบบ (บอทจะบล็อกคนทั่วไป)\n"
            f"• `/maintenance off` : เพื่อสั่งเปิดระบบปกติ (ทุกคนใช้ได้ตามปกติ)",
            parse_mode="Markdown"
        )
        return

    action = args[1].lower()
    if action in ["on", "enable", "true"]:
        success = await set_maintenance_mode(True)
        if success:
            await message.reply("🛠️ **เปิดใช้งานระบบปิดปรับปรุงสำเร็จ!**\nนับจากนี้ บอทจะงดบริการสแกนสลิปสำหรับคนทั่วไปชั่วคราว (แอดมินยังสแกนเทสได้ตามปกติ)", parse_mode="Markdown")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลสถานะปิดปรับปรุง")
    elif action in ["off", "disable", "false"]:
        success = await set_maintenance_mode(False)
        if success:
            await message.reply("✅ **ปิดระบบปิดปรับปรุงสำเร็จ!**\nบอทเปิดให้ทุกคนสแกนตรวจสอบสลิปได้ตามปกติแล้วครับ", parse_mode="Markdown")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลสถานะเปิดระบบ")
    else:
        await message.reply("❌ รูปแบบคำสั่งไม่ถูกต้อง กรุณาใช้ `/maintenance on` หรือ `/maintenance off`", parse_mode="Markdown")


@router.message(Command("limit"))
async def limit_handler(message: types.Message):
    """Admin command to configure normal transaction amount limits (ช่วงยอดเงินปกติ)."""
    # Check if the user has limit permission
    has_perm = await check_admin_permission(message.from_user.id, "limit")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split()
    if len(args) < 3:
        # Show current amount limits configuration
        min_amt, max_amt = await get_amount_limits()
        await message.reply(
            f"⚙️ **ช่วงยอดเงินปกติในการตรวจสอบสลิป (Amount Limits):**\n"
            f"• ยอดเงินขั้นต่ำ: `{min_amt:,.2f} THB`\n"
            f"• ยอดเงินขั้นสูงสุด: `{max_amt:,.2f} THB`\n\n"
            f"💡 หากยอดเงินอยู่นอกเหนือช่วงนี้ บอทจะเพิ่มข้อความเตือนร้านค้าทันทีเพื่อความปลอดภัย\n\n"
            f"💡 **วิธีตั้งค่า:**\n"
            f"• `/limit <ยอดต่ำสุด> <ยอดสูงสุด>`\n"
            f"  เช่น: `/limit 100 999` หรือ `/limit 50 1500`",
            parse_mode="Markdown"
        )
        return

    try:
        min_val = float(args[1])
        max_val = float(args[2])
    except ValueError:
        await message.reply("❌ รูปแบบตัวเลขไม่ถูกต้อง กรุณากรอกจำนวนเงินขั้นต่ำและขั้นสูงเป็นตัวเลข")
        return

    if min_val < 0 or max_val < 0:
        await message.reply("❌ จำนวนเงินไม่สามารถติดลบได้")
        return

    if min_val >= max_val:
        await message.reply("❌ ยอดเงินขั้นต่ำต้องน้อยกว่ายอดเงินขั้นสูงสุด")
        return

    success = await set_amount_limits(min_val, max_val)
    if success:
        await message.reply(
            f"✅ **ปรับปรุงช่วงยอดเงินปกติสำเร็จ!**\n\n"
            f"• ยอดเงินขั้นต่ำใหม่: `{min_val:,.2f} THB`\n"
            f"• ยอดเงินขั้นสูงสุดใหม่: `{max_val:,.2f} THB`",
            parse_mode="Markdown"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลช่วงยอดเงินลงฐานข้อมูล")


@router.message(Command("merchant"))
async def merchant_handler(message: types.Message):
    """Admin command to configure the merchant receiver name (ชื่อผู้รับโอน)."""
    # Check if the user has merchant permission
    has_perm = await check_admin_permission(message.from_user.id, "merchant")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        # Show all current merchant names
        names = await get_merchant_names()
        if not names:
            fallback_name = Config.MERCHANT_NAME or "ไม่ได้ตั้งค่า"
            names_text = f"• ยังไม่มีร้านค้าตั้งค่าพิเศษ (ใช้ค่าเริ่มต้นจาก .env: `{fallback_name}`)"
        else:
            names_text = "\n".join([f"{i}. `{name}`" for i, name in enumerate(names, 1)])
            
        await message.reply(
            f"🏢 **รายชื่อร้านค้าผู้รับโอนที่อนุญาต (Merchant Names):**\n\n"
            f"{names_text}\n\n"
            f"💡 **วิธีตั้งค่า:**\n"
            f"• `/merchant add <ชื่อร้าน>` : เพิ่มร้านค้าที่ยอมรับ\n"
            f"• `/merchant remove <ชื่อร้าน>` : ลบร้านค้าออกจากรายการ\n"
            f"• `/merchant clear` : ลบร้านค้าทั้งหมด (กลับไปใช้ค่าใน .env)\n"
            f"• `/merchant <ชื่อร้าน>` : ตั้งค่าให้ยอมรับชื่อนี้เพียงชื่อเดียว (เขียนทับ)",
            parse_mode="Markdown"
        )
        return

    subcommand = args[1].lower()
    
    if subcommand == "add":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/merchant add <ชื่อร้านค้า>`")
            return
        name_to_add = args[2].strip()
        success = await add_merchant_name(name_to_add)
        if success:
            await message.reply(f"✅ **เพิ่มร้านค้าสำเร็จ!**\nเพิ่มร้านค้า: `{name_to_add}` เข้าสู่ระบบแล้ว")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")
            
    elif subcommand == "remove":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/merchant remove <ชื่อร้านค้า>`")
            return
        name_to_remove = args[2].strip()
        success = await remove_merchant_name(name_to_remove)
        if success:
            await message.reply(f"✅ **ลบร้านค้าสำเร็จ!**\nลบร้านค้า: `{name_to_remove}` ออกจากระบบแล้ว")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการลบข้อมูล")
            
    elif subcommand == "clear":
        success = await clear_merchant_names()
        if success:
            fallback = Config.MERCHANT_NAME or "ไม่ได้ตั้งค่า"
            await message.reply(f"✅ **ล้างรายชื่อร้านค้าทั้งหมดเรียบร้อย!**\nระบบจะกลับไปใช้ค่าเริ่มต้นจาก `.env`: `{fallback}`")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการล้างข้อมูล")
            
    else:
        # Overwrite behavior: set sole merchant name
        full_text = message.text.split(maxsplit=1)[1].strip()
        success = await set_merchant_name(full_text)
        if success:
            await message.reply(
                f"✅ **ปรับปรุงชื่อร้านค้าผู้รับโอนสำเร็จ (เขียนทับ)!**\n\n"
                f"• ชื่อร้านค้าใหม่: `{full_text}`",
                parse_mode="Markdown"
            )
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการเขียนทับข้อมูล")


@router.message(Command("slipok"))
async def slipok_handler(message: types.Message):
    """Admin command to configure SlipOK verification API."""
    # Check if the user is an admin
    if message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split()
    cfg = await get_slipok_config()
    
    # helper function to mask API keys
    def mask_key(k: str) -> str:
        if not k:
            return "ไม่ได้ตั้งค่า"
        if len(k) <= 8:
            return "***"
        return f"{k[:4]}***{k[-4:]}"

    if len(args) < 2 or args[1].lower() == "listkeys":
        # Show current configurations & list of multiple credentials with live remaining quota
        mode_icons = {
            "smart": "🧠 **Smart (ตรวจผ่าน Risk Engine ก่อน ค่อยส่ง SlipOK)**",
            "always": "🔒 **Always (ตรวจสอบทุกใบผ่าน SlipOK)**",
            "off": "❌ **Off (ปิดใช้งาน SlipOK / ใช้ Vision AI OCR ปกติ)**"
        }
        current_mode = mode_icons.get(cfg["mode"], cfg["mode"])
        
        # Fetch multiple credentials
        creds = await get_slipok_credentials()
        keys_list_text = ""
        if not creds:
            keys_list_text = "• ยังไม่ได้ตั้งค่า API Key (ระบบ SlipOK จะใช้การไม่ได้)"
        else:
            from services.slipok import check_slipok_quota
            
            lines = []
            for i, c in enumerate(creds, 1):
                key = c.get("api_key")
                branch = c.get("branch_id")
                status = c.get("status", "active")
                
                masked = mask_key(key)
                status_icon = "🟢 Active" if status == "active" else "🔴 Exhausted" if status == "exhausted" else "⚪ Invalid"
                
                # Check live quota
                quota_res = await check_slipok_quota(key, branch)
                if quota_res is not None:
                    remaining = quota_res.get("quota", 0)
                    quota_text = f"`{remaining}` สลิป"
                else:
                    quota_text = "ไม่สามารถเชื่อมต่อได้"
                    
                lines.append(
                    f"{i}. Key: `{masked}` (Branch: `{branch}`)\n"
                    f"   • สถานะ: {status_icon}\n"
                    f"   • โควต้าคงเหลือ: {quota_text}"
                )
            keys_list_text = "\n".join(lines)

        await message.reply(
            f"⚙️ **ตั้งค่าระบบ SlipOK Verification:**\n\n"
            f"• **โหมดปัจจุบัน**: {current_mode}\n"
            f"• **ยอดตรวจขั้นต่ำ (Smart Mode)**: `{cfg['min_amount']:,.2f} THB`\n\n"
            f"🔑 **รายการ API Key / Branch ID ทั้งหมด:**\n"
            f"{keys_list_text}\n\n"
            f"💡 **คำสั่งตั้งค่า:**\n"
            f"• `/slipok mode <smart|always|off>` : สลับโหมดทำงาน\n"
            f"• `/slipok minamount <จำนวนเงิน>` : ตั้งยอดเงินขั้นต่ำในโหมด Smart\n"
            f"• `/slipok addkey <API_KEY> <BRANCH_ID>` : เพิ่ม API Key ใหม่\n"
            f"• `/slipok removekey <ลำดับที่>` : ลบคีย์ตามลำดับ\n"
            f"• `/slipok resetkeys` : รีเซ็ตสถานะคีย์ทั้งหมดให้พร้อมใช้งาน",
            parse_mode="Markdown"
        )
        return

    subcommand = args[1].lower()
    
    if subcommand == "mode":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok mode <smart|always|off>`")
            return
        mode = args[2].lower()
        if mode not in ["smart", "always", "off"]:
            await message.reply("❌ โหมดไม่ถูกต้อง กรุณาเลือก: `smart`, `always` หรือ `off`")
            return
        success = await set_slipok_mode(mode)
        if success:
            await message.reply(f"✅ **ปรับปรุงโหมด SlipOK สำเร็จ!**\nโหมดใหม่: `{mode.upper()}`")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกโหมดการทำงาน")
            
    elif subcommand == "addkey":
        if len(args) < 4:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok addkey <API_KEY> <BRANCH_ID>`")
            return
        key = args[2].strip()
        branch = args[3].strip()
        success = await add_slipok_credential(key, branch)
        if success:
            await message.reply(
                f"✅ **เพิ่ม API Key สำเร็จ!**\n\n"
                f"• API Key: `{mask_key(key)}`\n"
                f"• Branch ID: `{branch}`",
                parse_mode="Markdown"
            )
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")

    elif subcommand == "removekey":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok removekey <ลำดับที่>`")
            return
        try:
            idx = int(args[2]) - 1
            if idx < 0:
                raise ValueError
        except ValueError:
            await message.reply("❌ ลำดับไม่ถูกต้อง กรุณากรอกเป็นตัวเลขเชิงบวก")
            return
            
        success = await remove_slipok_credential(idx)
        if success:
            await message.reply(f"✅ **ลบ API Key ลำดับที่ {idx + 1} สำเร็จ!**")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการลบข้อมูล (กรุณาเช็คลำดับให้ถูกต้อง)")

    elif subcommand == "resetkeys":
        success = await reset_all_slipok_credentials()
        if success:
            await message.reply("✅ **รีเซ็ตสถานะ API Key ทั้งหมดกลับมาพร้อมใช้งานสำเร็จ!**")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการรีเซ็ตสถานะคีย์")

    elif subcommand == "setkey":
        # Backward compatibility wrapper
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok setkey <API_KEY>`")
            return
        key = args[2].strip()
        branch = cfg.get("branch_id") or "71154"
        success = await add_slipok_credential(key, branch)
        if success:
            await message.reply(f"✅ **บันทึก API Key สำเร็จ!**\nรหัสคีย์: `{mask_key(key)}` (Branch: `{branch}`)")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึก API Key")
            
    elif subcommand == "setbranch":
        # Backward compatibility wrapper
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok setbranch <BRANCH_ID>`")
            return
        branch = args[2].strip()
        creds = await get_slipok_credentials()
        key = creds[0].get("api_key") if creds else "LEGACY_KEY_NEEDED"
        success = await add_slipok_credential(key, branch)
        if success:
            await message.reply(f"✅ **บันทึก Branch ID สำเร็จ!**\nรหัสร้าน: `{branch}`")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึก Branch ID")
            
    elif subcommand == "minamount":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/slipok minamount <ยอดเงิน>`")
            return
        try:
            amount = float(args[2])
            if amount < 0:
                raise ValueError
        except ValueError:
            await message.reply("❌ ยอดเงินไม่ถูกต้อง กรุณากรอกเป็นตัวเลขเชิงบวก")
            return
            
        success = await set_slipok_min_amount(amount)
        if success:
            await message.reply(f"✅ **ปรับปรุงยอดตรวจขั้นต่ำสำเร็จ!**\nในโหมด Smart บอทจะบังคับตรวจ SlipOK เสมอเมื่อยอดเงินโอนตั้งแต่ `{amount:,.2f} THB` ขึ้นไป")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกยอดเงินขั้นต่ำ")
            
    else:
        await message.reply("❌ คำสั่งย่อยไม่ถูกต้อง กรุณากรอกคำสั่งให้ถูกต้องตามคู่มือการใช้งานของ `/slipok`")


@router.message(Command("account"))
async def account_handler(message: types.Message):
    """Admin command to configure whitelisted allowed receiver account numbers."""
    # Check if the user has account permission
    has_perm = await check_admin_permission(message.from_user.id, "account")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        # Show all current whitelisted accounts
        accounts = await get_allowed_accounts()
        if not accounts:
            accounts_text = "• ยังไม่ได้ตั้งค่าเลขบัญชีผู้รับโอนเพื่อตรวจสอบ (ปิดการสแกนเช็คเลขบัญชี)"
        else:
            accounts_text = "\n".join([f"{i}. `{acc}`" for i, acc in enumerate(accounts, 1)])
            
        await message.reply(
            f"💳 **รายชื่อเลขบัญชีผู้รับโอนที่ได้รับอนุญาต (Allowed Accounts):**\n\n"
            f"{accounts_text}\n\n"
            f"💡 **วิธีตั้งค่า:**\n"
            f"• `/account add <เลขบัญชี>` : เพิ่มเลขบัญชีที่ยอมรับ\n"
            f"• `/account remove <เลขบัญชี>` : ลบเลขบัญชีออกจากรายการ\n"
            f"• `/account clear` : ล้างบัญชีทั้งหมด (ปิดการตรวจสอบเลขบัญชี)",
            parse_mode="Markdown"
        )
        return

    subcommand = args[1].lower()
    
    if subcommand == "add":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/account add <เลขบัญชี>`")
            return
        acc_to_add = args[2].strip()
        success = await add_allowed_account(acc_to_add)
        if success:
            await message.reply(f"✅ **เพิ่มเลขบัญชีสำเร็จ!**\nเพิ่มเลขบัญชี: `{acc_to_add}` เข้าสู่ระบบแล้ว")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล (กรุณากรอกเฉพาะตัวเลขและเครื่องหมาย wildcard เช่น x)")
            
    elif subcommand == "remove":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/account remove <เลขบัญชี>`")
            return
        acc_to_remove = args[2].strip()
        success = await remove_allowed_account(acc_to_remove)
        if success:
            await message.reply(f"✅ **ลบเลขบัญชีสำเร็จ!**\nลบเลขบัญชี: `{acc_to_remove}` ออกจากระบบแล้ว")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการลบข้อมูล")
            
    elif subcommand == "clear":
        success = await clear_allowed_accounts()
        if success:
            await message.reply("✅ **ล้างรายชื่อเลขบัญชีทั้งหมดเรียบร้อย!**\nระบบจะข้ามการตรวจสอบเลขบัญชีผู้รับโอน")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการล้างข้อมูล")
            
    else:
        await message.reply("❌ คำสั่งย่อยไม่ถูกต้อง กรุณากรอกคำสั่งให้ถูกต้องตามคู่มือการใช้งานของ `/account`")


@router.message(Command("slipinfo"))
async def slip_info_handler(message: types.Message):
    """Admin command to query detailed slip verification logs by Slip ID."""
    # Check if the user has slipinfo permission
    has_perm = await check_admin_permission(message.from_user.id, "slipinfo")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("💡 **วิธีใช้งาน:** `/slipinfo <SLIP_ID>`")
        return

    slip_id = args[1].strip()
    log = await get_slip_log(slip_id)
    if not log:
        await message.reply(f"❌ ไม่พบข้อมูลสำหรับ Slip ID: `{slip_id}`")
        return

    # Extract fields
    status = log.get("status", "UNKNOWN")
    created_at = log.get("created_at", "ไม่ระบุ")
    user_id = log.get("telegram_user_id", "ไม่ระบุ")
    username = log.get("telegram_username") or "ไม่ระบุ"
    chat_id = log.get("chat_id", "ไม่ระบุ")
    file_id = log.get("telegram_file_id") or "ไม่มี (N/A)"
    image_hash = log.get("image_hash") or "N/A"
    ref = log.get("reference") or "N/A"
    amount = log.get("amount")
    amount_str = f"{float(amount):,.2f} THB" if amount is not None else "N/A"
    risk_score = log.get("risk_score")
    risk_score_str = f"{risk_score}/100" if risk_score is not None else "N/A"
    failure_reason = log.get("failure_reason") or "ไม่มี"
    error_code = log.get("error_code") or "ไม่มี"
    processing_time = log.get("processing_time_ms")
    proc_time_str = f"{processing_time:,} ms" if processing_time is not None else "N/A"

    # Format JSON fields nicely for display
    def format_json(obj):
        if not obj:
            return "N/A"
        import json
        try:
            return f"```json\n{json.dumps(obj, indent=2, ensure_ascii=False)}\n```"
        except Exception:
            return str(obj)

    qr_result_str = format_json(log.get("qr_result"))
    ocr_result_str = format_json(log.get("ocr_result"))
    slipok_result_str = format_json(log.get("slipok_result"))
    risk_result_str = format_json(log.get("risk_result"))

    status_icon = "🟢 PASS" if status == "PASS" else "🔴 FAIL" if status == "FAIL" else "⚪ ERROR"

    response_text = (
        f"📊 **ข้อมูลสลิปรายละเอียด (Slip Audit Logs)**\n"
        f"• **Slip ID**: `{slip_id}`\n"
        f"• **สถานะการตรวจสอบ**: {status_icon}\n"
        f"• **วันเวลาธุรกรรม**: `{created_at}`\n"
        f"• **ผู้ส่งรูปภาพ**: ID: `{user_id}` (Username: @{username})\n"
        f"• **Chat ID**: `{chat_id}`\n"
        f"• **File ID**: `{file_id}`\n"
        f"• **Image Hash**: `{image_hash[:16]}...`\n"
        f"• **เวลาประมวลผล**: `{proc_time_str}`\n\n"
        f"💰 **ข้อมูลสลิปที่จับคู่ได้:**\n"
        f"• **รหัสอ้างอิงธุรกรรม**: `{ref}`\n"
        f"• **จำนวนเงิน**: `{amount_str}`\n"
        f"• **ระดับความเสี่ยง**: `{risk_score_str}`\n"
        f"• **เหตุผลข้อผิดพลาด**: `{failure_reason}`\n"
        f"• **Error Code**: `{error_code}`\n\n"
        f"🔍 **ผลลัพธ์ขั้นตอนละเอียด:**\n"
        f"💬 **1. Local QR Result**:\n{qr_result_str}\n"
        f"💬 **2. Gemini OCR Result**:\n{ocr_result_str}\n"
        f"💬 **3. SlipOK API Result**:\n{slipok_result_str}\n"
        f"💬 **4. Risk Engine Result**:\n{risk_result_str}"
    )

    if len(response_text) > 4000:
        response_text = response_text[:3900] + "\n\n... (ข้อมูลยาวเกินขนาดการแสดงผลบน Telegram) ..."

    await message.reply(response_text, parse_mode="Markdown")


@router.message(Command("admin"))
async def admin_management_handler(message: types.Message):
    """Super Admin command to manage bot co-admins and their permissions."""
    # Strictly limited to hardcoded Super Admins for security
    if message.from_user.id not in Config.ADMIN_USER_IDS:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    args = message.text.split(maxsplit=4)
    if len(args) < 2:
        help_text = (
            "🔑 **ระบบจัดการสิทธิ์แอดมินบอท (Admin Permissions Manager)**\n\n"
            "💡 **วิธีใช้งานสำหรับ Super Admin:**\n"
            "• `/admin list` : ดูรายชื่อแอดมินทั้งหมดและสิทธิ์\n"
            "• `/admin add <user_id> <permissions> [username]` : เพิ่มแอดมินรอง\n"
            "• `/admin remove <user_id>` : ลบแอดมินรองออกจากระบบ\n\n"
            "📋 **คำสั่งที่สามารถกำหนดสิทธิ์ได้ (Valid Permissions):**\n"
            "• `stats` : ดูสถิติสลิปสะสม (`/stats`)\n"
            "• `slipinfo` : ค้นหารายละเอียดสลิปดิบ (`/slipinfo`)\n"
            "• `groups` : จัดการกลุ่มแชท (`/allowgroup`, `/disallowgroup`, `/groups`)\n"
            "• `maintenance` : เปิด/ปิดบอท (`/maintenance`)\n"
            "• `limit` : ตั้งค่าขีดจำกัดจำนวนเงินยอดโอน (`/limit`)\n"
            "• `merchant` : ตั้งชื่อร้านผู้รับโอน (`/merchant`)\n"
            "• `account` : ตั้งเลขบัญชีธนาคารปลายทาง (`/account`)\n\n"
            "💡 *ตัวอย่างการเพิ่มสิทธิ์*: `/admin add 12345678 stats,groups somchai`"
        )
        await message.reply(help_text, parse_mode="Markdown")
        return

    subcommand = args[1].lower()

    if subcommand == "list":
        admins = await get_bot_admins()
        if not admins:
            admins_text = "• ยังไม่มีการตั้งค่าแอดมินรองในระบบ"
        else:
            lines = []
            for i, adm in enumerate(admins, 1):
                role_label = "👑 Super Admin" if adm.get("role") == "super_admin" else "👤 Co-Admin"
                u_id = adm.get("user_id")
                u_name = f" (@{adm.get('username')})" if adm.get("username") else ""
                perms = adm.get("permissions") or []
                perms_str = ", ".join(perms) if perms else "ไม่มีสิทธิ์"
                lines.append(f"{i}. ID: `{u_id}`{u_name}\n    • บทบาท: `{role_label}`\n    • สิทธิ์: `{perms_str}`")
            admins_text = "\n\n".join(lines)

        # Also show hardcoded Super Admins from env
        env_admins = []
        for i, env_id in enumerate(Config.ADMIN_USER_IDS, 1):
            env_admins.append(f"{i}. ID: `{env_id}` (ระบุใน .env)")
        env_admins_text = "\n".join(env_admins)

        await message.reply(
            f"🔑 **รายชื่อแอดมินระบบทั้งหมด:**\n\n"
            f"👑 **Super Admins หลัก (จากไฟล์ Config):**\n"
            f"{env_admins_text}\n\n"
            f"👤 **แอดมินในฐานข้อมูล (Database Admins):**\n"
            f"{admins_text}",
            parse_mode="Markdown"
        )
        return

    elif subcommand == "add":
        if len(args) < 4:
            await message.reply("💡 **วิธีใช้งาน:** `/admin add <user_id> <permissions> [username]`\nเช่น: `/admin add 12345678 stats,groups somchai`")
            return
        
        try:
            target_id = int(args[2])
        except ValueError:
            await message.reply("❌ รูปแบบ User ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลข")
            return

        raw_perms = args[3].strip().lower().split(",")
        perms_to_add = []
        invalid_perms = []
        
        VALID_PERMISSIONS = {"stats", "slipinfo", "groups", "maintenance", "limit", "merchant", "account"}
        
        for p in raw_perms:
            p_clean = p.strip()
            if not p_clean:
                continue
            if p_clean in VALID_PERMISSIONS:
                perms_to_add.append(p_clean)
            else:
                invalid_perms.append(p_clean)
                
        if invalid_perms:
            await message.reply(
                f"❌ พบสิทธิ์ที่ไม่ถูกต้อง: `{', '.join(invalid_perms)}`\n"
                f"💡 คำสั่งสิทธิ์ที่กรอกได้คือ: `stats`, `slipinfo`, `groups`, `maintenance`, `limit`, `merchant`, `account`"
            )
            return
            
        username = args[4].strip() if len(args) > 4 else None
        
        success = await add_bot_admin(target_id, username, "co_admin", perms_to_add)
        if success:
            perms_str = ", ".join(perms_to_add) if perms_to_add else "ไม่มีสิทธิ์"
            u_name_str = f" (@{username})" if username else ""
            await message.reply(
                f"✅ **แต่งตั้งแอดมินรอง (Co-Admin) สำเร็จ!**\n\n"
                f"• **User ID**: `{target_id}`{u_name_str}\n"
                f"• **สิทธิ์ใช้งาน**: `{perms_str}`",
                parse_mode="Markdown"
            )
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูลสิทธิ์ลงฐานข้อมูล")

    elif subcommand == "remove":
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/admin remove <user_id>`")
            return
            
        try:
            target_id = int(args[2])
        except ValueError:
            await message.reply("❌ รูปแบบ User ID ไม่ถูกต้อง กรุณากรอกเป็นตัวเลข")
            return
            
        success = await remove_bot_admin(target_id)
        if success:
            await message.reply(f"✅ **ยกเลิกความเป็นแอดมินของ ID `{target_id}` สำเร็จ!**")
        else:
            await message.reply("❌ เกิดข้อผิดพลาดในการลบข้อมูลออกจากฐานข้อมูล")
            
    else:
        await message.reply("❌ คำสั่งย่อยไม่ถูกต้อง กรุณากรอกคำสั่งให้ถูกต้องตามคู่มือการใช้งานของ `/admin`")


@router.message(Command("groupinfo"))
async def groupinfo_handler(message: types.Message):
    """Admin command to show detailed config settings for the current group."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    group_id = message.chat.id
    
    # In private chat, need to provide group_id
    if not is_chat_group:
        args = message.text.split()
        if len(args) < 2:
            await message.reply("💡 **วิธีใช้งาน (พิมพ์ในแชทบอทส่วนตัว):** `/groupinfo <group_id>`")
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง")
            return

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ หรือกลุ่มยังไม่ได้รับอนุญาต")
        return

    g_name = g_config.get("group_name") or "กลุ่มไม่ระบุชื่อ"
    g_merchant = g_config.get("merchant_name") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"
    g_mode = g_config.get("slipok_mode") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"
    g_accounts = g_config.get("allowed_accounts") or "ใช้ค่าเริ่มต้นของระบบ (Global Fallback)"

    info_text = (
        f"👥 **ข้อมูลและการตั้งค่ากลุ่มนี้:**\n\n"
        f"• **ชื่อกลุ่ม**: **{g_name}**\n"
        f"• **Group ID**: `{group_id}`\n"
        f"• **ร้านค้าผู้รับ**: `{g_merchant}`\n"
        f"• **เลขบัญชีรับโอน**: `{g_accounts}`\n"
        f"• **โหมดตรวจสอบ**: `{g_mode.upper() if g_mode != 'ใช้ค่าเริ่มต้นของระบบ (Global Fallback)' else g_mode}`"
    )
    await message.reply(info_text, parse_mode="Markdown")


@router.message(Command("addmerchant"))
async def add_group_merchant_handler(message: types.Message):
    """Admin command to append a merchant name to the group list."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    name_to_add = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply("💡 **วิธีใช้งาน:** `/addmerchant <ชื่อร้าน>`")
            return
        name_to_add = message.text.split(maxsplit=1)[1].strip()
    else:
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/addmerchant <group_id> <ชื่อร้าน>`")
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง")
            return
        name_to_add = args[2].strip()

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ")
        return

    # Parse existing names
    existing = g_config.get("merchant_name") or ""
    sep = "|" if "|" in existing else ","
    names_list = [n.strip() for n in existing.split(sep) if n.strip()]
    
    # Check duplicate
    if any(n.lower() == name_to_add.lower() for n in names_list):
        await message.reply(f"💡 มีชื่อ `{name_to_add}` อยู่ในการตั้งค่ากลุ่มนี้แล้ว")
        return

    names_list.append(name_to_add)
    new_merchant_str = " | ".join(names_list)
    
    success = await update_group_config(group_id, merchant_name=new_merchant_str)
    if success:
        await message.reply(
            f"✅ **เพิ่มชื่อร้านค้าเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}**\n"
            f"• รายชื่อผู้รับโอนปัจจุบัน: `{new_merchant_str}`"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")


@router.message(Command("delmerchant"))
async def del_group_merchant_handler(message: types.Message):
    """Admin command to remove a specific merchant name from the group list."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    name_to_del = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply("💡 **วิธีใช้งาน:** `/delmerchant <ชื่อร้าน>`")
            return
        name_to_del = message.text.split(maxsplit=1)[1].strip()
    else:
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/delmerchant <group_id> <ชื่อร้าน>`")
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง")
            return
        name_to_del = args[2].strip()

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ")
        return

    existing = g_config.get("merchant_name") or ""
    if not existing:
        await message.reply("💡 กลุ่มนี้ยังไม่มีการตั้งชื่อร้านเฉพาะตัว")
        return

    sep = "|" if "|" in existing else ","
    names_list = [n.strip() for n in existing.split(sep) if n.strip()]
    
    # Filter out target name
    new_names_list = [n for n in names_list if n.lower() != name_to_del.lower()]
    
    if len(new_names_list) == len(names_list):
        await message.reply(f"💡 ไม่พบชื่อร้าน `{name_to_del}` ในการตั้งค่ากลุ่มนี้")
        return

    new_merchant_str = " | ".join(new_names_list) if new_names_list else "default"
    
    success = await update_group_config(group_id, merchant_name=new_merchant_str)
    if success:
        display_str = f"`{new_merchant_str}`" if new_merchant_str != "default" else "กลับไปใช้ค่าเริ่มต้นระบบ (Global Fallback)"
        await message.reply(
            f"✅ **ลบชื่อร้านค้าเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}**\n"
            f"• รายชื่อผู้รับโอนปัจจุบัน: {display_str}"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")


@router.message(Command("addaccount"))
async def add_group_account_handler(message: types.Message):
    """Admin command to append an allowed account to the group list."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    acc_to_add = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply("💡 **วิธีใช้งาน:** `/addaccount <เลขบัญชี>`")
            return
        acc_to_add = message.text.split(maxsplit=1)[1].strip()
    else:
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/addaccount <group_id> <เลขบัญชี>`")
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง")
            return
        acc_to_add = args[2].strip()

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ")
        return

    # Clean the input account format (digits only or wildcards)
    clean_acc = "".join([c for c in acc_to_add if c.isdigit() or c.lower() in ("x", "*", "_")])
    if not clean_acc:
        await message.reply("❌ รูปแบบบัญชีไม่ถูกต้อง กรุณากรอกเฉพาะตัวเลขและอักขระเช็ค")
        return

    existing = g_config.get("allowed_accounts") or ""
    sep = "|" if "|" in existing else ","
    accs_list = [a.strip() for a in existing.split(sep) if a.strip()]
    
    if clean_acc in accs_list:
        await message.reply(f"💡 มีเลขบัญชี `{clean_acc}` อยู่ในการตั้งค่ากลุ่มนี้แล้ว")
        return

    accs_list.append(clean_acc)
    new_acc_str = " | ".join(accs_list)
    
    success = await update_group_config(group_id, allowed_accounts=new_acc_str)
    if success:
        await message.reply(
            f"✅ **เพิ่มเลขบัญชีเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}**\n"
            f"• บัญชีผู้รับโอนปัจจุบัน: `{new_acc_str}`"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")


@router.message(Command("delaccount"))
async def del_group_account_handler(message: types.Message):
    """Admin command to remove an allowed account from the group list."""
    has_perm = await check_admin_permission(message.from_user.id, "groups")
    if not has_perm:
        await message.reply("❌ คุณไม่มีสิทธิ์เข้าถึงคำสั่งนี้")
        return

    is_chat_group = message.chat.type in ["group", "supergroup"]
    args = message.text.split(maxsplit=2)
    
    group_id = None
    acc_to_del = None
    
    if is_chat_group:
        group_id = message.chat.id
        if len(args) < 2:
            await message.reply("💡 **วิธีใช้งาน:** `/delaccount <เลขบัญชี>`")
            return
        acc_to_del = message.text.split(maxsplit=1)[1].strip()
    else:
        if len(args) < 3:
            await message.reply("💡 **วิธีใช้งาน:** `/delaccount <group_id> <เลขบัญชี>`")
            return
        try:
            group_id = int(args[1])
        except ValueError:
            await message.reply("❌ รูปแบบ Group ID ไม่ถูกต้อง")
            return
        acc_to_del = args[2].strip()

    g_config = await get_group_config(group_id)
    if not g_config:
        await message.reply(f"❌ ไม่พบกลุ่ม ID `{group_id}` ในระบบ")
        return

    existing = g_config.get("allowed_accounts") or ""
    if not existing:
        await message.reply("💡 กลุ่มนี้ยังไม่มีการตั้งค่าเลขบัญชีเฉพาะตัว")
        return

    clean_del = "".join([c for c in acc_to_del if c.isdigit() or c.lower() in ("x", "*", "_")])
    sep = "|" if "|" in existing else ","
    accs_list = [a.strip() for a in existing.split(sep) if a.strip()]
    
    new_accs_list = [a for a in accs_list if a != clean_del]
    
    if len(new_accs_list) == len(accs_list):
        await message.reply(f"💡 ไม่พบเลขบัญชี `{clean_acc}` ในการตั้งค่ากลุ่มนี้")
        return

    new_acc_str = " | ".join(new_accs_list) if new_accs_list else "default"
    
    success = await update_group_config(group_id, allowed_accounts=new_acc_str)
    if success:
        display_str = f"`{new_acc_str}`" if new_acc_str != "default" else "กลับไปใช้ค่าเริ่มต้นระบบ (Global Fallback)"
        await message.reply(
            f"✅ **ลบเลขบัญชีเฉพาะกลุ่มสำเร็จ!**\n"
            f"• กลุ่ม: **{g_config.get('group_name')}**\n"
            f"• บัญชีผู้รับโอนปัจจุบัน: {display_str}"
        )
    else:
        await message.reply("❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล")

