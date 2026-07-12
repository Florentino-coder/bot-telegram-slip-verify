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
from handlers.slip import process_slip_image


async def run_integration_test():
    print("\n--- Starting Bot Handler Integration Test ---")
    
    # 1. Mock Bot and Message objects
    mock_bot = AsyncMock()
    mock_message = AsyncMock()
    
    # Set up mock photo metadata
    mock_photo = MagicMock()
    mock_photo.file_id = "mock_file_id_123"
    mock_message.photo = [mock_photo]
    mock_message.from_user.id = 123456789
    
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
        if "ยืนยันสลิปโอนเงินสำเร็จ" in edited_text:
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
        if "ตรวจสอบสลิปไม่ผ่าน / น่าสงสัย" in edited_text and "ID mismatch" in edited_text:
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


if __name__ == "__main__":
    asyncio.run(run_integration_test())
