"""
Test script for PaddleOCR Server

This script tests the OCR server with a sample image.
Usage: python test_ocr.py <image_path>
Example: python test_ocr.py hana.png
"""

import sys
import base64
import json
from pathlib import Path

# Import the OCR client
from ocr_client import check_ocr_server, recognize_text, get_server_status

def test_ocr_with_image(image_path):
    """Test OCR with a given image file."""
    
    print("=" * 60)
    print("PaddleOCR Server Test")
    print("=" * 60)
    
    # Check if server is running
    print("\n1. Checking OCR server status...")
    if check_ocr_server():
        print("   ✓ OCR server is running")
        status = get_server_status()
        print(f"   Status: {status}")
    else:
        print("   ✗ OCR server is NOT running!")
        print("\n   Please start the server first:")
        print("   - Windows: Run start_ocr_server.bat")
        print("   - Or manually: python ocr_server.py")
        return False
    
    # Check if image exists
    print(f"\n2. Loading image: {image_path}")
    img_path = Path(image_path)
    if not img_path.exists():
        print(f"   ✗ Image file not found: {image_path}")
        return False
    print(f"   ✓ Image found: {img_path.absolute()}")
    
    # Read and encode image
    print("\n3. Encoding image to base64...")
    try:
        with open(img_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        print(f"   ✓ Image encoded ({len(image_data)} characters)")
    except Exception as e:
        print(f"   ✗ Failed to read image: {e}")
        return False
    
    # Perform OCR
    print("\n4. Performing OCR...")
    print("   (This may take 10-20 seconds on first run while models load)")
    result = recognize_text(image_data)
    
    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if result['success']:
        print(f"\n✓ SUCCESS!")
        print(f"\nRecognized Text: {result['text']}")
        
        if result.get('details'):
            print(f"\nDetailed Results ({len(result['details'])} text regions):")
            print("-" * 60)
            for i, detail in enumerate(result['details'], 1):
                print(f"\n  Region {i}:")
                print(f"    Text: {detail['text']}")
                print(f"    Confidence: {detail['confidence']:.2%}")
                if detail.get('bbox'):
                    print(f"    Bounding Box: {detail['bbox']}")
        
        if not result['text']:
            print("\n⚠ Warning: No text was detected in the image")
            print("   Possible reasons:")
            print("   - Image is too blurry or low contrast")
            print("   - Text is too small")
            print("   - Image doesn't contain Japanese text")
    else:
        print(f"\n✗ FAILED!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        return False
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    # Get image path from command line or use default
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = 'hana.png'
    
    success = test_ocr_with_image(image_path)
    
    if not success:
        print("\n❌ Test failed. Please check the error messages above.")
        sys.exit(1)
    else:
        print("\n✅ OCR server is working correctly!")
        print("   You can now integrate it with Anki.")
        sys.exit(0)
