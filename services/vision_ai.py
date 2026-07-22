import base64
import json
import logging
import httpx
from config import Config

logger = logging.getLogger("SlipBot.VisionAI")

SYSTEM_PROMPT = """
You are a banking OCR assistant specialized in Thai bank transfer slips.
Analyze the image of the bank transfer slip and extract the transaction details.
You must return your output strictly in JSON format.
If you cannot find a field or it is not readable, return null for that field.

Output JSON Format:
{
  "trans_ref": "Transaction ID, Reference Number, or เลขที่อ้างอิง. Strip all spaces.",
  "sender_name": "Sender name. Often starts with 'จาก' or 'From'.",
  "sender_account": "Sender account number or PromptPay number as printed on the slip (e.g., xxx-x-x5678-x or 06x-xxx-5890). Null if not found.",
  "receiver_name": "Receiver name. Often starts with 'ไปยัง' or 'To'.",
  "receiver_account": "Receiver account number as printed on the slip (e.g., xxx-x-x1234-x or x-1234 or a phone number for PromptPay). Null if not found.",
  "amount": "The transfer amount as a float number. Remove any comma.",
  "trans_date": "Transaction date and time in ISO 8601 format if possible (YYYY-MM-DD HH:MM:SS), otherwise as a string.",
  "amount_confidence": "A float between 0.0 and 1.0 representing your confidence in the amount field.",
  "receiver_confidence": "A float between 0.0 and 1.0 representing your confidence in the receiver_name field.",
  "reference_confidence": "A float between 0.0 and 1.0 representing your confidence in the trans_ref field."
}
"""

USER_PROMPT = "Extract the details from this Thai bank slip image. Answer only in JSON."


def _parse_and_normalize_json(content: str, provider_name: str) -> dict | None:
    """Helper to clean and parse JSON response from LLM providers."""
    try:
        cleaned_content = content.strip()
        if cleaned_content.startswith("```"):
            lines = cleaned_content.splitlines()
            cleaned_content = "\n".join(lines[1:-1])
            
        data = json.loads(cleaned_content)
        logger.info(f"Successfully extracted slip data via {provider_name}: {data}")
        
        # Normalize values
        if data.get("amount") is not None:
            try:
                data["amount"] = float(str(data["amount"]).replace(",", ""))
            except ValueError:
                data["amount"] = None
        
        # Normalize confidence scores
        for field in ["amount_confidence", "receiver_confidence", "reference_confidence"]:
            val = data.get(field)
            try:
                data[field] = float(val) if val is not None else 1.0
            except (ValueError, TypeError):
                data[field] = 1.0
                
        return data
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse {provider_name} content as JSON. Raw content: {content}. Error: {je}")
        return {"error": f"Failed to parse JSON response: {je}", "error_code": "INVALID_JSON"}


async def _call_gemini_direct(image_bytes: bytes) -> dict | None:
    """
    Primary Provider: Calls Google AI Studio Direct API (Free Tier: 15 RPM / 1500 RPD).
    Includes automatic fallback list of model identifiers to handle API version/regional naming differences.
    """
    if not Config.GEMINI_API_KEY:
        return None

    user_model = Config.GEMINI_MODEL or "gemini-2.5-flash"
    # List of candidate models to try in order
    candidate_models = [user_model, "gemini-2.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]
    # Preserve unique order
    models_to_try = []
    for m in candidate_models:
        if m not in models_to_try:
            models_to_try.append(m)

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    headers = {"Content-Type": "application/json"}

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [
                    {"text": USER_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    last_error = None
    async with httpx.AsyncClient(timeout=25.0) as client:
        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={Config.GEMINI_API_KEY}"
            try:
                logger.info(f"Calling Google AI Studio Direct API ({model_name})...")
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    res_json = response.json()
                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        logger.warning(f"Gemini Direct API ({model_name}) response empty candidates.")
                        last_error = {"error": "Empty candidates", "error_code": "EMPTY_CANDIDATES"}
                        continue

                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if not text:
                        logger.warning(f"Gemini Direct API ({model_name}) empty response text.")
                        last_error = {"error": "Empty text response", "error_code": "EMPTY_TEXT"}
                        continue

                    return _parse_and_normalize_json(text, f"Google AI Studio Direct ({model_name})")
                else:
                    logger.warning(f"Gemini Direct API ({model_name}) returned HTTP status {response.status_code}: {response.text}")
                    last_error = {"error": f"Gemini Direct error {response.status_code}", "error_code": f"HTTP_{response.status_code}"}
                    # If 404 or 429, try next model in loop
                    if response.status_code in (404, 429):
                        continue
                    else:
                        break
            except Exception as e:
                logger.warning(f"Exception during Gemini Direct API call ({model_name}): {e}")
                last_error = {"error": str(e), "error_code": "API_ERROR"}

    return last_error


async def _call_openrouter(image_bytes: bytes) -> dict | None:
    """
    Fallback Provider: Calls OpenRouter API.
    """
    if not Config.OPENROUTER_API_KEY:
        return None

    try:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        model_name = Config.OPENROUTER_MODEL or "google/gemini-2.0-flash"
        
        headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fluk3/bot-telegram-slip-verify",
            "X-Title": "Telegram Slip Verification Bot"
        }
        
        payload = {
            "model": model_name,
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": USER_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        }
        
        logger.info(f"Calling OpenRouter Fallback API ({model_name})...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"OpenRouter API returned status {response.status_code}: {response.text}")
                return {"error": f"OpenRouter API error {response.status_code}", "error_code": f"HTTP_{response.status_code}"}
                
            response_data = response.json()
            choices = response_data.get("choices", [])
            if not choices:
                return {"error": "Empty choices", "error_code": "EMPTY_CHOICES"}
                
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return {"error": "Empty content", "error_code": "EMPTY_CONTENT"}
                
            return _parse_and_normalize_json(content, "OpenRouter")
            
    except Exception as e:
        logger.error(f"Exception during OpenRouter API call: {e}")
        return {"error": str(e), "error_code": "API_ERROR"}


async def extract_slip_details(image_bytes: bytes) -> dict | None:
    """
    Dual-Provider Vision AI Extraction:
    1. Try Google AI Studio Direct API first (Free 100%)
    2. Fallback to OpenRouter if Gemini Direct key is missing or fails
    """
    # 1. Primary: Gemini Direct API (Free)
    if Config.GEMINI_API_KEY:
        direct_result = await _call_gemini_direct(image_bytes)
        if direct_result and "error" not in direct_result:
            return direct_result
        else:
            logger.warning(f"Gemini Direct API failed or returned error: {direct_result}. Trying OpenRouter fallback...")

    # 2. Fallback: OpenRouter API
    if Config.OPENROUTER_API_KEY:
        openrouter_result = await _call_openrouter(image_bytes)
        if openrouter_result and "error" not in openrouter_result:
            return openrouter_result
        else:
            logger.error(f"OpenRouter fallback also failed: {openrouter_result}")
            return openrouter_result

    logger.error("No Vision AI provider succeeded (both Gemini Direct and OpenRouter unavailable).")
    return {"error": "All Vision AI providers failed", "error_code": "ALL_PROVIDERS_FAILED"}

