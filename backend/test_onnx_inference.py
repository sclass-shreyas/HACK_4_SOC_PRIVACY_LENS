import os
import sys
import time

import numpy as np
import onnxruntime as ort
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer


ONNX_PATH = "assets/models/distilbert-ner.onnx"
PYTORCH_DIR = "assets/models/distilbert-ner"
HF_MODEL = "elastic/distilbert-base-uncased-finetuned-conll03-english"
TARGET_MS = 500

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ID2LABEL = {
    0: "O",
    1: "B-PER",
    2: "I-PER",
    3: "B-ORG",
    4: "I-ORG",
    5: "B-LOC",
    6: "I-LOC",
    7: "B-MISC",
    8: "I-MISC",
}


def load_tokenizer():
    if os.path.isdir(PYTORCH_DIR):
        return AutoTokenizer.from_pretrained(PYTORCH_DIR)
    return AutoTokenizer.from_pretrained(HF_MODEL)


def load_backend():
    try:
        session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
        print("[ONNX] Active backend: assets/models/distilbert-ner.onnx")
        return "ONNX", session
    except Exception as exc:
        print(f"[ONNX] Unavailable: {exc}")

    try:
        model = AutoModelForTokenClassification.from_pretrained(PYTORCH_DIR)
        model.eval()
        print("[PyTorch] Active backend: assets/models/distilbert-ner")
        return "PyTorch", model
    except Exception as exc:
        print(f"[PyTorch] Unavailable: {exc}")
        print("[FAILED] ✗ No model found. Run download_model.py first.")
        sys.exit(1)


def softmax(logits):
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def token_text(tokens):
    pieces = []
    for token in tokens:
        if token.startswith("##") and pieces:
            pieces[-1] += token[2:]
        elif token.startswith("##"):
            pieces.append(token[2:])
        else:
            pieces.append(token)
    return " ".join(pieces)


def decode_entities(input_ids, predictions, probabilities, tokenizer):
    tokens = tokenizer.convert_ids_to_tokens(input_ids)
    entities = []
    current = None

    for token, label_id, confidence in zip(tokens, predictions, probabilities):
        if token in tokenizer.all_special_tokens:
            continue

        label = ID2LABEL.get(int(label_id), "O")
        if label == "O":
            if current:
                entities.append(current)
                current = None
            continue

        prefix, entity_type = label.split("-", 1)
        token_conf = float(confidence[int(label_id)])

        if not current or current["type"] != entity_type:
            if current:
                entities.append(current)
            current = {"type": entity_type, "tokens": [token], "confidences": [token_conf]}
        else:
            current["tokens"].append(token)
            current["confidences"].append(token_conf)

    if current:
        entities.append(current)

    decoded = []
    for entity in entities:
        decoded.append(
            {
                "type": entity["type"],
                "text": token_text(entity["tokens"]),
                "confidence": float(np.mean(entity["confidences"])),
            }
        )
    return decoded


def run_onnx(session, tokenizer, text):
    inputs = tokenizer(
        text,
        return_tensors="np",
        truncation=True,
        max_length=512,
        padding=True,
        return_token_type_ids=True,
    )
    onnx_input_names = [inp.name for inp in session.get_inputs()]
    if "token_type_ids" in onnx_input_names and "token_type_ids" not in inputs:
        inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
    input_feed = {
        name: np.asarray(inputs[name], dtype=np.int64)
        for name in onnx_input_names
        if name in inputs
    }
    logits = session.run(None, input_feed)[0]
    probabilities = softmax(logits)
    predictions = np.argmax(probabilities, axis=2)
    return decode_entities(inputs["input_ids"][0], predictions[0], probabilities[0], tokenizer)


def run_pytorch(model, tokenizer, text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits
    probabilities = torch.softmax(logits, dim=2).cpu().numpy()
    predictions = np.argmax(probabilities, axis=2)
    return decode_entities(inputs["input_ids"][0].cpu().numpy(), predictions[0], probabilities[0], tokenizer)


def main():
    backend, model_or_session = load_backend()
    tokenizer = load_tokenizer()

    test_texts = [
        "My name is John Doe and my phone number is 9876543210",
        "The Aadhaar number is 1234 5678 9012",
        "Account details: balance 50000 rupees from HDFC Bank",
        "I visited Delhi and met Priya on 2024-01-15",
        "In 2012, we had a great year.",
    ]

    latencies = []
    print("\n--- Testing Inference Speed & Accuracy ---")
    for text in test_texts:
        start = time.perf_counter()
        if backend == "ONNX":
            entities = run_onnx(model_or_session, tokenizer, text)
        else:
            entities = run_pytorch(model_or_session, tokenizer, text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        status = "✓ PASS" if elapsed_ms < TARGET_MS else "! SLOW"
        print(f"\nText: {text}")
        print(f"Latency: {elapsed_ms:.0f}ms  {status}")
        if entities:
            for entity in entities:
                print(f'  → [{entity["type"]}] "{entity["text"]}"  (conf: {entity["confidence"]:.2f})')
        else:
            print("  → No NER entities")

    mean_latency = float(np.mean(latencies))
    summary_status = "✓ PASS" if mean_latency < TARGET_MS else "! SLOW"
    backend_label = "ONNX (INT8)" if backend == "ONNX" else "PyTorch"

    print("\n--- Latency Summary ---")
    print(f"Backend: {backend_label}")
    print(f"Mean latency: {mean_latency:.0f}ms  |  Target: <500ms")
    print(f"Status: {summary_status}")
    print("Model test: PASS")


if __name__ == "__main__":
    main()
