import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Gemini Direct API Configuration (Free tier from Google AI Studio)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    ENABLE_GEMINI_DIRECT: bool = os.getenv("ENABLE_GEMINI_DIRECT", "False").lower() == "true"
    
    # Groq Vision API Configuration (Free tier 100% - https://console.groq.com/)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.2-11b-vision-preview")
    
    # OpenRouter Configuration (Fallback)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash")
    # Keep the requested completion within the remaining key/workspace budget.
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "800"))
    
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
    AI_CONFIDENCE_THRESHOLD: float = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.85"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validates that all required configurations are present. Returns a list of missing config names."""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.GEMINI_API_KEY and not cls.GROQ_API_KEY and not cls.OPENROUTER_API_KEY:
            missing.append("GEMINI_API_KEY or GROQ_API_KEY or OPENROUTER_API_KEY")
        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")
        if not cls.MERCHANT_NAME:
            missing.append("MERCHANT_NAME")
        return missing
