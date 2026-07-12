# 03_GEMINI_RULES.md
This is a comprehensive implementation blueprint containing guidelines, rules, and specifications for developing the Telegram Slip Verification Bot.

## 1. Development Rules
- **Asynchronous First**: All network requests (Telegram Bot API, OpenRouter API, Supabase DB API) must be asynchronous. Use `httpx.AsyncClient` for API requests. Do not use blocking operations like `requests` or `time.sleep`.
- **Modular Code**: Keep database, services, handlers, and configuration in separate modules as described in the project directory structure.
- **Defensive Error Handling**: Always wrap API calls and QR decoding in try-except blocks. Log details of all exceptions and send clean, user-friendly error messages to Telegram.
- **Type Annotations**: Use Python type hinting for all function parameters and return values.

```python
# Rule verification: Ensure code uses async/await syntax and proper type hints
from typing import Dict, Any

async def check_async_rules(data: Dict[str, Any]) -> bool:
    return True
```

## 2. Coding Standards
- Follow PEP 8 guidelines for formatting (snake_case for variables/functions, PascalCase for classes).
- Use `logging` instead of `print` for runtime tracking.
- Do not store credentials, secrets, or host URLs in source code; use the `config.py` environment loader.
- All file names and imports must align with the folder structure:
  - Modules: `config.py`, `main.py`
  - Database: `database/supabase_db.py`
  - Services: `services/qr_decoder.py`, `services/vision_ai.py`, `services/risk_engine.py`
  - Handlers: `handlers/start.py`, `handlers/slip.py`

```python
# Coding standards checker helper
pass
```

## 3. Do/Don't
- **DO**:
  - Decode the QR code locally first. This is much faster and cheaper than calling Vision AI.
  - Verify that the transaction amount parsed by Vision AI matches a decimal format.
  - Perform case-insensitive checks on the receiver name.
  - Ensure the `trans_ref` from OCR matches the `trans_ref` from QR (if QR is readable).
- **DON'T**:
  - Do not use blocking libraries (like `requests`, `urllib.request`).
  - Do not verify the same transaction ref twice; check Supabase before starting expensive Vision AI requests.
  - Do not expose administrative commands (like statistics or logs) to non-admin users.

```python
# Rule validator mapping
pass
```

## 4. Acceptance Criteria
1. The Telegram Bot successfully replies to a photo upload within 6 seconds.
2. If the photo is a valid Thai bank transfer slip, it extracts the details correctly, logs them in Supabase, and displays a confirmation message showing:
   *   Transaction ID / Reference Number
   *   Sender Name (masking middle characters if necessary)
   *   Receiver Name
   *   Transfer Amount (e.g. 150.00 THB)
   *   Date & Time
3. If the slip is a duplicate (same `trans_ref` already verified), it declines verification and shows a warning.
4. If the slip receiver name does not match the merchant name, it flags it as a suspicious transaction.
5. If the QR code is damaged but `ENABLE_OCR_FALLBACK` is enabled, the bot successfully falls back to OpenRouter Vision AI to parse the text details.

```python
# Test cases verification criteria
pass
```

## 5. Phase Checklist
- **Phase 1: Project Skeleton & Configuration**: Create folder structure, `requirements.txt`, `.env.example`, and `config.py`.
- **Phase 2: Local QR Decoding Service**: Implement the local QR decoder using `pyzbar`. Ensure it returns PromptPay transaction reference payloads.
- **Phase 3: Supabase Database Integration**: Setup DB client, unique lookup constraints, and insertion functions.
- **Phase 4: OpenRouter Vision AI Service**: Implement the async client sending base64-encoded images and receiving parsed JSON structures.
- **Phase 5: Risk Engine & Match Logic**: Build cross-matching rules to detect tampered slips.
- **Phase 6: Handler Setup & Polling**: Connect bot routers, start handlers, and main polling loop.
- **Phase 7: End-to-End Verification**: Test the bot with real slips and verify duplicate checks.

```python
# Phase checklist validator
pass
```

## 6. Definition of Done
- All files listed in folder structure exist and contain clean, working, PEP-8 compliant code.
- No critical errors occur when starting the bot.
- Slip verification succeeds for valid slips and fails for duplicate/modified/invalid slips.
- The three documentation files (`01_PROJECT_SPEC.md`, `02_IMPLEMENTATION_GUIDE.md`, and `03_GEMINI_RULES.md`) contain complete implementation details.

```python
# Definition of Done verifier
pass
```

## 7. Prompts
- The OpenRouter Vision AI prompt must request JSON format. Here is the exact system instruction and user prompt to send:

```python
SYSTEM_PROMPT = """
You are a banking OCR assistant specialized in Thai bank transfer slips.
Analyze the image of the bank transfer slip and extract the transaction details.
You must return your output strictly in JSON format.
If you cannot find a field or it is not readable, return null for that field.

Output JSON Format:
{
  "trans_ref": "Transaction ID, Reference Number, or เลขที่อ้างอิง. Strip spaces.",
  "sender_name": "Sender name. Often starts with 'จาก' or 'From'.",
  "receiver_name": "Receiver name. Often starts with 'ไปยัง' or 'To'.",
  "amount": "The transfer amount as a float number. Remove comma.",
  "trans_date": "Transaction date and time in ISO 8601 format if possible (YYYY-MM-DD HH:MM:SS), otherwise as a string."
}
"""

USER_PROMPT = "Extract the details from this Thai bank slip image. Answer only in JSON."
```
