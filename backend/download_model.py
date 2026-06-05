import os
from transformers import AutoTokenizer, AutoModelForTokenClassification

# Create models directory
os.makedirs('assets/models', exist_ok=True)

# Download pre-trained NER model
model_name = "distilbert-base-uncased-finetuned-conll03-english"
print(f"Downloading model {model_name} to assets/models/distilbert-ner")

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)

# Save locally (fallback if ONNX not available)
model.save_pretrained('assets/models/distilbert-ner')
tokenizer.save_pretrained('assets/models/distilbert-ner')

print("✓ Model downloaded successfully")
print(f"Model location: assets/models/distilbert-ner")
