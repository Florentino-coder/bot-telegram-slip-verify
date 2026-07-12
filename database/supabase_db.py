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
