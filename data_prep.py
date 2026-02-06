"""
Data preparation utilities for handwriting recognition training
"""

import json
import base64
from io import BytesIO
import numpy as np
from PIL import Image
import os


def load_dataset(dataset_file="handwriting_dataset.json"):
    """Load the handwriting dataset from JSON file."""
    if not os.path.exists(dataset_file):
        raise FileNotFoundError(f"Dataset file not found: {dataset_file}")
    
    with open(dataset_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def decode_image(base64_string):
    """Decode base64 image string to PIL Image."""
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]
    
    image_data = base64.b64decode(base64_string)
    return Image.open(BytesIO(image_data))


def preprocess_image(image, target_size=(64, 64)):
    """
    Preprocess image for model input.
    
    Args:
        image: PIL Image
        target_size: Tuple (width, height) for resizing
    
    Returns:
        numpy array of shape (height, width, 1) with values in [0, 1]
    """
    # Convert to grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # Resize
    image = image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy array and normalize
    img_array = np.array(image, dtype=np.float32)
    img_array = img_array / 255.0  # Normalize to [0, 1]
    
    # Invert colors (make strokes white on black background for better learning)
    img_array = 1.0 - img_array
    
    # Add channel dimension
    img_array = np.expand_dims(img_array, axis=-1)
    
    return img_array


def prepare_training_data(dataset, target_size=(64, 64), min_samples=2):
    """
    Prepare training data from dataset.
    
    Args:
        dataset: Dictionary {character: [samples]}
        target_size: Image size for model input
        min_samples: Minimum samples required per character
    
    Returns:
        X: numpy array of images (N, height, width, 1)
        y: numpy array of labels (N,)
        char_to_idx: Dictionary mapping character to index
        idx_to_char: Dictionary mapping index to character
    """
    X = []
    y = []
    
    # Filter characters with enough samples
    valid_chars = {char: samples for char, samples in dataset.items() 
                   if len(samples) >= min_samples}
    
    if not valid_chars:
        raise ValueError(f"No characters have at least {min_samples} samples")
    
    # Create character to index mapping
    char_to_idx = {char: idx for idx, char in enumerate(sorted(valid_chars.keys()))}
    idx_to_char = {idx: char for char, idx in char_to_idx.items()}
    
    print(f"Processing {len(valid_chars)} characters with {min_samples}+ samples...")
    
    # Process each character
    for char, samples in valid_chars.items():
        char_idx = char_to_idx[char]
        
        for sample in samples:
            try:
                # Decode and preprocess image
                img = decode_image(sample['image'])
                img_array = preprocess_image(img, target_size)
                
                X.append(img_array)
                y.append(char_idx)
                
            except Exception as e:
                print(f"Error processing sample for '{char}': {e}")
                continue
    
    # Convert to numpy arrays
    X = np.array(X)
    y = np.array(y)
    
    print(f"Prepared {len(X)} samples for {len(char_to_idx)} characters")
    print(f"Image shape: {X.shape}")
    print(f"Labels shape: {y.shape}")
    
    return X, y, char_to_idx, idx_to_char


def get_dataset_stats(dataset):
    """Get statistics about the dataset."""
    total_samples = sum(len(samples) for samples in dataset.values())
    
    stats = {
        'total_characters': len(dataset),
        'total_samples': total_samples,
        'avg_samples_per_char': total_samples / len(dataset) if dataset else 0,
        'min_samples': min(len(samples) for samples in dataset.values()) if dataset else 0,
        'max_samples': max(len(samples) for samples in dataset.values()) if dataset else 0,
        'samples_per_char': {char: len(samples) for char, samples in dataset.items()}
    }
    
    return stats


def print_stats(stats):
    """Print dataset statistics."""
    print("\n" + "="*60)
    print("DATASET STATISTICS")
    print("="*60)
    print(f"Total Characters: {stats['total_characters']}")
    print(f"Total Samples: {stats['total_samples']}")
    print(f"Average Samples/Char: {stats['avg_samples_per_char']:.1f}")
    print(f"Min Samples: {stats['min_samples']}")
    print(f"Max Samples: {stats['max_samples']}")
    print("\nSamples per Character:")
    for char, count in sorted(stats['samples_per_char'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {char}: {count}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Test data preparation
    dataset = load_dataset()
    stats = get_dataset_stats(dataset)
    print_stats(stats)
    
    # Prepare training data
    X, y, char_to_idx, idx_to_char = prepare_training_data(dataset, min_samples=1)
    
    print(f"\nCharacter mapping:")
    for char, idx in sorted(char_to_idx.items()):
        print(f"  {char} → {idx}")
