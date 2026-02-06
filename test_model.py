"""
Test trained handwriting recognition model
"""

import numpy as np
import json
import os
from tensorflow import keras
from data_prep import load_dataset, decode_image, preprocess_image


def load_latest_model():
    """Load the most recently trained model."""
    # Look for timestamped models
    model_files = [f for f in os.listdir('.') if f.startswith('handwriting_model_') and f.endswith('.keras')]
    
    if not model_files:
        # Try best_model.keras
        if os.path.exists('best_model.keras'):
            return 'best_model.keras'
        raise FileNotFoundError("No trained model found. Run train_model.py first.")
    
    # Get most recent
    latest_model = sorted(model_files)[-1]
    return latest_model


def load_char_mappings(model_name):
    """Load character mappings for a model."""
    # Extract timestamp from model name
    if 'handwriting_model_' in model_name:
        timestamp = model_name.replace('handwriting_model_', '').replace('.keras', '')
        mapping_file = f'char_mappings_{timestamp}.json'
    else:
        # Look for any mapping file
        mapping_files = [f for f in os.listdir('.') if f.startswith('char_mappings_')]
        if mapping_files:
            mapping_file = sorted(mapping_files)[-1]
        else:
            raise FileNotFoundError("No character mappings found!")
    
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mappings = json.load(f)
    
    char_to_idx = mappings['char_to_idx']
    idx_to_char = {int(k): v for k, v in mappings['idx_to_char'].items()}
    
    return char_to_idx, idx_to_char, mappings


def predict_image(model, img_array, idx_to_char, top_k=5):
    """
    Predict character from image array.
    
    Returns:
        List of (character, confidence) tuples
    """
    # Add batch dimension if needed
    if len(img_array.shape) == 3:
        img_array = np.expand_dims(img_array, axis=0)
    
    # Predict
    predictions = model.predict(img_array, verbose=0)[0]
    
    # Get top K predictions
    top_indices = np.argsort(predictions)[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        char = idx_to_char[idx]
        confidence = predictions[idx]
        results.append((char, confidence))
    
    return results


def test_on_dataset(model, dataset, char_to_idx, idx_to_char):
    """Test model on all samples in dataset."""
    print("\n" + "="*60)
    print("TESTING MODEL ON DATASET")
    print("="*60)
    
    correct = 0
    total = 0
    per_char_accuracy = {}
    
    for true_char, samples in dataset.items():
        if true_char not in char_to_idx:
            continue  # Skip characters not in training set
        
        char_correct = 0
        char_total = 0
        
        for sample in samples:
            try:
                # Preprocess
                img = decode_image(sample['image'])
                img_array = preprocess_image(img, target_size=(64, 64))
                
                # Predict
                predictions = predict_image(model, img_array, idx_to_char, top_k=1)
                predicted_char = predictions[0][0]
                
                # Check if correct
                if predicted_char == true_char:
                    correct += 1
                    char_correct += 1
                
                total += 1
                char_total += 1
                
            except Exception as e:
                print(f"Error testing sample: {e}")
                continue
        
        if char_total > 0:
            per_char_accuracy[true_char] = (char_correct / char_total) * 100
    
    # Print results
    overall_accuracy = (correct / total * 100) if total > 0 else 0
    
    print(f"\nOverall Accuracy: {overall_accuracy:.2f}% ({correct}/{total})")
    print("\nPer-Character Accuracy:")
    print("-" * 40)
    
    for char in sorted(per_char_accuracy.keys()):
        acc = per_char_accuracy[char]
        print(f"  {char}: {acc:.1f}%")
    
    print("="*60)
    
    return overall_accuracy, per_char_accuracy


def interactive_test(model, idx_to_char):
    """Interactive testing mode."""
    print("\n" + "="*60)
    print("INTERACTIVE TESTING")
    print("="*60)
    print("Enter the path to an image file to test")
    print("Or type 'quit' to exit")
    print("="*60)
    
    while True:
        img_path = input("\nImage path: ").strip()
        
        if img_path.lower() in ['quit', 'exit', 'q']:
            break
        
        if not os.path.exists(img_path):
            print(f"File not found: {img_path}")
            continue
        
        try:
            from PIL import Image
            img = Image.open(img_path)
            img_array = preprocess_image(img, target_size=(64, 64))
            
            # Predict
            predictions = predict_image(model, img_array, idx_to_char, top_k=5)
            
            print("\nTop 5 Predictions:")
            print("-" * 40)
            for char, confidence in predictions:
                print(f"  {char}: {confidence*100:.2f}%")
            
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main testing function."""
    # Load model
    print("Loading model...")
    model_file = load_latest_model()
    print(f"Found model: {model_file}")
    
    model = keras.models.load_model(model_file)
    
    # Load mappings
    char_to_idx, idx_to_char, mappings = load_char_mappings(model_file)
    print(f"Model recognizes {len(char_to_idx)} characters")
    print(f"Trained on: {mappings.get('trained_on', 'unknown')}")
    
    # Load dataset
    dataset = load_dataset()
    
    # Test on dataset
    test_on_dataset(model, dataset, char_to_idx, idx_to_char)
    
    # Interactive mode
    response = input("\nEnter interactive testing mode? (y/n): ").strip().lower()
    if response == 'y':
        interactive_test(model, idx_to_char)


if __name__ == "__main__":
    main()
