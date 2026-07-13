import logging
from config import Config

logger = logging.getLogger("SlipBot.RiskEngine")

def normalize_ref(ref: str) -> str:
    """
    Normalizes transaction reference numbers by converting to uppercase,
    removing symbols, and replacing common OCR-confused characters:
    - I, L, l -> 1
    - O, o -> 0
    """
    if not ref:
        return ""
    # Strip spaces, hyphens, underscores and convert to uppercase
    s = ref.replace(" ", "").replace("-", "").replace("_", "").upper()
    # Unify character confusions
    s = s.replace("I", "1").replace("L", "1")
    s = s.replace("O", "0")
    return s

def clean_thai_name(name: str) -> str:
    """
    Cleans Thai and English names by removing spaces, common punctuation,
    and business/personal prefixes/suffixes (like บริษัท, บจก., นาย, นางสาว, Co., Ltd.)
    """
    name = name.lower()
    for char in [" ", ".", "-", "*", "(", ")", "[", "]", "_", "/"]:
        name = name.replace(char, "")
    
    # Prefix list to clean up (ordered by length descending to avoid partial matches first)
    prefixes = [
        "บริษัทจำกัด", "บริษัท", "บจกจำกัด", "บจก", "หจกจำกัด", "หจก",
        "นางสาว", "เด็กหญิง", "เด็กชาย", "นาย", "นาง", "miss", "mrs", "mr",
        "จำกัด", "coltd", "corp", "ltd", "co"
    ]
    for p in prefixes:
        name = name.replace(p, "")
    return name

def match_merchant_name(configured_name: str, slip_name: str) -> bool:
    """
    Intelligently checks if the slip receiver name matches the configured merchant name.
    Handles masking, common Thai name prefixes/suffixes, and substring matching.
    """
    c_clean = clean_thai_name(configured_name)
    s_clean = clean_thai_name(slip_name)
    
    if not c_clean or not s_clean:
        return False
        
    # Check if either is a prefix of the other (handles masking at the end like "บริษัท ดี พ" matching "บริษัท ดี พลัส โปร จำกัด")
    if c_clean.startswith(s_clean) or s_clean.startswith(c_clean):
        return True
        
    # Check if either is a substring of the other
    if s_clean in c_clean or c_clean in s_clean:
        return True
        
    return False


def match_account_number(full_acc: str, masked_acc: str) -> bool:
    """
    Intelligently checks if a full account number matches a masked account number.
    Handles wildcard characters (x, X, *, _) and partial matching (e.g. suffix 'x-2850').
    """
    full_clean = "".join([c for c in full_acc if c.isdigit()])
    masked_clean = "".join([c.lower() for c in masked_acc if c.isdigit() or c.lower() in ("x", "*", "_")])
    
    if not full_clean or not masked_clean:
        return False
        
    # Case 1: Exact length match (positional matching)
    if len(full_clean) == len(masked_clean):
        for f_char, m_char in zip(full_clean, masked_clean):
            if m_char in ("x", "*", "_"):
                continue
            if f_char != m_char:
                return False
        return True
        
    # Case 2: Different lengths (e.g. OCR only captured last 4 digits '2850' or 'x-2850')
    masked_digits = "".join([c for c in masked_clean if c.isdigit()])
    if not masked_digits:
        return False
        
    # Check if digits align as suffix
    if masked_clean.endswith(masked_digits):
        return full_clean.endswith(masked_digits)
    # Check if digits align as prefix
    if masked_clean.startswith(masked_digits):
        return full_clean.startswith(masked_digits)
        
    # Fallback to substring matching
    return masked_digits in full_clean


def assess_slip_risk(
    qr_data: dict | None,
    ocr_data: dict | None,
    merchant_names: str | list[str] | None = None,
    allowed_accounts: list[str] | None = None
) -> dict:
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
        warnings.append("No QR code detected; relying solely on OCR text extraction. (อาจจะปลอมแปลง - ตรวจไม่พบ QR Code)")
        risk_score += 20

    # Ensure ocr_data is not None for the checks below
    assert ocr_data is not None

    # 1. Receiver Name Verification
    receiver_name = ocr_data.get("receiver_name") or ""
    allowed_names = []
    if merchant_names is not None:
        if isinstance(merchant_names, str):
            allowed_names = [merchant_names]
        else:
            allowed_names = list(merchant_names)
    else:
        if Config.MERCHANT_NAME and Config.MERCHANT_NAME != "your_merchant_name_here":
            allowed_names = [Config.MERCHANT_NAME]

    if allowed_names:
        if not receiver_name:
            warnings.append("Receiver name could not be extracted from the slip image.")
            risk_score += 30
        else:
            # Check if any allowed name matches using match_merchant_name
            match_found = False
            for m_name in allowed_names:
                if match_merchant_name(m_name, receiver_name):
                    match_found = True
                    break
            if not match_found:
                allowed_str = ", ".join([f"'{n}'" for n in allowed_names])
                warnings.append(f"Receiver name mismatch. Expected one of: {allowed_str}, Found: '{receiver_name}'")
                risk_score += 60

    # 1.5. Receiver Account Number Verification
    receiver_acc = ocr_data.get("receiver_account") or ""
    if allowed_accounts:
        if not receiver_acc:
            warnings.append("Receiver account number could not be extracted from the slip.")
            risk_score += 25
        else:
            match_found = False
            for allowed_acc in allowed_accounts:
                if match_account_number(allowed_acc, receiver_acc):
                    match_found = True
                    break
            if not match_found:
                allowed_accs_str = ", ".join([f"'{a}'" for a in allowed_accounts])
                warnings.append(f"Receiver account number mismatch. Expected one of: {allowed_accs_str}, Found: '{receiver_acc}'")
                risk_score += 50

    # 2. Transaction Reference Mismatch Check
    qr_ref = qr_data.get("trans_ref") if qr_data else None
    ocr_ref = ocr_data.get("trans_ref")
    
    if qr_ref and ocr_ref:
        clean_qr_ref = normalize_ref(qr_ref)
        clean_ocr_ref = normalize_ref(ocr_ref)
        
        if clean_qr_ref != clean_ocr_ref:
            warnings.append(
                f"รหัสธุรกรรมไม่ตรงกัน! (ตรวจพบการสวม QR Code หรือการตัดต่อสลิป)\n"
                f"  • รหัสธุรกรรมใน QR Code: `{qr_ref}`\n"
                f"  • รหัสธุรกรรมบนภาพ (OCR): `{ocr_ref}`"
            )
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
