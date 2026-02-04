"""
OCR Client for communicating with the PaddleOCR server.

This module provides functions to send images to the OCR server
and receive recognized text.
"""

import urllib.request
import urllib.error
import json
import base64

OCR_SERVER_URL = "http://localhost:8765"

def check_ocr_server():
    """
    Check if the OCR server is running and healthy.
    
    Returns:
        bool: True if server is running and healthy, False otherwise
    """
    try:
        request = urllib.request.Request(f"{OCR_SERVER_URL}/health")
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('status') == 'ok'
    except Exception:
        return False

def recognize_text(image_data_url):
    """
    Send image to OCR server and get recognized text.
    
    Args:
        image_data_url (str): Base64 encoded image data (with or without data URL prefix)
    
    Returns:
        dict: {
            'success': bool,
            'text': str,  # Combined recognized text
            'details': list,  # Detailed results with confidence scores
            'error': str  # Error message if success is False
        }
    """
    try:
        # Prepare the request payload
        payload = {
            'image': image_data_url
        }
        
        # Make HTTP request to OCR server
        request = urllib.request.Request(
            f"{OCR_SERVER_URL}/ocr",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    
    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': f'Cannot connect to OCR server. Make sure it is running at {OCR_SERVER_URL}',
            'text': '',
            'details': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'text': '',
            'details': []
        }

def get_server_status():
    """
    Get the OCR server status.
    
    Returns:
        dict: Server status information or error
    """
    try:
        request = urllib.request.Request(f"{OCR_SERVER_URL}/health")
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
