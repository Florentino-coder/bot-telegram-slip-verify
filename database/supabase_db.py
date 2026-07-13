import asyncio
import logging
from supabase import create_client, Client
from config import Config
from services.risk_engine import normalize_ref

logger = logging.getLogger("SlipBot.Database")

# Initialize Supabase client
_supabase_client: Client = None

if Config.SUPABASE_URL and Config.SUPABASE_KEY:
    try:
        _supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
else:
    logger.warning("Supabase URL or Key is missing. Database operations will fail.")


def _db_check_duplicate(trans_ref: str) -> bool:
    """Synchronous database call to check for duplicates."""
    if not _supabase_client:
        logger.error("Supabase client not initialized.")
        return False
    norm_ref = normalize_ref(trans_ref)
    try:
        response = _supabase_client.table("transactions").select("trans_ref").eq("trans_ref", norm_ref).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking duplicate for {norm_ref}: {e}")
        return False


def _db_log_transaction(trans_ref: str, sender_name: str, receiver_name: str, amount: float, trans_date: str, raw_ocr: dict) -> bool:
    """Synchronous database call to log a transaction."""
    if not _supabase_client:
        logger.error("Supabase client not initialized.")
        return False
    norm_ref = normalize_ref(trans_ref)
    try:
        data = {
            "trans_ref": norm_ref,
            "sender_name": sender_name,
            "receiver_name": receiver_name,
            "amount": amount,
            "trans_date": trans_date,
            "raw_ocr": raw_ocr,
            "is_valid": True
        }
        _supabase_client.table("transactions").insert(data).execute()
        logger.info(f"Transaction logged successfully: {norm_ref}")
        return True
    except Exception as e:
        logger.error(f"Error logging transaction {norm_ref}: {e}")
        return False


async def check_duplicate(trans_ref: str) -> bool:
    """Asynchronously checks if the transaction reference already exists in the database."""
    if not trans_ref:
        return False
    # Run synchronous DB lookup in a separate thread to prevent blocking the event loop
    return await asyncio.to_thread(_db_check_duplicate, trans_ref)


async def log_transaction(trans_ref: str, sender_name: str, receiver_name: str, amount: float, trans_date: str, raw_ocr: dict) -> bool:
    """Asynchronously logs a new transaction in the database."""
    if not trans_ref:
        return False
    # Run synchronous DB write in a separate thread to prevent blocking the event loop
    return await asyncio.to_thread(_db_log_transaction, trans_ref, sender_name, receiver_name, amount, trans_date, raw_ocr)


# --- Allowed Groups Management (Access Control) ---

def _db_add_allowed_group(group_id: int, group_name: str, added_by: int) -> bool:
    if not _supabase_client:
        return False
    try:
        data = {
            "group_id": group_id,
            "group_name": group_name,
            "added_by": added_by
        }
        _supabase_client.table("allowed_groups").upsert(data).execute()
        logger.info(f"Group {group_id} whitelisted successfully.")
        return True
    except Exception as e:
        logger.error(f"Error adding allowed group {group_id}: {e}")
        return False

def _db_remove_allowed_group(group_id: int) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("allowed_groups").delete().eq("group_id", group_id).execute()
        logger.info(f"Group {group_id} removed from whitelist.")
        return True
    except Exception as e:
        logger.error(f"Error removing allowed group {group_id}: {e}")
        return False

def _db_is_group_allowed(group_id: int) -> bool:
    if not _supabase_client:
        return False
    try:
        response = _supabase_client.table("allowed_groups").select("group_id").eq("group_id", group_id).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking allowed group {group_id}: {e}")
        return False

def _db_get_allowed_groups() -> list:
    if not _supabase_client:
        return []
    try:
        response = _supabase_client.table("allowed_groups").select("group_id, group_name, created_at").order("created_at").execute()
        return response.data
    except Exception as e:
        logger.error(f"Error getting allowed groups: {e}")
        return []

async def add_allowed_group(group_id: int, group_name: str, added_by: int) -> bool:
    return await asyncio.to_thread(_db_add_allowed_group, group_id, group_name, added_by)

async def remove_allowed_group(group_id: int) -> bool:
    return await asyncio.to_thread(_db_remove_allowed_group, group_id)

async def is_group_allowed(group_id: int) -> bool:
    return await asyncio.to_thread(_db_is_group_allowed, group_id)

async def get_allowed_groups() -> list:
    return await asyncio.to_thread(_db_get_allowed_groups)


# --- Bot Settings Management (Maintenance Mode) ---

def _db_set_maintenance_mode(enabled: bool) -> bool:
    if not _supabase_client:
        return False
    try:
        val_str = "true" if enabled else "false"
        _supabase_client.table("bot_settings").upsert({"key": "maintenance_mode", "value": val_str}).execute()
        logger.info(f"Maintenance mode set to {enabled}")
        return True
    except Exception as e:
        logger.error(f"Error setting maintenance mode: {e}")
        return False

def _db_is_maintenance_mode() -> bool:
    if not _supabase_client:
        return False
    try:
        response = _supabase_client.table("bot_settings").select("value").eq("key", "maintenance_mode").execute()
        if response.data:
            return response.data[0].get("value") == "true"
        return False
    except Exception as e:
        logger.error(f"Error reading maintenance mode: {e}")
        return False

async def set_maintenance_mode(enabled: bool) -> bool:
    return await asyncio.to_thread(_db_set_maintenance_mode, enabled)

async def is_maintenance_mode() -> bool:
    return await asyncio.to_thread(_db_is_maintenance_mode)


def _db_get_amount_limits() -> tuple[float, float]:
    if not _supabase_client:
        return (100.0, 999.0)
    try:
        response = _supabase_client.table("bot_settings").select("key, value").in_("key", ["min_amount", "max_amount"]).execute()
        min_val = 100.0
        max_val = 999.0
        for row in response.data:
            k = row.get("key")
            v = row.get("value")
            try:
                if k == "min_amount":
                    min_val = float(v)
                elif k == "max_amount":
                    max_val = float(v)
            except ValueError:
                pass
        return (min_val, max_val)
    except Exception as e:
        logger.error(f"Error reading amount limits from db: {e}")
        return (100.0, 999.0)

def _db_set_amount_limits(min_val: float, max_val: float) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "min_amount", "value": str(min_val)}).execute()
        _supabase_client.table("bot_settings").upsert({"key": "max_amount", "value": str(max_val)}).execute()
        logger.info(f"Amount limits updated: Min={min_val}, Max={max_val}")
        return True
    except Exception as e:
        logger.error(f"Error setting amount limits in db: {e}")
        return False

async def get_amount_limits() -> tuple[float, float]:
    return await asyncio.to_thread(_db_get_amount_limits)

async def set_amount_limits(min_val: float, max_val: float) -> bool:
    return await asyncio.to_thread(_db_set_amount_limits, min_val, max_val)


# --- SlipOK & Merchant Name Settings Management ---

def _db_get_slipok_config() -> dict:
    config = {
        "mode": "off",
        "api_key": "",
        "branch_id": "",
        "min_amount": 500.0
    }
    if not _supabase_client:
        return config
    try:
        response = _supabase_client.table("bot_settings").select("key, value").in_("key", ["slipok_mode", "slipok_api_key", "slipok_branch_id", "slipok_min_amount"]).execute()
        for row in response.data:
            k = row.get("key")
            v = row.get("value")
            if k == "slipok_mode":
                config["mode"] = v if v in ["smart", "always", "off"] else "off"
            elif k == "slipok_api_key":
                config["api_key"] = v or ""
            elif k == "slipok_branch_id":
                config["branch_id"] = v or ""
            elif k == "slipok_min_amount":
                try:
                    config["min_amount"] = float(v)
                except ValueError:
                    pass
        return config
    except Exception as e:
        logger.error(f"Error reading slipok config: {e}")
        return config

def _db_set_slipok_mode(mode: str) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "slipok_mode", "value": mode}).execute()
        logger.info(f"SlipOK mode set to {mode}")
        return True
    except Exception as e:
        logger.error(f"Error setting slipok mode: {e}")
        return False

def _db_set_slipok_api_key(api_key: str) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "slipok_api_key", "value": api_key}).execute()
        logger.info("SlipOK API key updated in DB")
        return True
    except Exception as e:
        logger.error(f"Error setting slipok api key: {e}")
        return False

def _db_set_slipok_branch_id(branch_id: str) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "slipok_branch_id", "value": branch_id}).execute()
        logger.info(f"SlipOK branch ID set to {branch_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting slipok branch id: {e}")
        return False

def _db_set_slipok_min_amount(amount: float) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "slipok_min_amount", "value": str(amount)}).execute()
        logger.info(f"SlipOK min amount set to {amount}")
        return True
    except Exception as e:
        logger.error(f"Error setting slipok min amount: {e}")
        return False

def _db_get_merchant_name() -> str:
    if not _supabase_client:
        return Config.MERCHANT_NAME or ""
    try:
        response = _supabase_client.table("bot_settings").select("value").eq("key", "merchant_name").execute()
        if response.data and response.data[0].get("value"):
            return response.data[0].get("value")
        return Config.MERCHANT_NAME or ""
    except Exception as e:
        logger.error(f"Error reading merchant name: {e}")
        return Config.MERCHANT_NAME or ""

def _db_set_merchant_name(name: str) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "merchant_name", "value": name}).execute()
        logger.info(f"Merchant name set to {name}")
        return True
    except Exception as e:
        logger.error(f"Error setting merchant name: {e}")
        return False

async def get_slipok_config() -> dict:
    return await asyncio.to_thread(_db_get_slipok_config)

async def set_slipok_mode(mode: str) -> bool:
    return await asyncio.to_thread(_db_set_slipok_mode, mode)

async def set_slipok_api_key(api_key: str) -> bool:
    return await asyncio.to_thread(_db_set_slipok_api_key, api_key)

async def set_slipok_branch_id(branch_id: str) -> bool:
    return await asyncio.to_thread(_db_set_slipok_branch_id, branch_id)

async def set_slipok_min_amount(amount: float) -> bool:
    return await asyncio.to_thread(_db_set_slipok_min_amount, amount)

async def get_merchant_name() -> str:
    return await asyncio.to_thread(_db_get_merchant_name)

async def set_merchant_name(name: str) -> bool:
    return await asyncio.to_thread(_db_set_merchant_name, name)


def _db_get_merchant_names() -> list[str]:
    raw_name = _db_get_merchant_name()
    if not raw_name:
        return []
    sep = "|" if "|" in raw_name else ","
    names = [n.strip() for n in raw_name.split(sep) if n.strip()]
    return names

def _db_add_merchant_name(name: str) -> bool:
    names = _db_get_merchant_names()
    # Case-insensitive deduplication check
    for existing_name in names:
        if existing_name.lower() == name.lower():
            return True
    names.append(name)
    new_raw_val = "|".join(names)
    return _db_set_merchant_name(new_raw_val)

def _db_remove_merchant_name(name: str) -> bool:
    names = _db_get_merchant_names()
    # Case-insensitive removal
    new_names = [n for n in names if n.lower() != name.lower()]
    if len(new_names) == len(names):
        return True # Not found, nothing to remove
    new_raw_val = "|".join(new_names)
    return _db_set_merchant_name(new_raw_val)

def _db_clear_merchant_names() -> bool:
    return _db_set_merchant_name("")


async def get_merchant_names() -> list[str]:
    return await asyncio.to_thread(_db_get_merchant_names)

async def add_merchant_name(name: str) -> bool:
    return await asyncio.to_thread(_db_add_merchant_name, name)

async def remove_merchant_name(name: str) -> bool:
    return await asyncio.to_thread(_db_remove_merchant_name, name)

async def clear_merchant_names() -> bool:
    return await asyncio.to_thread(_db_clear_merchant_names)


# --- Allowed Accounts Settings Management ---

def _db_get_allowed_accounts() -> list[str]:
    if not _supabase_client:
        return []
    try:
        response = _supabase_client.table("bot_settings").select("value").eq("key", "allowed_accounts").execute()
        if response.data and response.data[0].get("value"):
            raw_acc = response.data[0].get("value")
            return [a.strip() for a in raw_acc.split("|") if a.strip()]
        return []
    except Exception as e:
        logger.error(f"Error reading allowed accounts: {e}")
        return []

def _db_add_allowed_account(acc: str) -> bool:
    if not _supabase_client:
        return False
    try:
        accs = _db_get_allowed_accounts()
        clean_acc = "".join([c for c in acc if c.isdigit() or c.lower() in ("x", "*", "_")])
        if not clean_acc:
            return False
        if clean_acc in accs:
            return True
        accs.append(clean_acc)
        new_val = "|".join(accs)
        _supabase_client.table("bot_settings").upsert({"key": "allowed_accounts", "value": new_val}).execute()
        logger.info(f"Account {clean_acc} added to whitelist.")
        return True
    except Exception as e:
        logger.error(f"Error adding allowed account {acc}: {e}")
        return False

def _db_remove_allowed_account(acc: str) -> bool:
    if not _supabase_client:
        return False
    try:
        accs = _db_get_allowed_accounts()
        clean_acc = "".join([c for c in acc if c.isdigit() or c.lower() in ("x", "*", "_")])
        if clean_acc not in accs:
            return True
        accs.remove(clean_acc)
        new_val = "|".join(accs)
        _supabase_client.table("bot_settings").upsert({"key": "allowed_accounts", "value": new_val}).execute()
        logger.info(f"Account {clean_acc} removed from whitelist.")
        return True
    except Exception as e:
        logger.error(f"Error removing allowed account {acc}: {e}")
        return False

def _db_clear_allowed_accounts() -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_settings").upsert({"key": "allowed_accounts", "value": ""}).execute()
        logger.info("Cleared all allowed accounts.")
        return True
    except Exception as e:
        logger.error(f"Error clearing allowed accounts: {e}")
        return False


async def get_allowed_accounts() -> list[str]:
    return await asyncio.to_thread(_db_get_allowed_accounts)

async def add_allowed_account(acc: str) -> bool:
    return await asyncio.to_thread(_db_add_allowed_account, acc)

async def remove_allowed_account(acc: str) -> bool:
    return await asyncio.to_thread(_db_remove_allowed_account, acc)

async def clear_allowed_accounts() -> bool:
    return await asyncio.to_thread(_db_clear_allowed_accounts)
