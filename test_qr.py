import sys
import os

# Reconfigure stdout/stderr to use UTF-8 to prevent encoding errors on Windows console when printing emojis
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from services.qr_decoder import parse_slip_verify_payload, decode_qr_from_bytes

def test_tlv_parser():
    print("Running TLV parser unit test...")
    # Mock EMVCo QR code string for Thai bank slip
    # A standard structure:
    # 000201 (Format indicator)
    # 3048 (Tag 30, Length 48)
    #   0016A000000677010111 (Sub-tag 00, Length 16, AID)
    #   0103014 (Sub-tag 01, Length 03, Sending bank: SCB)
    #   021720260712115500001 (Sub-tag 02, Length 17, Ref: 20260712115500001)
    mock_payload = (
        "000201"
        "3048"
          "0016A000000677010111"
          "0103014"
          "021720260712115500001"
    )
    
    parsed = parse_slip_verify_payload(mock_payload)
    if not parsed:
        print("❌ TLV Parser Test Failed: Return value is None")
        return False
        
    if parsed["sending_bank"] != "014":
        print(f"❌ TLV Parser Test Failed: Sending bank mismatch. Expected: '014', Found: '{parsed['sending_bank']}'")
        return False
        
    if parsed["trans_ref"] != "20260712115500001":
        print(f"❌ TLV Parser Test Failed: Trans Ref mismatch. Expected: '20260712115500001', Found: '{parsed['trans_ref']}'")
        return False
        
    print("✅ TLV Parser Unit Test Passed successfully!")
    return True


def test_file_decode(file_path: str):
    print(f"Testing QR decoder on local file: {file_path}")
    if not os.path.exists(file_path):
        print(f"❌ Error: File '{file_path}' does not exist.")
        return
        
    try:
        with open(file_path, "rb") as f:
            img_bytes = f.read()
            
        result = decode_qr_from_bytes(img_bytes)
        if result:
            print("✅ QR Code Decoded successfully!")
            print(f"🔹 AID: {result.get('aid')}")
            print(f"🔹 Sending Bank: {result.get('sending_bank')}")
            print(f"🔹 Transaction Ref: {result.get('trans_ref')}")
        else:
            print("❌ No valid slip verify QR code could be decoded from this file.")
    except Exception as e:
        print(f"❌ Error during file decoding: {e}")


if __name__ == "__main__":
    success = test_tlv_parser()
    
    # If a file path is provided as CLI argument, test it
    if len(sys.argv) > 1:
        test_file_decode(sys.argv[1])
    else:
        print("\n💡 Tip: You can run this script with an image path to test QR decoding:")
        print("   python test_qr.py path/to/slip_image.jpg")
        
    sys.exit(0 if success else 1)
