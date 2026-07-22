import logging
import httpx

logger = logging.getLogger("SlipBot.SlipOK")

# Mapping of SlipOK error codes to Thai messages
SLIPOK_ERROR_MAP = {
    1010: "⏳ ธนาคารล่าช้าหรือปิดปรับปรุงระบบชั่วคราว กรุณาเช็คยอดเงินในบัญชีโดยตรงเพื่อความถูกต้อง",
    1011: "❌ สลิปไม่ถูกต้อง หรือ คิวอาร์โค้ดไม่สามารถใช้งานได้ (ไม่พบข้อมูลในระบบธนาคาร)",
    1012: "⚠️ ตรวจพบการใช้สลิปซ้ำ! สลิปนี้เคยได้รับการตรวจยืนยันในระบบ SlipOK ไปก่อนหน้านี้แล้ว",
    1013: "❌ ยอดเงินโอนไม่ถูกต้องหรือยอดเงินไม่ตรง",
    1021: "🔑 API Key หรือ Branch ID ของ SlipOK ไม่ถูกต้อง กรุณาติดต่อแอดมินเพื่อแก้ไข",
    1022: "💳 โควต้าใช้งาน SlipOK หมดชั่วคราว (เครดิตไม่เพียงพอ) กรุณาติดต่อแอดมิน",
}

async def verify_slip_via_slipok(
    api_key: str,
    branch_id: str,
    qr_payload: str | None = None,
    image_bytes: bytes | None = None
) -> dict | None:
    """
    Verifies a Thai bank slip via the SlipOK API.
    Can verify using the raw QR code string (fastest) or by uploading the image bytes (fallback).
    
    Returns a unified dict on success:
        {
            "success": True,
            "trans_ref": str,
            "sender_name": str,
            "receiver_name": str,
            "amount": float,
            "trans_date": str,
            "sending_bank": str,
            "receiving_bank": str,
            "raw": dict
        }
    Or if SlipOK returns success=False:
        {
            "success": False,
            "error_code": int,
            "message": str,
            "raw": dict
        }
    Or returns None if connection fails or API returns bad status (outside success=False payload).
    """
    if not api_key or not branch_id:
        logger.error("SlipOK verification aborted: api_key or branch_id is missing.")
        return None

    url = f"https://api.slipok.com/api/line/apikey/{branch_id}"
    headers = {
        "x-authorization": api_key
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            if qr_payload:
                logger.info("Attempting SlipOK verification using decoded QR payload.")
                payload = {
                    "data": qr_payload,
                    "log": True
                }
                response = await client.post(url, headers=headers, json=payload)
            elif image_bytes:
                logger.info("Attempting SlipOK verification using image upload fallback.")
                files = {
                    "files": ("slip.png", image_bytes, "image/png")
                }
                data = {
                    "log": "true"
                }
                response = await client.post(url, headers=headers, files=files, data=data)
            else:
                logger.warning("Neither qr_payload nor image_bytes provided to verify_slip_via_slipok.")
                return None

            if response.status_code != 200:
                logger.error(f"SlipOK API returned HTTP status {response.status_code}: {response.text}")
                # Try to extract details if they return JSON error
                try:
                    err_json = response.json()
                    code = err_json.get("code")
                    # If it is unauthorized or out of quota, we map it
                    if response.status_code in (401, 403):
                        code = code or 1021
                    elif response.status_code == 402:
                        code = code or 1022
                        
                    if code:
                        msg = SLIPOK_ERROR_MAP.get(code, err_json.get("message", "SlipOK API error"))
                        return {
                            "success": False,
                            "error_code": code,
                            "message": msg,
                            "raw": err_json
                        }
                except Exception:
                    pass
                return None

            res_json = response.json()
            logger.info(f"SlipOK response received: {res_json}")

            # Check if SlipOK verification was successful
            is_success = res_json.get("success", False)
            if is_success:
                data_node = res_json.get("data", {})
                
                # Retrieve sender display name (check display name or name)
                sender = data_node.get("sender", {})
                sender_name = sender.get("displayName") or sender.get("name") or "ไม่ระบุผู้ส่ง"
                
                # Retrieve receiver display name and account
                receiver = data_node.get("receiver", {})
                receiver_name = receiver.get("displayName") or receiver.get("name") or "ไม่ระบุผู้รับ"
                receiver_account = receiver.get("account", {}).get("value") or ""
                
                # Date formatting
                trans_date = data_node.get("transTimestamp")
                if not trans_date:
                    t_date = data_node.get("transDate", "")
                    t_time = data_node.get("transTime", "")
                    trans_date = f"{t_date} {t_time}".strip()
                if not trans_date:
                    trans_date = "ไม่ระบุวันเวลา"

                # Parse amount safely
                try:
                    amount = float(data_node.get("amount") or 0.0)
                except ValueError:
                    amount = 0.0

                # Retrieve extra ref fields (where bank sometimes puts Thai name/reference)
                ref1 = data_node.get("ref1") or ""
                ref2 = data_node.get("ref2") or ""
                ref3 = data_node.get("ref3") or ""

                return {
                    "success": True,
                    "trans_ref": data_node.get("transRef") or "UNKNOWN_REF",
                    "sender_name": sender_name,
                    "receiver_name": receiver_name,
                    "receiver_account": receiver_account,
                    "ref1": ref1,
                    "ref2": ref2,
                    "ref3": ref3,
                    "amount": amount,
                    "trans_date": trans_date,
                    "sending_bank": data_node.get("sendingBank", ""),
                    "receiving_bank": data_node.get("receivingBank", ""),
                    "raw": res_json
                }
            else:
                # Handle error responses from SlipOK
                code = res_json.get("code")
                msg = res_json.get("message")
                
                # Translate error code if we have it in map
                translated_msg = SLIPOK_ERROR_MAP.get(code, msg or "สลิปตรวจสอบไม่สำเร็จ (ไม่ระบุสาเหตุ)")
                logger.warning(f"SlipOK verification failed: Code={code} | Message={msg} | Translated={translated_msg}")
                
                return {
                    "success": False,
                    "error_code": code,
                    "message": translated_msg,
                    "raw": res_json
                }

    except Exception as e:
        logger.error(f"Exception raised during SlipOK verification request: {e}", exc_info=True)
        return None


async def check_slipok_quota(api_key: str, branch_id: str) -> dict | None:
    """
    Checks the remaining quota for a SlipOK API key.
    URL: GET https://api.slipok.com/api/line/apikey/{branch_id}/quota
    """
    url = f"https://api.slipok.com/api/line/apikey/{branch_id}/quota"
    headers = {
        "x-authorization": api_key,
        "User-Agent": "SlipBot/1.0"
    }
    
    logger.info(f"Checking SlipOK quota for branch {branch_id}...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.error(f"SlipOK quota check returned status {response.status_code}: {response.text}")
                return None
                
            res_json = response.json()
            if res_json.get("success"):
                return res_json.get("data")
            return None
    except Exception as e:
        logger.error(f"Exception during SlipOK quota check: {e}")
        return None
