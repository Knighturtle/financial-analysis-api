
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify():
    print("1. Checking Imports...")
    try:
        import torch
        import transformers
        print(f"   Success: torch {torch.__version__}, transformers {transformers.__version__}")
    except ImportError as e:
        print(f"   FAIL: Missing dependency: {e}")
        return

    try:
        import bitsandbytes
        print(f"   Success: bitsandbytes {bitsandbytes.__version__}")
    except ImportError as e:
        print(f"   WARNING: bitsandbytes not found (GPU 4-bit load will fail). {e}")

    print("\n2. Checking ModelManager (Lazy Load FinBERT)...")
    try:
        from engine.models import ModelManager
        mm = ModelManager()
        print(f"   ModelManager initialized on {mm.device}")
        
        print("   Loading FinBERT...")
        fb = mm.get_finbert()
        
        test_text = "There is a risk of significant loss due to market volatility."
        res = fb(test_text)
        print(f"   FinBERT Inference Result: {res}")
        print("   Success: FinBERT loaded and ran.")
        
    except Exception as e:
        print(f"   FAIL: ModelManager error: {e}")
        return

    print("\nVerification Complete. (Skipping Heavy LLM load)")

if __name__ == "__main__":
    verify()
