import os
import shutil
import sys
import time

import onnxruntime as ort
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer


MODEL_NAME = "elastic/distilbert-base-uncased-finetuned-conll03-english"
PYTORCH_DIR = "assets/models/distilbert-ner"
ONNX_PATH = "assets/models/distilbert-ner.onnx"
INT8_PATH = "assets/models/distilbert-ner-int8.onnx"
ROOT_ONNX_PATH = "../assets/models/distilbert-ner.onnx"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class DistilBertOnnxWrapper(torch.nn.Module):
    """Expose token_type_ids in the ONNX schema while DistilBERT ignores it."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask, token_type_ids):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        keep_token_type_ids = token_type_ids.to(dtype=logits.dtype).sum() * 0.0
        return logits + keep_token_type_ids


def directory_size_mb(path):
    total_bytes = 0
    for root, _, files in os.walk(path):
        for filename in files:
            total_bytes += os.path.getsize(os.path.join(root, filename))
    return total_bytes / (1024 * 1024)


def file_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)


def verify_onnx_model(path):
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    dummy_inputs = {
        "input_ids": torch.ones((1, 128), dtype=torch.long).numpy(),
        "attention_mask": torch.ones((1, 128), dtype=torch.long).numpy(),
        "token_type_ids": torch.zeros((1, 128), dtype=torch.long).numpy(),
    }
    expected_names = [inp.name for inp in session.get_inputs()]
    input_feed = {name: dummy_inputs[name] for name in expected_names if name in dummy_inputs}

    start = time.perf_counter()
    session.run(None, input_feed)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


def main():
    os.makedirs("assets/models", exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
    model.eval()

    tokenizer.save_pretrained(PYTORCH_DIR)
    model.save_pretrained(PYTORCH_DIR)
    print(f"✓ PyTorch model downloaded: {PYTORCH_DIR}")

    try:
        wrapper = DistilBertOnnxWrapper(model)
        wrapper.eval()

        dummy_input_ids = torch.ones((1, 128), dtype=torch.long)
        dummy_attention_mask = torch.ones((1, 128), dtype=torch.long)
        dummy_token_type_ids = torch.zeros((1, 128), dtype=torch.long)

        torch.onnx.export(
            wrapper,
            (dummy_input_ids, dummy_attention_mask, dummy_token_type_ids),
            ONNX_PATH,
            input_names=["input_ids", "attention_mask", "token_type_ids"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq_len"},
                "attention_mask": {0: "batch", 1: "seq_len"},
                "token_type_ids": {0: "batch", 1: "seq_len"},
                "logits": {0: "batch", 1: "seq_len"},
            },
            opset_version=13,
        )
        print(f"✓ ONNX exported: {ONNX_PATH}")
    except Exception as exc:
        print(f"✗ ONNX export failed: {exc}")
        sys.exit(1)

    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(
            model_input=ONNX_PATH,
            model_output=INT8_PATH,
            weight_type=QuantType.QInt8,
        )
        shutil.move(INT8_PATH, ONNX_PATH)
        os.makedirs(os.path.dirname(ROOT_ONNX_PATH), exist_ok=True)
        shutil.copy2(ONNX_PATH, ROOT_ONNX_PATH)
        print("✓ INT8 quantization complete")
    except Exception as exc:
        print(f"✗ INT8 quantization failed: {exc}")
        sys.exit(1)

    try:
        elapsed_ms = verify_onnx_model(ONNX_PATH)
        pytorch_size = directory_size_mb(PYTORCH_DIR)
        onnx_size = file_size_mb(ONNX_PATH)
        print(f"✓ Verification inference: PASS  ({elapsed_ms:.0f}ms)")
        print(f"PyTorch size: {pytorch_size:.1f} MB  |  ONNX size: {onnx_size:.1f} MB")
        print("✓ ONNX export + quantization complete")
    except Exception as exc:
        print(f"✗ Verification inference failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
