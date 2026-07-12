# 02_IMPLEMENTATION_GUIDE.md
This is a comprehensive implementation blueprint for the Telegram Slip Verification Bot.

## 1. Environment
- Setup a virtual environment:
  ```bash
  python -m venv venv
  .\venv\Scripts\activate  # Windows
  source venv/bin/activate  # Linux/macOS
  ```
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- **Windows ZBar dependency**: The `pyzbar` library includes precompiled zbar DLLs for Windows. No manual installation of zbar is required.
- **Linux ZBar dependency**: If deploying on Linux/Docker, run:
  ```bash
  sudo apt-get update && sudo apt-get install -y libzbar0
  ```

```python
# Environment verification script
import sys
import platform

print(f"Python Version: {sys.version}")
print(f"Platform: {platform.system()}")
try:
    from PIL import Image
    import pyzbar.pyzbar as pyzbar
    print("Pillow and pyzbar are installed successfully.")
except ImportError as e:
    print(f"Dependency error: {e}")
```

## 2. Railway Setup
- Install the Railway CLI or use the Railway Web UI.
- Create a new project on Railway.
- Connect your GitHub repository.
- Add the environment variables to the project configuration (see `.env.example`).
- Set the start command in your `Procfile` or Railway configuration:
  ```
  web: python main.py
  ```

```python
# Railway health check endpoint (if using web hooks or HTTP server)
# Since we use polling for simplicity, a web server is not strictly required.
pass
```

## 3. Supabase Setup
- Create a new project in Supabase.
- Open the SQL Editor and run the following script to create the `transactions` table:
  ```sql
  CREATE TABLE transactions (
      id BIGSERIAL PRIMARY KEY,
      trans_ref VARCHAR(255) UNIQUE NOT NULL,
      sender_name VARCHAR(255),
      receiver_name VARCHAR(255),
      amount NUMERIC(10, 2) NOT NULL,
      trans_date TIMESTAMP WITH TIME ZONE,
      raw_ocr JSONB,
      is_valid BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
  );

  -- Create an index on trans_ref for O(1) duplicate checks
  CREATE INDEX idx_transactions_trans_ref ON transactions(trans_ref);
  ```
- Retrieve your **Supabase URL** and **Anon Key** from Project Settings -> API.

```python
# SQL Schema check helper
pass
```

## 4. BotFather
- Open Telegram and search for `@BotFather`.
- Use the `/newbot` command to create a new bot. Keep the generated HTTP API Token safe.
- Set the bot description and profile picture.
- Add commands to the menu using `/setcommands`:
  ```
  start - Start the bot and get instructions
  help - How to verify slips
  stats - View transaction statistics (Admin only)
  ```

```python
# Telegram bot connection health check
pass
```

## 5. OpenRouter
- Sign up at [OpenRouter](https://openrouter.ai/).
- Create an API key.
- Recommended models:
  - `google/gemini-2.5-flash` (Fast, cheap, excellent multi-lingual/Thai support, multimodal vision)
  - `meta-llama/llama-3.2-11b-vision-instruct` (Fast and cost-efficient)
- API endpoint: `https://openrouter.ai/api/v1/chat/completions`

```python
# OpenRouter Request Header Template
headers = {
    "Authorization": "Bearer YOUR_OPENROUTER_API_KEY",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/fluk3/bot-telegram-slip-verify",
    "X-Title": "Telegram Slip Verification Bot"
}
```

## 6. Requirements
- File: `requirements.txt`
  ```
  aiogram>=3.0.0
  pyzbar>=0.1.9
  pillow>=10.0.0
  httpx>=0.24.0
  supabase>=2.0.0
  python-dotenv>=1.0.0
  ```

```python
# Automated requirement validator
pass
```

## 7. Project Tree
- The complete source code layout:
  ```
  bot-telegram-slip-verify/
  ├── database/
  │   ├── __init__.py
  │   └── supabase_db.py
  ├── services/
  │   ├── __init__.py
  │   ├── qr_decoder.py
  │   ├── vision_ai.py
  │   └── risk_engine.py
  ├── handlers/
  │   ├── __init__.py
  │   ├── start.py
  │   └── slip.py
  ├── config.py
  ├── main.py
  ├── requirements.txt
  └── .env.example
  ```

```python
# Project directories generator
import os

def create_structure():
    dirs = ['database', 'services', 'handlers']
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '__init__.py'), 'w') as f:
            pass
```

## 8. Module by Module
- **config.py**: Loads environment variables from `.env`.
- **database/supabase_db.py**: Connects to Supabase, checks for duplicate `trans_ref`, and inserts new verified transactions.
- **services/qr_decoder.py**: Reads PromptPay slip QR codes using `pyzbar` to extract payload data.
- **services/vision_ai.py**: Encodes image to base64, sends it to OpenRouter Vision API, and parses structured text details (JSON format).
- **services/risk_engine.py**: Compares OCR text data against QR payload reference, checks merchant name, validates date and amount.
- **handlers/start.py**: Welcomes users and outputs help text.
- **handlers/slip.py**: Processes uploaded images, coordinates QR, Vision AI, DB, and Risk Engine, then formats replies.

```python
# Module by Module placeholder code definitions
pass
```

## 9. Sample Code Layout
- Shows how the components link together inside `handlers/slip.py`:

```python
# Conceptual interaction inside slip.py handler
async def handle_slip_image(photo_bytes: bytes, merchant_name: str, supabase_client) -> str:
    # 1. Decode QR code locally
    qr_payload = decode_qr(photo_bytes)
    qr_ref = parse_qr_ref(qr_payload) if qr_payload else None
    
    # 2. Extract OCR data via OpenRouter
    ocr_data = await extract_slip_ocr(photo_bytes)
    
    # 3. Check for duplicates in DB
    if qr_ref and check_duplicate(supabase_client, qr_ref):
         return "❌ Duplicate transaction detected!"
         
    if ocr_data.get("trans_ref") and check_duplicate(supabase_client, ocr_data["trans_ref"]):
         return "❌ Duplicate transaction detected!"
         
    # 4. Assess risk
    risk = await assess_risk(qr_ref, ocr_data, merchant_name)
    if not risk["is_safe"]:
         return f"⚠️ Suspicious slip detected: {', '.join(risk['warnings'])}"
         
    # 5. Log and approve
    log_transaction(supabase_client, ocr_data)
    return "✅ Slip verified successfully!"
```

## 10. Testing
- Create testing scripts under the main folder.
- Run offline tests using mock slip images.

```python
# Test suite executor placeholder
pass
```

## 11. Logging
- Configured using python's built-in `logging` module.
- Logs events to standard output (useful for Railway logs) and writes errors/warnings to `bot.log`.

```python
# Logging configuration block
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("SlipBot")
```

## 12. Backup
- Supabase automatically manages database backups on the Pro tier. For Free tier, you can set up a daily GitHub Action using pg_dump to backup the schema and transactions.

```python
# Backup script interface
pass
```

## 13. Troubleshooting
- **Error: `zbar shared library not found` (Linux/Docker)**: Ensure `libzbar0` is installed via `apt-get`.
- **Error: `supabase.client.APIError`**: Ensure your `SUPABASE_URL` and `SUPABASE_KEY` are correct.
- **Error: `OpenRouter returns 400 Mismatching Models`**: Verify the model name in your `.env` (e.g. `google/gemini-2.5-flash`).
