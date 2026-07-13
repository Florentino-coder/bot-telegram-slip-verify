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


async def extract_slip_details(image_bytes: bytes) -> dict | None:
    """
    Sends the image bytes to OpenRouter Vision API and extracts slip details as a dictionary.
    Returns a dictionary of parsed details or a dictionary containing an 'error' key on failure.
    """
    if not Config.OPENROUTER_API_KEY:
        logger.error("OpenRouter API key is missing.")
        return {"error": "API Key is missing", "error_code": "CONFIG_ERROR"}

    try:
        # Encode image to base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fluk3/bot-telegram-slip-verify",
            "X-Title": "Telegram Slip Verification Bot"
        }
        
        # Prepare request payload
        payload = {
            "model": Config.OPENROUTER_MODEL,
            "max_tokens": 1000, # Avoid 402 credit limit issues by asking for a small token allocation
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
        
        # Make async POST request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 429:
                logger.error("OpenRouter API rate limit exceeded.")
                return {"error": "OpenRouter API rate limit exceeded", "error_code": "RATE_LIMIT"}
            elif response.status_code != 200:
                logger.error(f"OpenRouter API returned error code {response.status_code}: {response.text}")
                return {"error": f"OpenRouter API error {response.status_code}", "error_code": f"HTTP_{response.status_code}"}
                
            response_data = response.json()
            choices = response_data.get("choices", [])
            if not choices:
                logger.error("OpenRouter API response did not contain any choices.")
                return {"error": "Empty choices in response", "error_code": "EMPTY_CHOICES"}
                
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.error("OpenRouter API response content is empty.")
                return {"error": "Empty message content", "error_code": "EMPTY_CONTENT"}
                
            # Parse response content as JSON
            try:
                # Clean content block if markdown formatted (like ```json ... ```)
                cleaned_content = content.strip()
                if cleaned_content.startswith("```"):
                    lines = cleaned_content.splitlines()
                    # Remove the first line (```json) and the last line (```)
                    cleaned_content = "\n".join(lines[1:-1])
                    
                data = json.loads(cleaned_content)
                logger.info(f"Successfully extracted slip data via OpenRouter: {data}")
                
                # Normalize values
                if data.get("amount") is not None:
                    try:
                        # Convert amount to float (if it is a string representation)
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
                logger.error(f"Failed to parse content as JSON. Raw content: {content}. Error: {je}")
                return {"error": f"Failed to parse JSON response: {je}", "error_code": "INVALID_JSON"}
                
    except httpx.TimeoutException:
        logger.error("OpenRouter Vision API request timed out.")
        return {"error": "Request timed out", "error_code": "TIMEOUT"}
    except Exception as e:
        logger.error(f"Exception during OpenRouter vision request: {e}")
        return {"error": str(e), "error_code": "API_ERROR"}
