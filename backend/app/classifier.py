import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List

try:
    import numpy as np
except ImportError:
    np = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    from transformers import AutoTokenizer
except ImportError:
    AutoTokenizer = None

logger = logging.getLogger(__name__)


class PIIClassifier:
    """Regex-first PII classifier with optional ONNX/PyTorch NER fallback."""

    MAX_TOKENS = 512
    CHUNK_CHARS = 1800

    REGEX_PATTERNS = {
        "Aadhaar": r"\b\d{4}\s\d{4}\s\d{4}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CreditCard": r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b",
        "Email": r"\b[\w.-]+@[\w.-]+\.\w+\b",
        "Phone": r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b",
        "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        "BankAccount": r"\b(?:account|acct|bank_account_num)[^\d\n]{0,80}\d{8,18}\b|(?<=,)\d{8,18}(?=,[A-Z]{4}0[A-Z0-9]{6}\b)",
        "RoutingCode": r"\b(?:(?:routing(?:_code)?|ifsc)\D{0,40})?[A-Z]{4}0[A-Z0-9]{6}\b",
        "Secret": r"\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z0-9_]*\s*[:=]\s*\S+",
        "APIKey": r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b",
        "Medical": r"\b(?:patient|diagnosed|diagnosis|prescribed|prescription|hospital|doctor|dr\.|asthma|diabetes|surgery)\b",
    }

    CATEGORY_BY_TYPE = {
        "Aadhaar": "identity",
        "SSN": "identity",
        "PAN": "identity",
        "Name": "identity",
        "CreditCard": "financial",
        "BankAccount": "financial",
        "RoutingCode": "financial",
        "Email": "contact",
        "Phone": "contact",
        "Organization": "contact",
        "Location": "location",
        "Secret": "credentials",
        "APIKey": "credentials",
        "Medical": "medical",
    }

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

    ENTITY_TO_PII = {
        "PER": "Name",
        "ORG": "Organization",
        "LOC": "Location",
    }

    def __init__(self, model_path: str = "assets/models/distilbert-ner.onnx"):
        self.model_path = Path(model_path)
        self.tokenizer = None
        self.session = None
        self.pytorch_model = None
        self.backend = "regex"
        self._load_model()

    def _load_model(self):
        """Load ONNX first, PyTorch second, regex-only when model assets/deps are missing."""
        if not AutoTokenizer:
            logger.warning("Transformers unavailable. NER disabled; regex remains active.")
            return

        tokenizer_path = Path("assets/models/distilbert-ner")
        try:
            if tokenizer_path.exists():
                self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
            else:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    "elastic/distilbert-base-uncased-finetuned-conll03-english"
                )
        except Exception as exc:
            logger.warning(f"Tokenizer load failed: {exc}. NER disabled.")
            return

        if ort and np is not None and self.model_path.exists():
            try:
                self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
                self.backend = "onnx"
                logger.info("NER backend: onnx")
                return
            except Exception as exc:
                logger.warning(f"ONNX load failed: {exc}. Trying PyTorch fallback.")

        try:
            from transformers import AutoModelForTokenClassification

            if tokenizer_path.exists():
                self.pytorch_model = AutoModelForTokenClassification.from_pretrained(str(tokenizer_path))
                self.pytorch_model.eval()
                self.backend = "pytorch"
                logger.info("NER backend: pytorch")
                return
        except Exception as exc:
            logger.warning(f"PyTorch fallback unavailable: {exc}.")

        self.backend = "regex"
        logger.info("NER backend: regex")

    def classify(self, text: str) -> Dict:
        detections = self._classify_regex(text)

        if self.backend != "regex":
            for chunk_text, chunk_start in self._iter_chunks(text):
                detections.extend(self._classify_ner_chunk(chunk_text, chunk_start, text))

        detections = self._dedupe(detections)
        return {
            "detections": detections,
            "pii_types": [item["pii_type"] for item in detections],
            "confidence": [item["confidence"] for item in detections],
            "excerpts": [item["excerpt"] for item in detections],
            "categories": sorted({item["category"] for item in detections}),
            "backend": self.backend,
        }

    def _classify_regex(self, text: str) -> List[Dict]:
        detections = []
        for pii_type, pattern in self.REGEX_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if self._should_skip_regex_match(pii_type, match, text):
                    continue
                detections.append(
                    self._build_detection(
                        pii_type=pii_type,
                        method="regex",
                        confidence=0.95,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        text=text,
                    )
                )
        return detections

    def _classify_ner_chunk(self, chunk_text: str, chunk_start: int, full_text: str) -> List[Dict]:
        if not self.tokenizer or np is None:
            return []

        inputs = self.tokenizer(
            chunk_text,
            return_tensors="np" if self.backend == "onnx" else "pt",
            truncation=True,
            max_length=self.MAX_TOKENS,
            padding=True,
            return_token_type_ids=True,
            return_offsets_mapping=True,
        )
        offsets = inputs.pop("offset_mapping")

        if self.backend == "onnx":
            names = [input_meta.name for input_meta in self.session.get_inputs()]
            if "token_type_ids" in names and "token_type_ids" not in inputs:
                inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
            feed = {name: np.asarray(inputs[name], dtype=np.int64) for name in names if name in inputs}
            logits = self.session.run(None, feed)[0]
            offset_array = offsets[0]
        elif self.backend == "pytorch":
            import torch

            inputs.pop("token_type_ids", None)
            with torch.no_grad():
                logits = self.pytorch_model(**inputs).logits.cpu().numpy()
            offset_array = offsets[0].cpu().numpy()
        else:
            return []

        probs = self._softmax(logits)
        predictions = np.argmax(probs, axis=2)[0]
        return self._decode_entities(chunk_text, chunk_start, full_text, offset_array, predictions, probs[0])

    def _decode_entities(self, chunk_text, chunk_start, full_text, offsets, predictions, probs) -> List[Dict]:
        detections = []
        current = None

        for index, pred in enumerate(predictions):
            label = self.ID2LABEL.get(int(pred), "O")
            start, end = int(offsets[index][0]), int(offsets[index][1])
            if start == end:
                continue

            if label == "O":
                current = self._flush_entity(current, detections, full_text)
                continue

            prefix, entity_type = label.split("-", 1)
            pii_type = self.ENTITY_TO_PII.get(entity_type)
            if not pii_type:
                current = self._flush_entity(current, detections, full_text)
                continue

            abs_start = chunk_start + start
            abs_end = chunk_start + end
            confidence = float(probs[index][int(pred)])
            if prefix == "B" or not current or current["pii_type"] != pii_type:
                current = self._flush_entity(current, detections, full_text)
                current = {
                    "pii_type": pii_type,
                    "start": abs_start,
                    "end": abs_end,
                    "confidence": [confidence],
                }
            else:
                current["end"] = abs_end
                current["confidence"].append(confidence)

        self._flush_entity(current, detections, full_text)
        return detections

    def _flush_entity(self, entity, detections: List[Dict], text: str):
        if not entity:
            return None
        value = text[entity["start"]:entity["end"]].strip()
        if value:
            detections.append(
                self._build_detection(
                    pii_type=entity["pii_type"],
                    method="ner",
                    confidence=sum(entity["confidence"]) / len(entity["confidence"]),
                    value=value,
                    start=entity["start"],
                    end=entity["end"],
                    text=text,
                )
            )
        return None

    def _build_detection(self, pii_type, method, confidence, value, start, end, text) -> Dict:
        return {
            "pii_type": pii_type,
            "category": self.CATEGORY_BY_TYPE.get(pii_type, "other"),
            "method": method,
            "confidence": round(float(confidence), 4),
            "value": value,
            "start": start,
            "end": end,
            "excerpt": text[max(0, start - 50):min(len(text), end + 50)],
        }

    def _dedupe(self, detections: Iterable[Dict]) -> List[Dict]:
        best = {}
        for detection in detections:
            key = (detection["pii_type"], detection["value"].lower(), detection["start"], detection["end"])
            existing = best.get(key)
            if not existing or detection["confidence"] > existing["confidence"]:
                best[key] = detection
        return sorted(best.values(), key=lambda item: (item["start"], item["pii_type"]))

    def _iter_chunks(self, text: str):
        for start in range(0, len(text), self.CHUNK_CHARS):
            yield text[start:start + self.CHUNK_CHARS], start

    def _softmax(self, logits):
        shifted = logits - np.max(logits, axis=-1, keepdims=True)
        exp = np.exp(shifted)
        return exp / np.sum(exp, axis=-1, keepdims=True)

    def _should_skip_regex_match(self, pii_type: str, match: re.Match, text: str) -> bool:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        line_has_financial_csv_shape = line.count(",") >= 3 and re.search(
            r"\b[A-Z]{4}0[A-Z0-9]{6}\b", line, re.IGNORECASE
        )

        if pii_type == "Aadhaar":
            return line_has_financial_csv_shape
        if pii_type == "Phone":
            return line_has_financial_csv_shape and text[match.start() - 1:match.start()] != "+"
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    classifier = PIIClassifier()
    samples = [
        "Aadhaar 5543 8892 1012 PAN AMZPM9941L SSN 000-12-3456",
        "Email sjenkins@securemail.net phone +91 9845012345 card 4111-2222-3333-4444",
        "bank_account_num 918273645019 routing_code HDFC0000124 OPENAI_API_KEY=sk-proj-LiveEngine2026XyZAlphaBravoCharlie019283",
        "Patient was prescribed medication for asthma by Dr. Sharma.",
    ]

    print("\n--- PII Classification Test ---")
    print(f"Backend: {classifier.backend}")
    for sample in samples:
        results = classifier.classify(sample)
        print(f"\nText: {sample[:80]}...")
        print(f"PII Types: {results['pii_types']}")
        print(f"Categories: {results['categories']}")
        print(f"Methods: {[item['method'] for item in results['detections']]}")
        print(f"Confidence: {results['confidence']}")
