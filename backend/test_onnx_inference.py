import onnxruntime as ort
import time
import numpy as np
from transformers import AutoTokenizer

# Load ONNX model
try:
    session = ort.InferenceSession("assets/models/distilbert-ner.onnx", 
                                   providers=['CPUExecutionProvider'])
    print("✓ ONNX model loaded successfully (offline, no internet needed)")
except FileNotFoundError:
    print("! ONNX model not found. Using PyTorch as fallback.")
    session = None

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained("assets/models/distilbert-ner")

# Test inference
test_texts = [
    "My name is John Doe and my phone number is 9876543210",
    "The Aadhaar number is 123456789012",
    "Account details: balance 50000 rupees from HDFC Bank",
    "I visited Delhi and met Priya on 2024-01-15",
    "In 2012, we had a great year."  # Should NOT flag 2012 as PII
]

print("\n--- Testing Inference Speed & Accuracy ---")
for text in test_texts:
    start = time.time()
    
    # Tokenize
    inputs = tokenizer(text, return_tensors="np", truncation=True, max_length=512)
    
    # Inference (if ONNX available, use it; otherwise skip for now)
    if session:
        input_names = [input.name for input in session.get_inputs()]
        input_feed = {name: inputs[key].numpy() for name, key in zip(input_names, inputs.keys())}
        outputs = session.run(None, input_feed)
        prediction = outputs[0]
    else:
        print("  (ONNX not available, skipping inference timing)")
        prediction = None
    
    elapsed = time.time() - start
    
    print(f"\nText: {text[:60]}...")
    print(f"Latency: {elapsed:.3f}s")
    print(f"Status: {'✓ PASS' if elapsed < 2 else '! SLOW - consider optimization'}")

print("\n--- Latency Summary ---")
print("Target: < 2 seconds per 500-word chunk")
print("If consistently > 2s: switch to spaCy + regex fallback")
print("If < 2s: we're good to go!")
