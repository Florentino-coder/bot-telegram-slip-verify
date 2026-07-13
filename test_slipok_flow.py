import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Reconfigure stdout/stderr to use UTF-8 to prevent encoding errors on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Import handlers under test
import handlers.slip
from handlers.slip import process_slip_image
from config import Config

# Mock core db functions to isolate testing
handlers.slip.is_maintenance_mode = AsyncMock(return_value=False)
handlers.slip.get_amount_limits = AsyncMock(return_value=(100.0, 999.0))
handlers.slip.get_allowed_accounts = AsyncMock(return_value=[])
handlers.slip.check_duplicate = AsyncMock(return_value=False)
handlers.slip.log_transaction = AsyncMock(return_value=True)

async def run_slipok_integration_test():
    print("\n--- Starting SlipOK Routing & Flow Integration Test ---")
    Config.ADMIN_USER_IDS = [123456789]
    
    # 1. Mock Bot and Message objects
    mock_bot = AsyncMock()
    mock_message = AsyncMock()
    
    mock_photo = MagicMock()
    mock_photo.file_id = "mock_file_id_slipok_test"
    mock_message.photo = [mock_photo]
    mock_message.from_user.id = 123456789 # Admin user ID
    mock_message.chat.type = "private"
    mock_message.chat.title = "Private Test Chat"
    
    processing_msg = AsyncMock()
    mock_message.reply.return_value = processing_msg
    
    # 2. Setup mock data
    mock_qr_data = {
        "aid": "A000000677010111",
        "sending_bank": "014",
        "trans_ref": "REF_1234567890",
        "raw_payload": "000201..."
    }
    
    mock_ocr_data = {
        "trans_ref": "REF_1234567890",
        "sender_name": "Somchai Sukdee",
        "receiver_name": "Antigravity Merchant",
        "amount": 150.00,
        "trans_date": "2026-07-13 12:00:00"
    }

    mock_slipok_success_response = {
        "success": True,
        "trans_ref": "REF_1234567890_SLIPOK",
        "sender_name": "Somchai Sukdee",
        "receiver_name": "Antigravity Merchant",
        "amount": 150.00,
        "trans_date": "2026-07-13T12:00:00.000Z",
        "sending_bank": "014",
        "receiving_bank": "004",
        "raw": {"success": True, "data": {"transRef": "REF_1234567890_SLIPOK"}}
    }

    mock_slipok_fail_response = {
        "success": False,
        "error_code": 1012,
        "message": "⚠️ ตรวจพบการใช้สลิปซ้ำ! สลิปนี้เคยได้รับการตรวจยืนยันในระบบ SlipOK ไปก่อนหน้านี้แล้ว",
        "raw": {"success": False, "code": 1012}
    }

    # Case 1: SlipOK Mode OFF -> Should fall back to local OCR
    print("\n[Case 1] SlipOK Mode = OFF (Should process locally)")
    mock_slipok_config_off = {
        "mode": "off",
        "api_key": "test_api_key",
        "branch_id": "test_branch_id",
        "min_amount": 500.0
    }
    
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_off)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=mock_ocr_data)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock()) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_not_called()
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Response:\n{edited_text}")
        if "สลิปผ่านเกณฑ์" in edited_text and "การตรวจสอบ QR" in edited_text:
            print("✅ Case 1: PASSED")
        else:
            print("❌ Case 1: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 2: SlipOK Mode SMART, Slip is safe and low amount -> Should skip SlipOK (process locally)
    print("\n[Case 2] SlipOK Mode = SMART, Safe Slip, Amount < Min (Should skip SlipOK)")
    mock_slipok_config_smart = {
        "mode": "smart",
        "api_key": "test_api_key",
        "branch_id": "test_branch_id",
        "min_amount": 500.0
    }
    
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_smart)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=mock_ocr_data)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock()) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_not_called()
        edited_text = processing_msg.edit_text.call_args[0][0]
        if "สลิปผ่านเกณฑ์" in edited_text and "การตรวจสอบ QR" in edited_text:
            print("✅ Case 2: PASSED")
        else:
            print("❌ Case 2: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 3: SlipOK Mode SMART, Amount >= Min (High Value) -> Should trigger SlipOK
    print("\n[Case 3] SlipOK Mode = SMART, Safe Slip, High Amount >= 500 (Should call SlipOK)")
    high_amount_ocr_data = mock_ocr_data.copy()
    high_amount_ocr_data["amount"] = 600.00
    
    mock_slipok_high_response = mock_slipok_success_response.copy()
    mock_slipok_high_response["amount"] = 600.00
    
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_smart)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=high_amount_ocr_data)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock(return_value=mock_slipok_high_response)) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_called_once()
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Response:\n{edited_text}")
        if "ยืนยันผ่านธนาคาร" in edited_text and "600.00 THB" in edited_text and "SlipOK" in edited_text:
            print("✅ Case 3: PASSED")
        else:
            print("❌ Case 3: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 4: SlipOK Mode SMART, Suspicious (Receiver Name mismatch) -> Should trigger SlipOK
    print("\n[Case 4] SlipOK Mode = SMART, Wrong Receiver Name (Should call SlipOK)")
    wrong_receiver_ocr = mock_ocr_data.copy()
    wrong_receiver_ocr["receiver_name"] = "Somying Shop"
    
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_smart)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=wrong_receiver_ocr)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock(return_value=mock_slipok_success_response)) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_called_once()
        edited_text = processing_msg.edit_text.call_args[0][0]
        if "ยืนยันผ่านธนาคาร" in edited_text:
            print("✅ Case 4: PASSED")
        else:
            print("❌ Case 4: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 5: SlipOK Mode SMART, SlipOK returns verification error (e.g., duplicate slip in SlipOK)
    print("\n[Case 5] SlipOK Mode = SMART, SlipOK returns 1012 duplicate error (Should reject)")
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_smart)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=wrong_receiver_ocr)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock(return_value=mock_slipok_fail_response)) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_called_once()
        edited_text = processing_msg.edit_text.call_args[0][0]
        print(f"Response:\n{edited_text}")
        if "ตรวจสอบสลิปไม่ผ่าน" in edited_text and "ตรวจพบการใช้สลิปซ้ำ" in edited_text:
            print("✅ Case 5: PASSED")
        else:
            print("❌ Case 5: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 6: SlipOK Mode SMART, SlipOK returns API key error (code 1021) -> Should fallback to local verification instead of rejecting
    print("\n[Case 6] SlipOK Mode = SMART, SlipOK returns 1021 quota/key error (Should fallback to local check)")
    mock_slipok_key_err = {
        "success": False,
        "error_code": 1021,
        "message": "API key invalid",
        "raw": {}
    }
    high_amount_ocr_data = mock_ocr_data.copy()
    high_amount_ocr_data["amount"] = 600.00
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_smart)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=high_amount_ocr_data)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock(return_value=mock_slipok_key_err)) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_called_once()
        edited_text = processing_msg.edit_text.call_args[0][0]
        # Should fallback to local success text because local checks are safe (names match, amount is safe)
        if "สลิปผ่านเกณฑ์" in edited_text:
            print("✅ Case 6: PASSED")
        else:
            print("❌ Case 6: FAILED")

    # Reset mocks
    mock_message.reply.reset_mock()
    processing_msg.edit_text.reset_mock()

    # Case 7: SlipOK Mode ALWAYS -> Should always call SlipOK
    print("\n[Case 7] SlipOK Mode = ALWAYS (Should always call SlipOK)")
    mock_slipok_config_always = {
        "mode": "always",
        "api_key": "test_api_key",
        "branch_id": "test_branch_id",
        "min_amount": 500.0
    }
    with patch("handlers.slip.get_slipok_config", AsyncMock(return_value=mock_slipok_config_always)), \
         patch("handlers.slip.get_merchant_names", AsyncMock(return_value=["Antigravity Merchant"])), \
         patch("handlers.slip.decode_qr_from_bytes", return_value=mock_qr_data), \
         patch("handlers.slip.extract_slip_details", AsyncMock(return_value=mock_ocr_data)), \
         patch("handlers.slip.verify_slip_via_slipok", AsyncMock(return_value=mock_slipok_success_response)) as mock_verify:
         
        await process_slip_image(mock_message, mock_bot)
        mock_verify.assert_called_once()
        edited_text = processing_msg.edit_text.call_args[0][0]
        if "ยืนยันผ่านธนาคาร" in edited_text:
            print("✅ Case 7: PASSED")
        else:
            print("❌ Case 7: FAILED")


if __name__ == "__main__":
    asyncio.run(run_slipok_integration_test())
