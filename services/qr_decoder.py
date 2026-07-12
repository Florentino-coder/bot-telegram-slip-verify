import io
import logging
from PIL import Image
from pyzbar.pyzbar import decode

logger = logging.getLogger("SlipBot.QRDecoder")

def parse_tlv(payload: str) -> dict[str, str]:
    """Parses an EMVCo string in Tag-Length-Value (TLV) format."""
    data = {}
    i = 0
    while i < len(payload):
        if i + 4 > len(payload):
            break
        tag = payload[i:i+2]
        length_str = payload[i+2:i+4]
        if not length_str.isdigit():
            break
        length = int(length_str)
        val = payload[i+4:i+4+length]
        data[tag] = val
        i += 4 + length
    return data


def parse_slip_verify_payload(payload: str) -> dict | None:
    """
    Parses a Thai bank slip Mini QR (Slip Verify) payload.
    The payload follows the EMVCo standard where Tag 30 contains:
      - Sub-tag 00: GUID / AID (e.g., A000000677010111)
      - Sub-tag 01: Sending Bank Code (e.g., 014 for SCB, 004 for KBANK)
      - Sub-tag 02: Transaction Reference Number
    """
    try:
        # Parse outer TLV tags
        outer_tags = parse_tlv(payload)
        
        # Tag 30 is the Merchant Account Information containing the slip data
        tag_30_data = outer_tags.get("30")
        if not tag_30_data:
            logger.warning("Tag 30 not found in QR payload.")
            return None
            
        # Parse sub-tags inside Tag 30
        sub_tags = parse_tlv(tag_30_data)
        
        aid = sub_tags.get("00")
        sending_bank = sub_tags.get("01")
        trans_ref = sub_tags.get("02")
        
        if not trans_ref:
            logger.warning("Transaction reference (sub-tag 02) not found inside Tag 30.")
            return None
            
        return {
            "aid": aid,
            "sending_bank": sending_bank,
            "trans_ref": trans_ref,
            "raw_payload": payload
        }
    except Exception as e:
        logger.error(f"Error parsing slip QR payload: {e}")
        return None


def decode_qr_from_bytes(image_bytes: bytes) -> dict | None:
    """
    Decodes QR code from image bytes locally using pyzbar.
    If a valid Slip Verify QR code is found, returns its parsed details.
    """
    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Decode QR codes
        decoded_objects = decode(image)
        if not decoded_objects:
            logger.info("No QR codes detected in the image.")
            return None
            
        for obj in decoded_objects:
            qr_text = obj.data.decode("utf-8")
            logger.info(f"QR Code detected: {qr_text[:30]}...")
            
            # Check if it starts with standard EMVCo payload format indicator
            if qr_text.startswith("000201"):
                parsed_data = parse_slip_verify_payload(qr_text)
                if parsed_data:
                    return parsed_data
                    
        logger.info("No valid Thai bank slip QR found in decoded QR codes.")
        return None
    except Exception as e:
        logger.error(f"Error decoding QR from image bytes: {e}")
        return None
