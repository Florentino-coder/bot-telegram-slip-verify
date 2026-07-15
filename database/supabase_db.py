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


# --- Multiple SlipOK Credentials Management ---

def _db_get_slipok_credentials() -> list[dict]:
    if not _supabase_client:
        return []
    try:
        response = _supabase_client.table("bot_settings").select("value").eq("key", "slipok_credentials").execute()
        if response.data and response.data[0].get("value"):
            import json
            try:
                return json.loads(response.data[0].get("value"))
            except Exception:
                pass
        
        # Fallback to single legacy credentials if available
        legacy_key_resp = _supabase_client.table("bot_settings").select("value").eq("key", "slipok_api_key").execute()
        legacy_branch_resp = _supabase_client.table("bot_settings").select("value").eq("key", "slipok_branch_id").execute()
        
        legacy_key = legacy_key_resp.data[0].get("value") if legacy_key_resp.data else None
        legacy_branch = legacy_branch_resp.data[0].get("value") if legacy_branch_resp.data else None
        
        if legacy_key and legacy_branch:
            initial_creds = [{"api_key": legacy_key, "branch_id": legacy_branch, "status": "active"}]
            import json
            _supabase_client.table("bot_settings").upsert({"key": "slipok_credentials", "value": json.dumps(initial_creds)}).execute()
            return initial_creds
            
        return []
    except Exception as e:
        logger.error(f"Error reading slipok credentials: {e}")
        return []

def _db_add_slipok_credential(api_key: str, branch_id: str) -> bool:
    if not _supabase_client:
        return False
    try:
        creds = _db_get_slipok_credentials()
        for c in creds:
            if c.get("api_key") == api_key:
                c["branch_id"] = branch_id
                c["status"] = "active"
                break
        else:
            creds.append({"api_key": api_key, "branch_id": branch_id, "status": "active"})
            
        import json
        _supabase_client.table("bot_settings").upsert({"key": "slipok_credentials", "value": json.dumps(creds)}).execute()
        logger.info(f"SlipOK credential added/updated for key: {api_key[:10]}...")
        return True
    except Exception as e:
        logger.error(f"Error adding slipok credential: {e}")
        return False

def _db_remove_slipok_credential(index: int) -> bool:
    if not _supabase_client:
        return False
    try:
        creds = _db_get_slipok_credentials()
        if 0 <= index < len(creds):
            creds.pop(index)
            import json
            _supabase_client.table("bot_settings").upsert({"key": "slipok_credentials", "value": json.dumps(creds)}).execute()
            logger.info(f"SlipOK credential at index {index} removed.")
            return True
        return False
    except Exception as e:
        logger.error(f"Error removing slipok credential: {e}")
        return False

def _db_update_slipok_credential_status(api_key: str, status: str) -> bool:
    if not _supabase_client:
        return False
    try:
        creds = _db_get_slipok_credentials()
        updated = False
        for c in creds:
            if c.get("api_key") == api_key:
                c["status"] = status
                updated = True
                break
        if updated:
            import json
            _supabase_client.table("bot_settings").upsert({"key": "slipok_credentials", "value": json.dumps(creds)}).execute()
            logger.info(f"Updated status of SlipOK key {api_key[:10]}... to {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating slipok credential status: {e}")
        return False

def _db_reset_all_slipok_credentials() -> bool:
    if not _supabase_client:
        return False
    try:
        creds = _db_get_slipok_credentials()
        for c in creds:
            c["status"] = "active"
        import json
        _supabase_client.table("bot_settings").upsert({"key": "slipok_credentials", "value": json.dumps(creds)}).execute()
        logger.info("Reset all SlipOK credentials to active status.")
        return True
    except Exception as e:
        logger.error(f"Error resetting all slipok credentials: {e}")
        return False


async def get_slipok_credentials() -> list[dict]:
    return await asyncio.to_thread(_db_get_slipok_credentials)

async def add_slipok_credential(api_key: str, branch_id: str) -> bool:
    return await asyncio.to_thread(_db_add_slipok_credential, api_key, branch_id)

async def remove_slipok_credential(index: int) -> bool:
    return await asyncio.to_thread(_db_remove_slipok_credential, index)

async def update_slipok_credential_status(api_key: str, status: str) -> bool:
    return await asyncio.to_thread(_db_update_slipok_credential_status, api_key, status)

async def reset_all_slipok_credentials() -> bool:
    return await asyncio.to_thread(_db_reset_all_slipok_credentials)


def _db_log_slip_log(log_data: dict) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("slip_logs").insert(log_data).execute()
        logger.info(f"Slip log saved successfully: {log_data.get('slip_id')}")
        return True
    except Exception as e:
        logger.error(f"Error logging slip: {e}")
        return False

def _db_get_slip_log(slip_id: str) -> dict | None:
    if not _supabase_client:
        return None
    try:
        response = _supabase_client.table("slip_logs").select("*").eq("slip_id", slip_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting slip log {slip_id}: {e}")
        return None

def _db_check_duplicate_image_hash(image_hash: str) -> bool:
    if not _supabase_client:
        return False
    try:
        # Check if hash exists in slip_logs where status is PASS
        response = _supabase_client.table("slip_logs").select("slip_id").eq("image_hash", image_hash).eq("status", "PASS").execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking duplicate image hash: {e}")
        return False


async def log_slip_log(log_data: dict) -> bool:
    return await asyncio.to_thread(_db_log_slip_log, log_data)

async def get_slip_log(slip_id: str) -> dict | None:
    return await asyncio.to_thread(_db_get_slip_log, slip_id)

async def check_duplicate_image_hash(image_hash: str) -> bool:
    return await asyncio.to_thread(_db_check_duplicate_image_hash, image_hash)


def _db_get_bot_admins() -> list[dict]:
    if not _supabase_client:
        return []
    try:
        response = _supabase_client.table("bot_admins").select("*").order("created_at").execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching bot admins: {e}")
        return []

def _db_get_bot_admin(user_id: int) -> dict | None:
    if not _supabase_client:
        return None
    try:
        response = _supabase_client.table("bot_admins").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching bot admin {user_id}: {e}")
        return None

def _db_add_bot_admin(user_id: int, username: str | None, role: str, permissions: list[str]) -> bool:
    if not _supabase_client:
        return False
    try:
        data = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "permissions": permissions
        }
        _supabase_client.table("bot_admins").upsert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Error adding/updating bot admin {user_id}: {e}")
        return False

def _db_remove_bot_admin(user_id: int) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("bot_admins").delete().eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error removing bot admin {user_id}: {e}")
        return False


async def get_bot_admins() -> list[dict]:
    return await asyncio.to_thread(_db_get_bot_admins)

async def get_bot_admin(user_id: int) -> dict | None:
    return await asyncio.to_thread(_db_get_bot_admin, user_id)

async def add_bot_admin(user_id: int, username: str | None, role: str, permissions: list[str]) -> bool:
    return await asyncio.to_thread(_db_add_bot_admin, user_id, username, role, permissions)

async def remove_bot_admin(user_id: int) -> bool:
    return await asyncio.to_thread(_db_remove_bot_admin, user_id)

async def check_admin_permission(user_id: int, required_permission: str | None = None) -> bool:
    """
    Checks if a user has admin access.
    - If user_id is in Config.ADMIN_USER_IDS, returns True (Super Admin).
    - Checks bot_admins table:
      - If user role is 'super_admin', returns True.
      - If user role is 'co_admin' and required_permission is in permissions list, returns True.
      - If required_permission is None, returns True (since they are at least a co_admin).
    """
    if user_id in Config.ADMIN_USER_IDS:
        return True
        
    admin = await get_bot_admin(user_id)
    if not admin:
        return False
        
    if admin.get("role") == "super_admin":
        return True
        
    # If it is co_admin
    if required_permission is None:
        return True
        
    user_perms = admin.get("permissions") or []
    if required_permission in user_perms:
        return True
        
    return False


def _db_count_sender_today(sender_name: str | None, sender_account: str | None) -> tuple[int, list[dict]]:
    """
    Synchronously queries the database to count transaction slips uploaded today (Thai Time)
    that match either the sender account (matching last 4 digits) or the fuzzy sender name.
    
    Returns:
        (match_count, list_of_matched_transactions_today)
    """
    if not _supabase_client:
        logger.error("Supabase client not initialized.")
        return 0, []
        
    from datetime import datetime, timezone, timedelta
    from services.risk_engine import clean_thai_name
    
    tz_th = timezone(timedelta(hours=7))
    now_th = datetime.now(tz_th)
    # Start of today in Bangkok time (00:00:00)
    today_start_th = now_th.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_th.astimezone(timezone.utc).isoformat()
    
    try:
        # Fetch all transactions from today
        response = _supabase_client.table("transactions")\
            .select("trans_ref, sender_name, amount, trans_date, raw_ocr, created_at")\
            .gte("created_at", today_start_utc)\
            .execute()
            
        today_txs = response.data or []
        matched_txs = []
        
        # Prepare helper for checking last 4 digits of sender account
        def get_last_4_digits(acc_str: str | None) -> str | None:
            if not acc_str:
                return None
            digits = "".join([c for c in str(acc_str) if c.isdigit()])
            return digits[-4:] if len(digits) >= 4 else None

        target_acc_last4 = get_last_4_digits(sender_account)
        target_name_clean = clean_thai_name(sender_name) if sender_name else ""
        # Require name length after cleaning to be at least 4 characters to avoid false positive name matches
        is_name_valid_for_match = len(target_name_clean) >= 4
        
        for tx in today_txs:
            # Check sender_account from stored raw_ocr JSONB
            raw_ocr = tx.get("raw_ocr") or {}
            tx_sender_account = raw_ocr.get("sender_account")
            tx_acc_last4 = get_last_4_digits(tx_sender_account)
            
            # Match 1: Match by account last 4 digits (highly reliable)
            if target_acc_last4 and tx_acc_last4 and target_acc_last4 == tx_acc_last4:
                matched_txs.append(tx)
                continue
                
            # Match 2: Fallback to match by clean name substring matching
            tx_sender_name = tx.get("sender_name")
            tx_name_clean = clean_thai_name(tx_sender_name) if tx_sender_name else ""
            
            if is_name_valid_for_match and len(tx_name_clean) >= 4:
                if (target_name_clean in tx_name_clean) or (tx_name_clean in target_name_clean):
                    matched_txs.append(tx)
                    continue
                    
        # Sort matched transactions by creation time ascending
        matched_txs.sort(key=lambda x: x.get("created_at") or "")
        
        return len(matched_txs), matched_txs
    except Exception as e:
        logger.error(f"Error counting sender today (name={sender_name}, acc={sender_account}): {e}")
        return 0, []


async def count_sender_today(sender_name: str | None, sender_account: str | None) -> tuple[int, list[dict]]:
    """Asynchronously counts and returns matching transaction history for today."""
    return await asyncio.to_thread(_db_count_sender_today, sender_name, sender_account)


def _db_get_group_config(group_id: int) -> dict | None:
    if not _supabase_client:
        return None
    try:
        response = _supabase_client.table("allowed_groups")\
            .select("group_id, group_name, merchant_name, slipok_mode, allowed_accounts, min_limit, max_limit, slipok_min_amount")\
            .eq("group_id", group_id)\
            .execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting group config for {group_id}: {e}")
        return None


def _db_update_group_config(group_id: int, updates: dict) -> bool:
    if not _supabase_client:
        return False
    try:
        _supabase_client.table("allowed_groups").update(updates).eq("group_id", group_id).execute()
        logger.info(f"Group config updated for {group_id}: {updates}")
        return True
    except Exception as e:
        logger.error(f"Error updating group config for {group_id} with {updates}: {e}")
        return False


async def get_group_config(group_id: int) -> dict | None:
    """Asynchronously fetches the configuration for a given group ID."""
    return await asyncio.to_thread(_db_get_group_config, group_id)


async def update_group_config(group_id: int, merchant_name: str | None = None, slipok_mode: str | None = None, 
                              allowed_accounts: str | None = None, min_limit: float | str | None = None, 
                              max_limit: float | str | None = None, slipok_min_amount: float | str | None = None) -> bool:
    """Asynchronously updates the configuration parameters for a group."""
    updates = {}
    if merchant_name is not None:
        updates["merchant_name"] = merchant_name if merchant_name != "default" else None
    if slipok_mode is not None:
        updates["slipok_mode"] = slipok_mode if slipok_mode != "default" else None
    if allowed_accounts is not None:
        updates["allowed_accounts"] = allowed_accounts if allowed_accounts != "default" else None
    
    if min_limit is not None:
        updates["min_limit"] = float(min_limit) if str(min_limit).lower() != "default" else None
    if max_limit is not None:
        updates["max_limit"] = float(max_limit) if str(max_limit).lower() != "default" else None
    if slipok_min_amount is not None:
        updates["slipok_min_amount"] = float(slipok_min_amount) if str(slipok_min_amount).lower() != "default" else None
        
    if not updates:
        return True
        
    return await asyncio.to_thread(_db_update_group_config, group_id, updates)



