"""
Train handwriting recognition model
"""

import numpy as np
import json
import os
from datetime import datetime

# TensorFlow imports
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split

from data_prep import load_dataset, prepare_training_data, get_dataset_stats, print_stats


def create_model(num_classes, input_shape=(64, 64, 1)):
    """
    Create a lightweight CNN model for handwriting recognition.
    
    Args:
        num_classes: Number of character classes
        input_shape: Input image shape (height, width, channels)
    
    Returns:
        Compiled Keras model
    """
    model = keras.Sequential([
        # First convolutional block
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=input_shape),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),
        
        # Second convolutional block
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),
        
        # Third convolutional block (optional, comment out for faster training)
        layers.Conv2D(128, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),
        
        # Flatten and dense layers
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(num_classes, activation='softmax')
    ])
    
    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model


def create_data_augmentation():
    """Create data augmentation pipeline."""
    return keras.Sequential([
        layers.RandomRotation(0.1),  # Rotate ±10%
        layers.RandomTranslation(0.1, 0.1),  # Shift ±10%
        layers.RandomZoom(0.1),  # Zoom ±10%
    ])


def train_model(dataset_file="handwriting_dataset.json", 
                epochs=100, 
                batch_size=16,
                validation_split=0.2,
                min_samples=2,
                use_augmentation=True):
    """
    Train the handwriting recognition model.
    
    Args:
        dataset_file: Path to dataset JSON
        epochs: Number of training epochs
        batch_size: Batch size
        validation_split: Fraction of data for validation
        min_samples: Minimum samples per character
        use_augmentation: Whether to use data augmentation
    
    Returns:
        model, history, char_to_idx, idx_to_char
    """
    print("Loading dataset...")
    dataset = load_dataset(dataset_file)
    
    # Show statistics
    stats = get_dataset_stats(dataset)
    print_stats(stats)
    
    # Check if we have enough data
    if stats['total_samples'] < 10:
        print("WARNING: Very few samples! Collect more data for better results.")
        print("Recommended: At least 10-20 samples per character, 50+ total.")
    
    # Prepare data
    print("Preparing training data...")
    X, y, char_to_idx, idx_to_char = prepare_training_data(
        dataset, 
        target_size=(64, 64),
        min_samples=min_samples
    )
    
    num_classes = len(char_to_idx)
    
    if num_classes < 2:
        raise ValueError("Need at least 2 different characters to train!")
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=validation_split, random_state=42, stratify=y
    )
    
    print(f"\nTraining samples: {len(X_train)}")
    print(f"Validation samples: {len(X_val)}")
    
    # Create model
    print(f"\nCreating model for {num_classes} classes...")
    model = create_model(num_classes, input_shape=(64, 64, 1))
    model.summary()
    
    # Create data augmentation
    if use_augmentation:
        print("\nUsing data augmentation")
        data_augmentation = create_data_augmentation()
        
        # Apply augmentation to training data
        X_train_aug = data_augmentation(X_train, training=True)
    else:
        X_train_aug = X_train
    
    # Callbacks
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=15,
            restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        ),
        keras.callbacks.ModelCheckpoint(
            'best_model.keras',
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1
        )
    ]
    
    # Train model
    print(f"\nTraining for {epochs} epochs...")
    print("This may take 5-15 minutes depending on your hardware.\n")
    
    history = model.fit(
        X_train_aug, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1
    )
    
    # Evaluate
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    val_loss, val_accuracy = model.evaluate(X_val, y_val, verbose=0)
    print(f"Final Validation Loss: {val_loss:.4f}")
    print(f"Final Validation Accuracy: {val_accuracy*100:.2f}%")
    
    # Save model and mappings
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_file = f"handwriting_model_{timestamp}.keras"
    mapping_file = f"char_mappings_{timestamp}.json"
    
    model.save(model_file)
    print(f"\nModel saved to: {model_file}")
    
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump({
            'char_to_idx': char_to_idx,
            'idx_to_char': {str(k): v for k, v in idx_to_char.items()},
            'num_classes': num_classes,
            'input_shape': [64, 64, 1],
            'trained_on': timestamp
        }, f, ensure_ascii=False, indent=2)
    
    print(f"Character mappings saved to: {mapping_file}")
    print("="*60)
    
    return model, history, char_to_idx, idx_to_char


def test_prediction(model, dataset, char_to_idx, idx_to_char, character=None):
    """Test model prediction on a sample."""
    from data_prep import decode_image, preprocess_image
    
    if character is None:
        character = list(dataset.keys())[0]
    
    if character not in dataset:
        print(f"Character '{character}' not in dataset!")
        return
    
    sample = dataset[character][0]
    img = decode_image(sample['image'])
    img_array = preprocess_image(img, target_size=(64, 64))
    
    # Predict
    img_batch = np.expand_dims(img_array, axis=0)
    predictions = model.predict(img_batch, verbose=0)[0]
    
    # Get top 5 predictions
    top_indices = np.argsort(predictions)[-5:][::-1]
    
    print(f"\nPredictions for character '{character}':")
    print("-" * 40)
    for idx in top_indices:
        char = idx_to_char[idx]
        confidence = predictions[idx] * 100
        marker = "✓" if char == character else " "
        print(f"{marker} {char}: {confidence:.2f}%")


if __name__ == "__main__":
    # Check if dataset exists
    if not os.path.exists("handwriting_dataset.json"):
        print("ERROR: handwriting_dataset.json not found!")
        print("Collect training data first by practicing kanji in Anki.")
        exit(1)
    
    # Train model
    model, history, char_to_idx, idx_to_char = train_model(
        epochs=100,
        batch_size=16,
        validation_split=0.2,
        min_samples=2,
        use_augmentation=True
    )
    
    # Test prediction
    dataset = load_dataset()
    test_char = list(dataset.keys())[0]
    test_prediction(model, dataset, char_to_idx, idx_to_char, test_char)
    
    print("\n" + "="*60)
    print("Next steps:")
    print("1. Test the model with: python test_model.py")
    print("2. Integrate into OCR server for live recognition")
    print("3. Collect more samples and retrain for better accuracy")
    print("="*60)
