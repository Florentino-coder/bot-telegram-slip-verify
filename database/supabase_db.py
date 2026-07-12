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
