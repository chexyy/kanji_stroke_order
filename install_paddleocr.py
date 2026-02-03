# Install PaddleOCR for Anki
# This script installs PaddleOCR into Anki's bundled Python environment

import subprocess
import sys
import os

def install_paddleocr():
    """Install PaddleOCR into Anki's Python environment."""
    
    # Get Anki's Python executable
    python_exe = sys.executable
    print(f"Using Python: {python_exe}")
    print(f"Python version: {sys.version}")
    
    # Install PaddleOCR and PaddlePaddle
    print("\n" + "="*60)
    print("Installing PaddlePaddle and PaddleOCR...")
    print("="*60 + "\n")
    
    try:
        # Install PaddlePaddle first (backend)
        print("Step 1/2: Installing PaddlePaddle...")
        subprocess.check_call([
            python_exe, 
            "-m", 
            "pip", 
            "install", 
            "paddlepaddle",
            "--upgrade"
        ])
        
        # Then install PaddleOCR
        print("\nStep 2/2: Installing PaddleOCR...")
        subprocess.check_call([
            python_exe, 
            "-m", 
            "pip", 
            "install", 
            "paddleocr",
            "--upgrade"
        ])
        print("\n" + "="*60)
        print("✓ PaddleOCR installed successfully!")
        print("="*60)
        print("\nPlease restart Anki for changes to take effect.")
        
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print("✗ Installation failed!")
        print("="*60)
        print(f"\nError: {e}")
        print("\nTry installing manually:")
        print(f'  {python_exe} -m pip install paddleocr')
        
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

if __name__ == "__main__":
    install_paddleocr()
