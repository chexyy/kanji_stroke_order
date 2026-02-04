# PaddleOCR Server Setup Guide

This guide explains how to set up and use the separate PaddleOCR server for handwriting recognition in the Kanji Stroke Order Anki plugin.

## Why a Separate Server?

Running PaddleOCR in a separate process avoids dependency conflicts with Anki's Python environment and allows for easier updates and maintenance.

## Installation

### 1. Create a Virtual Environment (Recommended)

Open a terminal in the addon directory and run:

```bash
# Create virtual environment
python -m venv ocr_env

# Activate it
# On Windows:
ocr_env\Scripts\activate
# On macOS/Linux:
source ocr_env/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r ocr_server_requirements.txt
```

This will install:
- Flask (web server)
- Flask-CORS (for Anki communication)
- PaddleOCR (OCR engine)
- PaddlePaddle (ML framework)
- Pillow (image processing)
- NumPy (array operations)

**Note:** The installation may take several minutes as PaddlePaddle is a large package (~200MB).

### 3. Download OCR Models

PaddleOCR will automatically download the Japanese recognition models (~20MB) on first use. This may take a minute or two.

## Running the Server

### Option 1: Using the Batch File (Windows)

Simply double-click `start_ocr_server.bat`

### Option 2: Manual Start

```bash
# Activate virtual environment first (if using one)
ocr_env\Scripts\activate  # Windows
# or
source ocr_env/bin/activate  # macOS/Linux

# Start the server
python ocr_server.py
```

The server will start on `http://localhost:8765`

You should see output like:
```
Starting PaddleOCR server on http://localhost:8765
Press Ctrl+C to stop
```

## Using with Anki

1. **Start the OCR server** before opening Anki (or use the in-plugin server status check)
2. **In Anki**, the plugin will automatically detect if the OCR server is running
3. **Draw kanji** in the practice window
4. **Click "Recognize"** to send the drawing to the OCR server
5. The recognized text will be inserted into the answer box

## Testing the Server

You can test if the server is running by opening this URL in your browser:
```
http://localhost:8765/health
```

You should see:
```json
{
  "status": "ok",
  "service": "paddleocr-server",
  "ocr_initialized": false
}
```

## Troubleshooting

### Server won't start

**Error: `ModuleNotFoundError: No module named 'flask'`**
- Make sure you installed the requirements: `pip install -r ocr_server_requirements.txt`
- Make sure you activated the virtual environment if using one

**Error: `Address already in use`**
- Port 8765 is already in use. Either:
  - Kill the existing process using that port
  - Change the port in `ocr_server.py` (and update `ocr_client.py` accordingly)

### OCR not working

**"Cannot connect to OCR server"**
- Make sure the server is running (`python ocr_server.py`)
- Check that nothing is blocking localhost:8765 (firewall, antivirus)

**OCR returns empty text**
- The image might be unclear or too small
- Try drawing larger, clearer strokes
- PaddleOCR works best with clear, high-contrast images

### Slow performance

**First OCR request is slow**
- This is normal - PaddleOCR loads models on first use
- Subsequent requests will be much faster

**All requests are slow**
- Consider enabling GPU support if you have a NVIDIA GPU:
  - Install CUDA and cuDNN
  - Install GPU version of PaddlePaddle
  - Set `use_gpu=True` in `ocr_server.py`

## Advanced Configuration

### Changing the Port

Edit `ocr_server.py`, line at the bottom:
```python
app.run(host='localhost', port=8765, debug=False)
```

Also update `ocr_client.py`:
```python
OCR_SERVER_URL = "http://localhost:8765"
```

### Enabling GPU Support

Edit `ocr_server.py`, in the `init_ocr()` function:
```python
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='japan',
    show_log=False,
    use_gpu=True  # Change this to True
)
```

### Running as a Background Service

For production use, consider running the server as a Windows service or Linux daemon:

**Windows (using NSSM):**
```bash
nssm install PaddleOCRServer "C:\path\to\ocr_env\Scripts\python.exe" "C:\path\to\ocr_server.py"
nssm start PaddleOCRServer
```

**Linux (using systemd):**
Create `/etc/systemd/system/paddleocr.service`

## API Reference

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "paddleocr-server",
  "ocr_initialized": true
}
```

### POST /ocr
Perform OCR on an image.

**Request:**
```json
{
  "image": "base64_encoded_image_data"
}
```

**Response:**
```json
{
  "success": true,
  "text": "認識されたテキスト",
  "details": [
    {
      "text": "認識されたテキスト",
      "confidence": 0.95,
      "bbox": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    }
  ]
}
```

## License

This OCR server uses PaddleOCR, which is licensed under Apache License 2.0.
