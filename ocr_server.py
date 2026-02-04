"""
PaddleOCR Server for Anki Kanji Stroke Order Plugin

This server runs separately from Anki and provides OCR services via HTTP.
It uses PaddleOCR for Japanese text recognition.

Usage:
    python ocr_server.py

The server will run on http://localhost:8765
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import io
from PIL import Image
import logging

app = Flask(__name__)
CORS(app)  # Allow requests from Anki

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to hold the OCR instance
ocr = None

def init_ocr():
    """Initialize Manga OCR (lazy loading)."""
    global ocr
    if ocr is None:
        try:
            from manga_ocr import MangaOcr
            
            logger.info("Initializing Manga OCR...")
            logger.info("This will download models on first run (~400MB)...")
            # Initialize Manga OCR (optimized for Japanese handwriting/manga)
            ocr = MangaOcr()
            logger.info("Manga OCR initialized successfully")
        except ImportError:
            logger.error("Manga OCR not installed. Install with: pip install manga-ocr")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Manga OCR: {e}")
            raise
    return ocr

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'paddleocr-server',
        'ocr_initialized': ocr is not None
    })

@app.route('/ocr', methods=['POST'])
def perform_ocr():
    """
    Perform OCR on the provided image.
    
    Expected JSON payload:
    {
        "image": "base64_encoded_image_data",
        "context": "expected_characters" (optional - helps OCR accuracy)
    }
    
    Returns:
    {
        "success": true,
        "text": "recognized text",
        "details": [...] // optional detailed results
    }
    """
    try:
        # Get JSON data
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({
                'success': False,
                'error': 'No image data provided'
            }), 400
        
        # Optional context for better recognition
        context = data.get('context', '')
        if context:
            logger.info(f"OCR context provided: {context}")
        
        # Decode base64 image
        image_data = data['image']
        if ',' in image_data:
            # Remove data URL prefix if present
            image_data = image_data.split(',', 1)[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed (remove alpha channel, handle grayscale)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # For single characters, add padding and centering to help OCR
        # This simulates how the character would appear in a sentence
        width, height = image.size
        max_dim = max(width, height)
        
        # If image looks like a single character (roughly square), add context padding
        aspect_ratio = width / height if height > 0 else 1
        if 0.5 < aspect_ratio < 2.0:  # Roughly square = likely single character
            # Create a larger canvas (3x size) and center the character
            new_size = (max_dim * 3, max_dim * 3)
            padded = Image.new('RGB', new_size, (255, 255, 255))  # White background
            paste_x = (new_size[0] - width) // 2
            paste_y = (new_size[1] - height) // 2
            padded.paste(image, (paste_x, paste_y))
            image = padded
            logger.info(f"Added context padding for single character: {new_size}")
        
        # Resize if image is too large
        max_size = 1024
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.LANCZOS)
            logger.info(f"Resized image to {new_size}")
        
        # Initialize OCR if needed
        logger.info("Initializing OCR instance...")
        ocr_instance = init_ocr()
        logger.info("OCR instance ready")
        
        # Perform OCR
        logger.info(f"Performing OCR on image...")
        
        try:
            # Manga OCR works directly on PIL images
            text = ocr_instance(image)
            logger.info("OCR prediction complete")
            logger.info(f"Recognized text: {text}")
        except Exception as pred_error:
            logger.error(f"Prediction failed: {pred_error}")
            import traceback
            traceback.print_exc()
            raise
        
        # Manga OCR returns simple text string
        if text and text.strip():
            logger.info(f"OCR result: {text}")
            
            return jsonify({
                'success': True,
                'text': text.strip(),
                'details': [{
                    'text': text.strip(),
                    'confidence': 1.0,  # Manga OCR doesn't provide confidence
                    'bbox': None
                }]
            })
        else:
            logger.info("No text detected")
            return jsonify({
                'success': True,
                'text': '',
                'details': []
            })
    
    except Exception as e:
        logger.error(f"OCR error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the server (for development purposes)."""
    logger.info("Shutting down server...")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        return jsonify({'success': False, 'error': 'Not running with Werkzeug server'})
    func()
    return jsonify({'success': True, 'message': 'Server shutting down...'})

if __name__ == '__main__':
    logger.info("Starting PaddleOCR server on http://localhost:8765")
    logger.info("Press Ctrl+C to stop")
    app.run(host='localhost', port=8765, debug=False)
