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
  "trans_date": "Transaction date and time in ISO 8601 format if possible (YYYY-MM-DD HH:MM:SS), otherwise as a string."
}
"""

USER_PROMPT = "Extract the details from this Thai bank slip image. Answer only in JSON."


async def extract_slip_details(image_bytes: bytes) -> dict | None:
    """
    Sends the image bytes to OpenRouter Vision API and extracts slip details as a dictionary.
    """
    if not Config.OPENROUTER_API_KEY:
        logger.error("OpenRouter API key is missing.")
        return None

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
            
            if response.status_code != 200:
                logger.error(f"OpenRouter API returned error code {response.status_code}: {response.text}")
                return None
                
            response_data = response.json()
            choices = response_data.get("choices", [])
            if not choices:
                logger.error("OpenRouter API response did not contain any choices.")
                return None
                
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.error("OpenRouter API response content is empty.")
                return None
                
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
                        
                return data
            except json.JSONDecodeError as je:
                logger.error(f"Failed to parse content as JSON. Raw content: {content}. Error: {je}")
                return None
                
    except Exception as e:
        logger.error(f"Exception during OpenRouter vision request: {e}")
        return None
