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
    The payload follows the EMVCo standard where Tag 30 (or Tag 00) contains:
      - Sub-tag 00: GUID / AID (e.g., A000000677010111 or 000001)
      - Sub-tag 01: Sending Bank Code (e.g., 014 for SCB, 004 for KBANK)
      - Sub-tag 02: Transaction Reference Number
    """
    try:
        # Parse outer TLV tags
        outer_tags = parse_tlv(payload)
        
        # Check Tag 30 first (standard), fallback to Tag 00 (SCB and some others)
        tag_data = outer_tags.get("30") or outer_tags.get("00")
        if not tag_data:
            logger.warning("Neither Tag 30 nor Tag 00 found in QR payload.")
            return None
            
        # Parse sub-tags inside the container tag
        sub_tags = parse_tlv(tag_data)
        
        aid = sub_tags.get("00")
        sending_bank = sub_tags.get("01")
        trans_ref = sub_tags.get("02")
        
        if not trans_ref:
            logger.warning("Transaction reference (sub-tag 02) not found inside container tag.")
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
    If standard decoding fails, applies sequential image preprocessing
    (grayscale, contrast enhancement, scaling) to improve detection.
    """
    try:
        # Load image from bytes
        original_image = Image.open(io.BytesIO(image_bytes))
        
        # We will try a sequence of preprocessed versions of the image
        # 1. Original image
        # 2. Grayscale image
        # 3. Grayscale + Enhanced Contrast (2x)
        # 4. Grayscale + Scaled Up (2x)
        # 5. Grayscale + Scaled Up (2x) + Enhanced Contrast (2.0x)
        # 6. Grayscale + Scaled Up (2x) + Binarized (Threshold 128)
        
        preprocessors = []
        
        # 1. Original
        preprocessors.append(("Original", original_image))
        
        # Convert to Grayscale (L)
        gray_img = original_image.convert('L')
        preprocessors.append(("Grayscale", gray_img))
        
        # Grayscale + Enhanced Contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(gray_img)
        contrast_img = enhancer.enhance(2.0)
        preprocessors.append(("Grayscale + Contrast", contrast_img))
        
        # Grayscale + Scaled Up
        w, h = gray_img.size
        scaled_img = gray_img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        preprocessors.append(("Grayscale + Scaled 2x", scaled_img))
        
        # Grayscale + Scaled Up + Contrast
        scaled_enhancer = ImageEnhance.Contrast(scaled_img)
        scaled_contrast_img = scaled_enhancer.enhance(2.0)
        preprocessors.append(("Grayscale + Scaled 2x + Contrast", scaled_contrast_img))
        
        # Grayscale + Scaled Up + Binarized
        binarized_img = scaled_img.point(lambda x: 0 if x < 128 else 255, '1')
        preprocessors.append(("Grayscale + Scaled 2x + Binarized", binarized_img))

        for name, img in preprocessors:
            logger.info(f"Attempting QR decoding with image preprocessor: {name}")
            decoded_objects = decode(img)
            if decoded_objects:
                for obj in decoded_objects:
                    try:
                        qr_text = obj.data.decode("utf-8")
                        logger.info(f"[{name}] QR Code detected: {qr_text}")
                        
                        # Let's parse it using our TLV parser to see if it works
                        parsed_data = parse_slip_verify_payload(qr_text)
                        if parsed_data:
                            logger.info(f"Successfully decoded QR using preprocessor: {name}")
                            return parsed_data
                    except Exception as dec_err:
                        logger.error(f"Error decoding text from QR object: {dec_err}")
                        
        logger.info("No valid Thai bank slip QR found in decoded QR codes after all preprocessing attempts.")
        return None
    except Exception as e:
        logger.error(f"Error decoding QR from image bytes: {e}")
        return None
