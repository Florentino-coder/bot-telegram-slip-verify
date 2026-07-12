# 01_PROJECT_SPEC.md
This is a comprehensive implementation blueprint for the Telegram Slip Verification Bot.

## 1. Vision
- A secure, reliable, and asynchronous Telegram bot that automatically processes uploaded Thai bank transfer slips, extracts transaction data locally using QR decoding, utilizes OpenRouter Vision AI as an OCR fallback and semantic validation tool, and cross-checks data against a database to prevent duplicate slip usage (double-spending).

```python
# The system operates as a single asynchronous application pipeline.
# Module vision encapsulates the main execution context.
pass
```

## 2. Goals
- Automated detection of Thai QR Payment codes on uploaded bank slip images.
- Precise extraction of transfer details (Transaction Ref, Sender, Receiver, Amount, Date/Time) using OpenRouter vision models.
- Cross-validation between decoded QR code data and OCR-extracted text to prevent slip tampering (modifying amounts or receiver names while leaving the QR intact).
- Check against Supabase database for duplicate transaction references.
- Administrative alerts for suspicious or duplicate slips.

```python
# Goals definition for validation pipeline:
async def validate_goals(slip_data: dict) -> bool:
    # Ensure amount matches, reference is unique, and receiver is correct
    return True
```

## 3. Non-Goals
- Directly connecting to merchant bank accounts for transaction retrieval (we rely on the slip's QR/text validation).
- Processing slips from foreign banks (non-Thai).
- Automated customer refund processing.

```python
# Non-goals handler (silently ignore or send clean user errors)
pass
```

## 4. Architecture
- The bot is designed around a decoupled, event-driven, asynchronous architecture:
  1. **Telegram Client**: Receives photos from users via `aiogram`.
  2. **QR Decoder Service**: Decodes the "Mini QR" (PromptPay transfer QR) locally.
  3. **Vision AI Service**: Calls OpenRouter Vision API to extract text and details.
  4. **Risk Engine**: Runs cross-matching rules (Ref, Amount, Receiver, Date) and flags deviations.
  5. **Database Manager**: Connects to Supabase to verify transaction uniqueness and logs entries.

```python
# Architecture block
# Coordinates handlers, services, and db packages.
pass
```

## 5. Tech Stack
- **Language**: Python 3.11+
- **Bot Framework**: `aiogram` (v3)
- **Image Processing**: `Pillow` (PIL)
- **QR Decoding**: `pyzbar`
- **HTTP Client**: `httpx` (async)
- **Database**: Supabase Python Client (`supabase-py`)
- **Config**: `python-dotenv`

```python
# Tech stack dependencies verification
import aiogram
import pyzbar
import PIL
import httpx
import supabase
pass
```

## 6. Folder Structure
- Decoupled modules separating business logic, DB, services, and Telegram handlers:
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
# Folder structure definition loader
pass
```

## 7. Database Schema
- Supabase PostgreSQL schema for logging verified slips:
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
  ```

```python
# Database transaction model template
class TransactionModel:
    def __init__(self, trans_ref: str, sender_name: str, receiver_name: str, amount: float, trans_date: str, raw_ocr: dict):
        self.trans_ref = trans_ref
        self.sender_name = sender_name
        self.receiver_name = receiver_name
        self.amount = amount
        self.trans_date = trans_date
        self.raw_ocr = raw_ocr
```

## 8. Storage
- Slip images are processed completely in-memory. They are downloaded as byte streams from Telegram API, analyzed, and discarded.
- No local file storage is used for user images to ensure privacy and low disk footprint.

```python
# Memory-only image handling
import io
def load_image_bytes(image_bytes: bytes) -> io.BytesIO:
    return io.BytesIO(image_bytes)
```

## 9. Security
- API keys (Telegram, OpenRouter, Supabase) are stored in a `.env` file and loaded via `config.py`.
- Strict validation of the `Receiver Name` against the merchant's target receiver name (`MERCHANT_NAME`).
- Duplicate checks query the Supabase indexed column `trans_ref` before approving.

```python
# Security checks mapping
pass
```

## 10. Feature Flags
- `ENABLE_OCR_FALLBACK`: If True, attempts to verify slips using Vision AI even if the QR code is missing or unreadable.
- `STRICT_QR_MATCH`: If True, requires the QR reference and OCR reference to match perfectly.

```python
# Feature flag helper
class Features:
    ENABLE_OCR_FALLBACK: bool = True
    STRICT_QR_MATCH: bool = True
```

## 11. Risk Engine
- Validates the parsed details from QR and OCR:
  1. Checks if `trans_ref` exists in the database -> Duplicate Alert.
  2. Compares QR `trans_ref` with OCR `trans_ref` -> Mismatch Alert (indicates slip modification).
  3. Checks if `receiver_name` matches `MERCHANT_NAME` (fuzzy matching or substring checks).
  4. Checks if the transfer date is within acceptable bounds (e.g., within the last 3 days).

```python
# Risk engine validation pipeline
async def assess_risk(qr_ref: str, ocr_data: dict, merchant_name: str) -> dict:
    risk_score = 0
    warnings = []
    
    # 1. Receiver validation
    if merchant_name.lower() not in ocr_data.get("receiver_name", "").lower():
        risk_score += 50
        warnings.append("Receiver name mismatch")
        
    # 2. QR Ref validation
    if qr_ref and ocr_data.get("trans_ref") and qr_ref != ocr_data.get("trans_ref"):
        risk_score += 100
        warnings.append("QR reference and OCR reference mismatch")
        
    return {"risk_score": risk_score, "warnings": warnings, "is_safe": risk_score < 50}
```

## 12. OCR
- Utilizes Vision AI model through OpenRouter.
- Passes a high-accuracy system prompt to extract data structures from Thai bank slips and returns clean JSON formatting.

```python
# OCR helper skeleton
pass
```

## 13. QR
- Decodes QR codes using `pyzbar`.
- Parses the Thai QR Payment slip payload (Mini QR) to extract the transaction reference.
- Mini QR code payloads contain ID `00` (payload format indicator), `01` (point of initiation), and bank-specific reference identifiers under tag `30` (Thai QR code format specifications).

```python
# QR processing functions
pass
```

## 14. Vision AI
- Connects to OpenRouter's chat completions endpoint.
- Sends the image encoded as base64.
- Receives JSON response matching the required schema.

```python
# OpenRouter integration loader
pass
```

## 15. Duplicate
- Ensures unique transaction references to prevent double-spending of the same slip image.
- Uses `trans_ref` as the primary lookup index in the Supabase `transactions` table.

```python
# Duplicate validator interface
pass
```

## 16. Telegram UX
- Rich messages back to users:
  - **Success (Green Theme)**: Displays transaction details (Bank, Sender, Amount, Date).
  - **Duplicate Slip (Yellow Theme)**: Warns that this slip was already verified.
  - **Suspicious Slip (Red Theme)**: Displays alerts (Receiver mismatch, QR-OCR ref mismatch).
  - **Error (Gray Theme)**: Unreadable QR/slip or API failure.

```python
# UI format helpers
pass
```

## 17. Commands
- `/start`: Starts the bot and welcomes users.
- `/help`: Describes how to use the bot (send a slip photo).
- `/stats`: (Admin Only) Returns daily/weekly slip verification statistics.

```python
# Command definitions
pass
```

## 18. Config
- Load environment configs:
  - `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather.
  - `OPENROUTER_API_KEY`: API key for OpenRouter.
  - `OPENROUTER_MODEL`: Model name (default: `google/gemini-2.5-flash`).
  - `SUPABASE_URL` / `SUPABASE_KEY`: Supabase connection details.
  - `MERCHANT_NAME`: The legal or display name of the merchant receiver.
  - `ADMIN_USER_IDS`: Comma-separated list of admin telegram IDs.

```python
# Config interface
pass
```

## 19. Deployment
- Built for simple containerized deployment on Railway.
- Runs using python command or inside a minimal Dockerfile.

```python
# Deployment task
pass
```

## 20. Roadmap
- Phase 1: Local QR scanner and OpenRouter integration.
- Phase 2: Supabase database setup and duplicate prevention.
- Phase 3: Detailed admin notifications and dashboard configuration.

```python
# Roadmap execution checker
pass
```
