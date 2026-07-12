import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    MERCHANT_NAME: str = os.getenv("MERCHANT_NAME", "")
    
    # Parse admin user IDs (comma-separated string to list of ints)
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    ADMIN_USER_IDS: list[int] = [
        int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip().isdigit()
    ]
    
    # Feature flags
    ENABLE_OCR_FALLBACK: bool = os.getenv("ENABLE_OCR_FALLBACK", "True").lower() == "true"
    STRICT_QR_MATCH: bool = os.getenv("STRICT_QR_MATCH", "True").lower() == "true"

    @classmethod
    def validate(cls) -> list[str]:
        """Validates that all required configurations are present. Returns a list of missing config names."""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.OPENROUTER_API_KEY:
            missing.append("OPENROUTER_API_KEY")
        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")
        if not cls.MERCHANT_NAME:
            missing.append("MERCHANT_NAME")
        return missing
