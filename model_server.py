"""
Custom Handwriting Model Server
Runs the trained TensorFlow model as a separate HTTP server
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import json
import os
import sys
from io import BytesIO

app = Flask(__name__)
CORS(app)

# Global model and mappings
model = None
char_mappings = None
model_path = None


def get_latest_model_path():
    """Find the most recent trained model file."""
    # Check in multiple possible locations
    possible_dirs = [
        os.path.dirname(__file__),  # Script directory
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Anki2", "addons21", "kanji_stroke_order"),
        "."
    ]
    
    for directory in possible_dirs:
        if not os.path.exists(directory):
            continue
            
        model_files = [f for f in os.listdir(directory) 
                      if f.startswith('handwriting_model_') and f.endswith('.keras')]
        
        if model_files:
            latest_model = sorted(model_files)[-1]
            return os.path.join(directory, latest_model)
        
        # Try best_model.keras
        best_model = os.path.join(directory, 'best_model.keras')
        if os.path.exists(best_model):
            return best_model
    
    return None


def load_model():
    """Load the custom handwriting recognition model."""
    global model, char_mappings, model_path
    
    try:
        import tensorflow as tf
        import numpy as np
        from PIL import Image
        
        model_path = get_latest_model_path()
        if not model_path:
            print("ERROR: No trained model found")
            return False
        
        print(f"Loading model from: {model_path}")
        
        # Load character mappings
        model_dir = os.path.dirname(model_path)
        if 'handwriting_model_' in model_path:
            timestamp = os.path.basename(model_path).replace('handwriting_model_', '').replace('.keras', '')
            mapping_file = os.path.join(model_dir, f'char_mappings_{timestamp}.json')
        else:
            # Look for any mapping file
            mapping_files = [f for f in os.listdir(model_dir) 
                           if f.startswith('char_mappings_') and f.endswith('.json')]
            if not mapping_files:
                print("ERROR: No character mappings found")
                return False
            mapping_file = os.path.join(model_dir, sorted(mapping_files)[-1])
        
        print(f"Loading mappings from: {mapping_file}")
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            char_mappings = json.load(f)
        
        # Load model
        model = tf.keras.models.load_model(model_path)
        
        print(f"Model loaded successfully!")
        print(f"Recognizes {len(char_mappings['char_to_idx'])} characters")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Required dependency not installed: {e}")
        print("Install with: pip install tensorflow numpy pillow")
        return False
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False


def predict_character(image_data_base64):
    """
    Predict character from base64 image.
    
    Returns:
        dict with 'character', 'confidence', and 'alternatives'
    """
    global model, char_mappings
    
    if model is None:
        return None
    
    try:
        import numpy as np
        from PIL import Image
        
        # Remove data URL prefix if present
        if ',' in image_data_base64:
            image_data_base64 = image_data_base64.split(',', 1)[1]
        
        # Decode image
        image_data = base64.b64decode(image_data_base64)
        img = Image.open(BytesIO(image_data))
        
        # Preprocess image (same as training)
        if img.mode != 'L':
            img = img.convert('L')
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = 1.0 - img_array  # Invert colors
        img_array = np.expand_dims(img_array, axis=-1)
        img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension
        
        # Predict
        predictions = model.predict(img_array, verbose=0)[0]
        
        # Get top 5 predictions
        idx_to_char = {int(k): v for k, v in char_mappings['idx_to_char'].items()}
        top_indices = np.argsort(predictions)[-5:][::-1]
        
        results = []
        for idx in top_indices:
            char = idx_to_char[idx]
            confidence = float(predictions[idx])
            results.append({'character': char, 'confidence': confidence})
        
        if results:
            return {
                'character': results[0]['character'],
                'confidence': results[0]['confidence'],
                'alternatives': results[1:]
            }
        
        return None
        
    except Exception as e:
        print(f"ERROR in prediction: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'running',
        'model_loaded': model is not None,
        'model_path': model_path,
        'num_characters': len(char_mappings['char_to_idx']) if char_mappings else 0
    })


@app.route('/predict', methods=['POST'])
def predict():
    """Prediction endpoint."""
    try:
        data = request.get_json()
        
        if not data or 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400
        
        image_data = data['image']
        
        # Predict
        result = predict_character(image_data)
        
        if result:
            print(f"Predicted: '{result['character']}' (confidence: {result['confidence']:.2f})")
            return jsonify(result)
        else:
            return jsonify({'error': 'Prediction failed'}), 500
            
    except Exception as e:
        print(f"ERROR in /predict: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def main():
    """Main function to start the server."""
    print("="*60)
    print("Custom Handwriting Model Server")
    print("="*60)
    
    # Load model
    if not load_model():
        print("\nFailed to load model. Exiting.")
        sys.exit(1)
    
    # Start server
    print("\n" + "="*60)
    print("Server starting on http://localhost:8766")
    print("="*60)
    print("\nEndpoints:")
    print("  GET  /health  - Health check")
    print("  POST /predict - Character prediction")
    print("\nPress Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='localhost', port=8766, debug=False)


if __name__ == '__main__':
    main()
