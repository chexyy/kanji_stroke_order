"""
Handwriting Dataset Viewer
Displays collected handwriting samples from handwriting_dataset.json
"""

import json
import base64
from io import BytesIO
from PIL import Image
import os

DATASET_FILE = "handwriting_dataset.json"


def load_dataset():
    """Load the handwriting dataset from JSON file."""
    if not os.path.exists(DATASET_FILE):
        print(f"Dataset file not found: {DATASET_FILE}")
        return {}
    
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def decode_image(base64_string):
    """Decode base64 image string to PIL Image."""
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]
    
    image_data = base64.b64decode(base64_string)
    return Image.open(BytesIO(image_data))


def display_dataset_summary(dataset):
    """Display summary statistics of the dataset."""
    print("\n" + "="*60)
    print("HANDWRITING DATASET SUMMARY")
    print("="*60)
    
    total_samples = sum(len(samples) for samples in dataset.values())
    print(f"\nTotal Characters: {len(dataset)}")
    print(f"Total Samples: {total_samples}")
    print(f"Average Samples per Character: {total_samples / len(dataset):.1f}" if dataset else 0)
    
    print("\n" + "-"*60)
    print("Samples per Character:")
    print("-"*60)
    
    # Sort by number of samples (descending)
    sorted_chars = sorted(dataset.items(), key=lambda x: len(x[1]), reverse=True)
    
    for char, samples in sorted_chars:
        print(f"  {char}: {len(samples)} samples")
    
    print("="*60)


def view_character_samples(dataset, character):
    """View all samples for a specific character."""
    if character not in dataset:
        print(f"\nNo samples found for character: {character}")
        return
    
    samples = dataset[character]
    print(f"\n{'='*60}")
    print(f"Character: {character} ({len(samples)} samples)")
    print(f"{'='*60}")
    
    # Create sample directory structure
    sample_dir = os.path.join("sample", character)
    os.makedirs(sample_dir, exist_ok=True)
    
    for i, sample in enumerate(samples, 1):
        print(f"\nSample {i}:")
        print(f"  Timestamp: {sample['timestamp']}")
        print(f"  Strokes: {len(sample['strokes'])}")
        
        # Decode and display image
        try:
            img = decode_image(sample['image'])
            print(f"  Image Size: {img.size}")
            
            # Save to sample folder
            sample_file = os.path.join(sample_dir, f"sample_{i}.png")
            img.save(sample_file)
            print(f"  Saved to: {sample_file}")
            
        except Exception as e:
            print(f"  Error displaying image: {e}")


def create_character_grid(dataset, character, output_file=None):
    """Create a grid image showing all samples for a character."""
    if character not in dataset:
        print(f"\nNo samples found for character: {character}")
        return
    
    samples = dataset[character]
    num_samples = len(samples)
    
    # Calculate grid dimensions (try to make it roughly square)
    cols = min(5, num_samples)  # Max 5 columns
    rows = (num_samples + cols - 1) // cols
    
    # Sample size
    sample_size = 300  # Original size
    padding = 10
    
    # Create grid image
    grid_width = cols * (sample_size + padding) + padding
    grid_height = rows * (sample_size + padding) + padding
    grid = Image.new('RGB', (grid_width, grid_height), 'white')
    
    print(f"\nCreating grid for '{character}' ({num_samples} samples)...")
    print(f"Grid size: {cols}x{rows}")
    
    for i, sample in enumerate(samples):
        try:
            img = decode_image(sample['image'])
            
            # Calculate position
            row = i // cols
            col = i % cols
            x = padding + col * (sample_size + padding)
            y = padding + row * (sample_size + padding)
            
            # Paste image
            grid.paste(img, (x, y))
            
        except Exception as e:
            print(f"Error processing sample {i+1}: {e}")
    
    # Save grid
    if output_file is None:
        output_file = f"grid_{character}.png"
    
    grid.save(output_file)
    print(f"Grid saved to: {output_file}")
    
    # Try to open
    try:
        os.startfile(output_file)
    except:
        print("(Could not auto-open grid)")
    
    return output_file


def export_all_grids(dataset):
    """Export grid images for all characters."""
    print("\nExporting grids for all characters...")
    
    for character in dataset.keys():
        try:
            create_character_grid(dataset, character)
        except Exception as e:
            print(f"Error creating grid for '{character}': {e}")
    
    print("\nAll grids exported!")


def interactive_menu(dataset):
    """Interactive menu for viewing dataset."""
    while True:
        print("\n" + "="*60)
        print("HANDWRITING DATASET VIEWER")
        print("="*60)
        print("\n1. Show dataset summary")
        print("2. View samples for a character")
        print("3. Create grid for a character")
        print("4. Export all grids")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            display_dataset_summary(dataset)
        
        elif choice == '2':
            char = input("Enter character to view: ").strip()
            view_character_samples(dataset, char)
        
        elif choice == '3':
            char = input("Enter character for grid: ").strip()
            create_character_grid(dataset, char)
        
        elif choice == '4':
            confirm = input("This will create grid images for all characters. Continue? (y/n): ")
            if confirm.lower() == 'y':
                export_all_grids(dataset)
        
        elif choice == '5':
            print("\nExiting...")
            break
        
        else:
            print("\nInvalid choice. Please try again.")


def main():
    """Main function."""
    dataset = load_dataset()
    
    if not dataset:
        print("\nNo data found in dataset. Start collecting samples by practicing kanji!")
        return
    
    # Show summary by default
    display_dataset_summary(dataset)
    
    # Start interactive menu
    interactive_menu(dataset)


if __name__ == "__main__":
    main()
