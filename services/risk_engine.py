import logging
from config import Config

logger = logging.getLogger("SlipBot.RiskEngine")

def assess_slip_risk(qr_data: dict | None, ocr_data: dict | None) -> dict:
    """
    Assesses the risk of the bank transfer slip.
    Cross-checks the locally parsed QR data with OCR text data from Vision AI.
    
    Returns a dict with:
      - 'is_safe': bool (True if low risk, False otherwise)
      - 'warnings': list[str] (List of reason strings for suspicion)
      - 'risk_score': int (Value from 0 to 100)
    """
    warnings = []
    risk_score = 0

    # Case 1: Both QR and OCR data are missing
    if not qr_data and not ocr_data:
        return {
            "is_safe": False,
            "warnings": ["Could not parse QR code or extract text details from the image."],
            "risk_score": 100
        }

    # Case 2: QR is present but OCR is missing (and STRICT_QR_MATCH or OCR required)
    if qr_data and not ocr_data:
        # If OCR fails, but QR works:
        # If strict verification is required, we fail. Otherwise, we might allow it.
        # But we need OCR to verify the Receiver Name and Amount!
        return {
            "is_safe": False,
            "warnings": ["QR code parsed successfully, but text verification failed. Merchant receiver name cannot be verified."],
            "risk_score": 50
        }

    # Case 3: OCR is present but QR is missing
    if ocr_data and not qr_data:
        if not Config.ENABLE_OCR_FALLBACK:
            return {
                "is_safe": False,
                "warnings": ["QR code is missing or unreadable, and OCR fallback is disabled."],
                "risk_score": 90
            }
        warnings.append("No QR code detected; relying solely on OCR text extraction.")
        risk_score += 20

    # Ensure ocr_data is not None for the checks below
    assert ocr_data is not None

    # 1. Receiver Name Verification
    receiver_name = ocr_data.get("receiver_name") or ""
    merchant_name = Config.MERCHANT_NAME or ""
    
    if not merchant_name:
        logger.warning("Config MERCHANT_NAME is not set. Skipping receiver name validation.")
    elif not receiver_name:
        warnings.append("Receiver name could not be extracted from the slip image.")
        risk_score += 30
    elif merchant_name.lower() not in receiver_name.lower():
        # Substring matching (case insensitive)
        warnings.append(f"Receiver name mismatch. Expected: '{merchant_name}', Found: '{receiver_name}'")
        risk_score += 60

    # 2. Transaction Reference Mismatch Check
    qr_ref = qr_data.get("trans_ref") if qr_data else None
    ocr_ref = ocr_data.get("trans_ref")
    
    if qr_ref and ocr_ref:
        # Strip all whitespace, hyphens, or formatting for comparison
        clean_qr_ref = qr_ref.replace(" ", "").replace("-", "").replace("_", "")
        clean_ocr_ref = ocr_ref.replace(" ", "").replace("-", "").replace("_", "")
        
        if clean_qr_ref != clean_ocr_ref:
            warnings.append(f"Transaction ID mismatch! QR Ref: '{qr_ref}', OCR Ref: '{ocr_ref}'. This indicates potential slip alteration.")
            risk_score += 90

    # 3. Transfer Amount Verification
    amount = ocr_data.get("amount")
    if amount is None:
        warnings.append("Transfer amount could not be extracted from the slip.")
        risk_score += 30
    elif not isinstance(amount, (int, float)) or amount <= 0:
        warnings.append(f"Invalid transfer amount extracted: {amount}")
        risk_score += 40

    is_safe = risk_score < 50
    return {
        "is_safe": is_safe,
        "warnings": warnings,
        "risk_score": min(risk_score, 100)
    }
