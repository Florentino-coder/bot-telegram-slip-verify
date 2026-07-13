import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Reconfigure stdout/stderr to use UTF-8 to prevent encoding errors on Windows console when printing emojis
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure dummy configs are loaded successfully
from config import Config
print(f"Loaded config MERCHANT_NAME: '{Config.MERCHANT_NAME}'")

# Import handlers under test
import handlers.slip
from handlers.slip import process_slip_image

# Mock maintenance mode check to prevent database calls during test execution
handlers.slip.is_maintenance_mode = AsyncMock(return_value=False)
handlers.slip.get_amount_limits = AsyncMock(return_value=(100.0, 999.0))
handlers.slip.get_merchant_names = AsyncMock(return_value=["Antigravity Merchant"])
handlers.slip.get_allowed_accounts = AsyncMock(return_value=[])
handlers.slip.get_slipok_credentials = AsyncMock(return_value=[])
handlers.slip.update_slipok_credential_status = AsyncMock(return_value=True)
handlers.slip.get_slipok_config = AsyncMock(return_value={"mode": "off", "api_key": "", "branch_id": "", "min_amount": 500.0})


async def run_integration_test():
    print("\n--- Starting Bot Handler Integration Test ---")
    
    # Override admin IDs for testing
    Config.ADMIN_USER_IDS = [123456789]
    
    # 1. Mock Bot and Message objects
    mock_bot = AsyncMock()
    mock_message = AsyncMock()
    
    # Set up mock photo metadata
    mock_photo = MagicMock()
    mock_photo.file_id = "mock_file_id_123"
    mock_message.photo = [mock_photo]
    mock_message.from_user.id = 123456789
    mock_message.chat.type = "private"
    mock_message.chat.title = "Private Test Chat"
    
    # Capture replies and edits
    processing_msg = AsyncMock()
    mock_message.reply.return_value = processing_msg
    
    # 2. Setup service mocks
    mock_qr_data = {
        "aid": "A000000677010111",
        "sending_bank": "014",
        "trans_ref": "20260712115500001",
        "raw_payload": "000201..."
    }
    
    mock_ocr_data = {
        "trans_ref": "20260712115500001",
        "sender_name": "Somchai Sukdee",
        "receiver_name": "Antigravity Merchant",
        "amount": 150.00,
        "trans_date": "2026-07-12 11:55:00"
    }

    # Case A: Valid Slip
    print("\n[Test Case A] Processing a valid and genuine bank slip...")
    with patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=mock_ocr_data)), \
         patch("handlers.slip.check_duplicate", AsyncMock(return_value=False)), \
         patch("handlers.slip.log_transaction", AsyncMock(return_value=True)):
         
        await process_slip_image(mock_message, mock_bot)
        
        # Verify replies
        mock_message.reply.assert_called_with(
            "⏳ **กำลังดาวน์โหลดและประมวลผลสลิปโอนเงินของคุณ...**\nกรุณารอสักครู่"
        )
        # Capture what was printed by the edited reply
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Bot Response:\n{edited_text}")
        if "สลิปผ่านเกณฑ์" in edited_text:
            print("✅ Test Case A: PASSED")
        else:
            print("❌ Test Case A: FAILED")

    # Reset mocks for next test
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case B: Duplicate Slip
    print("\n[Test Case B] Processing a duplicate slip (already verified)...")
    with patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.check_duplicate", AsyncMock(return_value=True)):
         
        await process_slip_image(mock_message, mock_bot)
        
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Bot Response:\n{edited_text}")
        if "ตรวจพบการใช้สลิปซ้ำ" in edited_text:
            print("✅ Test Case B: PASSED")
        else:
            print("❌ Test Case B: FAILED")

    # Reset mocks for next test
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case C: Tampered/Modified Slip (QR ref does not match OCR ref)
    print("\n[Test Case C] Processing a tampered slip (QR ref mismatch with OCR text)...")
    tampered_ocr_data = mock_ocr_data.copy()
    tampered_ocr_data["trans_ref"] = "DIFFERENT_REF_99999" # Altered text on slip
    
    with patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=tampered_ocr_data)), \
         patch("handlers.slip.check_duplicate", AsyncMock(return_value=False)):
         
        await process_slip_image(mock_message, mock_bot)
        
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Bot Response:\n{edited_text}")
        if "ตรวจสอบสลิปไม่ผ่าน / น่าสงสัย" in edited_text and "รหัสธุรกรรมไม่ตรงกัน" in edited_text:
            print("✅ Test Case C: PASSED")
        else:
            print("❌ Test Case C: FAILED")

    # Reset mocks for next test
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case D: Receiver Name Mismatch
    print("\n[Test Case D] Processing a slip transferred to a different merchant...")
    wrong_receiver_ocr_data = mock_ocr_data.copy()
    wrong_receiver_ocr_data["receiver_name"] = "Somying Shop" # Wrong receiver name
    
    with patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=wrong_receiver_ocr_data)), \
         patch("handlers.slip.check_duplicate", AsyncMock(return_value=False)), \
         patch("config.Config.MERCHANT_NAME", "Antigravity Merchant"):
          
        await process_slip_image(mock_message, mock_bot)
        
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Bot Response:\n{edited_text}")
        if "ตรวจสอบสลิปไม่ผ่าน / น่าสงสัย" in edited_text and "Receiver name mismatch" in edited_text:
            print("✅ Test Case D: PASSED")
        else:
            print("❌ Test Case D: FAILED")

    # Reset mocks for next test
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case E: Confusing Characters (I in QR, 1 in OCR)
    print("\n[Test Case E] Testing OCR character confusion (I in QR, 1 in OCR)...")
    qr_data_with_I = mock_qr_data.copy()
    qr_data_with_I["trans_ref"] = "619314297410I000015B9790" # Real reference with 'I'
    ocr_data_with_1 = mock_ocr_data.copy()
    ocr_data_with_1["trans_ref"] = "6193142974101000015B9790" # Misread as '1' by OCR
    
    with patch("handlers.slip.decode_qr_from_bytes", return_value=qr_data_with_I), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=ocr_data_with_1)), \
         patch("handlers.slip.check_duplicate", AsyncMock(return_value=False)):
          
        await process_slip_image(mock_message, mock_bot)
        
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Bot Response:\n{edited_text}")
        if "สลิปผ่านเกณฑ์" in edited_text and "อาจจะเป็นสลิปจริง" in edited_text:
            print("✅ Test Case E: PASSED")
        else:
            print("❌ Test Case E: FAILED")


if __name__ == "__main__":
    asyncio.run(run_integration_test())
