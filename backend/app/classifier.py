import logging
import re
from typing import List, Dict, Tuple
import onnxruntime as ort
from transformers import AutoTokenizer
import numpy as np

logger = logging.getLogger(__name__)

class PIIClassifier:
    """Classifies PII in text using DistilBERT NER + regex patterns."""

    # PII category definitions
    PII_CATEGORIES = {
        'identity': ['name', 'aadhaar', 'pan', 'ssn', 'passport', 'license'],
        'financial': ['account', 'card', 'credit', 'bank', 'routing', 'swift', 'iban'],
        'contact': ['phone', 'email', 'address', 'zip', 'postcode'],
        'medical': ['hospital', 'doctor', 'prescription', 'diagnosis', 'medication', 'surgery'],
        'location': ['address', 'city', 'state', 'country', 'latitude', 'longitude'],
        'credentials': ['password', 'api_key', 'token', 'secret']
    }

    # Regex patterns for common PII
    REGEX_PATTERNS = {
        'aadhaar': r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        'pan': r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b',
        'phone_in': r'\b(?:\+?91|0)?[6-9]\d{9}\b',
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'ipv4': r'\b(?:192|172|10)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'  # Private IP
    }

    def __init__(self, model_path: str = 'assets/models/distilbert-ner.onnx'):
        """Initialize classifier with NER backend fallback."""
        self.model_path = model_path
        self.session = None
        self.pytorch_model = None
        self.tokenizer = None
        self.backend = "regex"
        self._load_model()

    def _load_model(self):
        """Load NER backend with ONNX, PyTorch, then regex-only fallback."""
        tokenizer_path = 'assets/models/distilbert-ner'
        tokenizer_fallback = 'elastic/distilbert-base-uncased-finetuned-conll03-english'

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        except Exception as e:
            logger.warning(f"Local tokenizer load failed: {e}. Trying HuggingFace fallback.")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_fallback)
            except Exception as tokenizer_error:
                logger.warning(f"Tokenizer load failed: {tokenizer_error}. NER disabled.")
                self.session = None
                self.pytorch_model = None
                self.backend = "regex"
                logger.info(f"NER backend: {self.backend}")
                return

        try:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=['CPUExecutionProvider']
            )
            self.pytorch_model = None
            self.backend = "onnx"
        except Exception as e:
            logger.warning(f"ONNX model load failed: {e}. Trying PyTorch fallback.")
            self.session = None
            try:
                from transformers import AutoModelForTokenClassification

                self.pytorch_model = AutoModelForTokenClassification.from_pretrained(
                    'assets/models/distilbert-ner'
                )
                self.pytorch_model.eval()
                self.session = self.pytorch_model
                self.backend = "pytorch"
            except Exception as pytorch_error:
                logger.warning(f"PyTorch model load failed: {pytorch_error}. Using regex fallback.")
                self.session = None
                self.pytorch_model = None
                self.backend = "regex"

        logger.info(f"NER backend: {self.backend}")

    def classify(self, text: str) -> Dict:
        """
        Classify PII in text.
        Returns: {pii_types: [...], confidence: [...], excerpts: [...]}
        """
        pii_results = {
            'pii_types': [],
            'confidence': [],
            'excerpts': [],
            'categories': set()
        }

        # Regex-based classification (always available)
        regex_results = self._classify_regex(text)
        pii_results['pii_types'].extend(regex_results['types'])
        pii_results['confidence'].extend(regex_results['confidence'])
        pii_results['excerpts'].extend(regex_results['excerpts'])
        pii_results['categories'].update(regex_results['categories'])

        # NER-based classification (if model available)
        if self.session:
            try:
                ner_results = self._classify_ner(text)
                pii_results['pii_types'].extend(ner_results['types'])
                pii_results['confidence'].extend(ner_results['confidence'])
                pii_results['excerpts'].extend(ner_results['excerpts'])
                pii_results['categories'].update(ner_results['categories'])
            except Exception as e:
                logger.warning(f"NER classification failed: {e}")

        # Convert set to list for JSON serialization
        pii_results['categories'] = list(pii_results['categories'])

        logger.info(f"Classification complete: {len(pii_results['pii_types'])} PII found")
        return pii_results

    def _classify_regex(self, text: str) -> Dict:
        """Regex-based PII classification."""
        results = {
            'types': [],
            'confidence': [],
            'excerpts': [],
            'categories': set()
        }

        for pattern_name, pattern in self.REGEX_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                excerpt = text[max(0, match.start()-50):min(len(text), match.end()+50)]
                results['types'].append(pattern_name)
                results['confidence'].append(0.95)  # Regex has high confidence
                results['excerpts'].append(excerpt)

                # Map pattern to category
                for category, keywords in self.PII_CATEGORIES.items():
                    if pattern_name in keywords or any(kw in pattern_name for kw in keywords):
                        results['categories'].add(category)

        return results

    def _classify_ner(self, text: str) -> Dict:
        """NER-based PII classification using ONNX or PyTorch."""
        results = {
            'types': [],
            'confidence': [],
            'excerpts': [],
            'categories': set()
        }

        if self.backend == "regex":
            return results

        def append_entity(entity):
            char_start = entity['start']
            char_end = entity['end']
            label = entity['label']
            entity_text = text[char_start:char_end]

            if not entity_text.strip():
                return

            excerpt = text[max(0, char_start - 50):min(len(text), char_end + 50)]
            results['types'].append(label)
            results['confidence'].append(float(np.mean(entity['confidence'])))
            results['excerpts'].append(excerpt)
            results['categories'].add(self._map_entity_to_category(label))

        try:
            inputs = self.tokenizer(
                text,
                return_tensors="np" if self.backend == "onnx" else "pt",
                truncation=True,
                max_length=512,
                padding=True,
                return_token_type_ids=True,
                return_offsets_mapping=True
            )
            offset_mapping = inputs.pop("offset_mapping")

            if self.backend == "onnx":
                onnx_input_names = [inp.name for inp in self.session.get_inputs()]
                if "token_type_ids" in onnx_input_names and "token_type_ids" not in inputs:
                    inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
                input_feed = {
                    name: np.asarray(inputs[name], dtype=np.int64)
                    for name in onnx_input_names
                    if name in inputs
                }
                outputs = self.session.run(None, input_feed)
                logits = outputs[0]
                offsets = offset_mapping[0]
            elif self.backend == "pytorch":
                import torch

                inputs.pop("token_type_ids", None)
                with torch.no_grad():
                    logits = self.pytorch_model(**inputs).logits.cpu().numpy()
                offsets = offset_mapping[0].cpu().numpy()
            else:
                return results

            exp_logits = np.exp(logits - np.max(logits, axis=2, keepdims=True))
            probabilities = exp_logits / np.sum(exp_logits, axis=2, keepdims=True)
            predictions = np.argmax(probabilities, axis=2)

            ID2LABEL = {
                0: "O",
                1: "B-PER", 2: "I-PER",
                3: "B-ORG", 4: "I-ORG",
                5: "B-LOC", 6: "I-LOC",
                7: "B-MISC", 8: "I-MISC"
            }

            current_entity = None

            for i, pred in enumerate(predictions[0]):
                label = ID2LABEL.get(int(pred), 'O')
                char_start, char_end = int(offsets[i][0]), int(offsets[i][1])

                if char_start == char_end:
                    continue

                if label == 'O':
                    if current_entity:
                        append_entity(current_entity)
                        current_entity = None
                    continue

                prefix, entity_type = label.split('-', 1)
                confidence = float(probabilities[0][i][int(pred)])

                if not current_entity or current_entity['entity_type'] != entity_type:
                    if current_entity:
                        append_entity(current_entity)
                    current_entity = {
                        'label': f'B-{entity_type}',
                        'entity_type': entity_type,
                        'start': char_start,
                        'end': char_end,
                        'confidence': [confidence]
                    }
                else:
                    current_entity['end'] = char_end
                    current_entity['confidence'].append(confidence)

            if current_entity:
                append_entity(current_entity)

        except Exception as e:
            logger.error(f"NER classification error: {e}")

        return results

    def _map_entity_to_category(self, entity_label: str) -> str:
        """Map NER entity label to PII category."""
        if 'PER' in entity_label:
            return 'identity'
        elif 'ORG' in entity_label:
            return 'contact'
        elif 'LOC' in entity_label:
            return 'location'
        else:
            return 'unknown'


# Test the classifier
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    classifier = PIIClassifier()
    
    test_texts = [
        "My name is John Doe and my Aadhaar is 1234 5678 9012",
        "Account number 1234567890 from HDFC Bank",
        "Contact me at john@example.com or 9876543210",
        "I live at 123 Main St, New York, NY 10001",
        "Dr. Smith diagnosed me with diabetes in 2023"
    ]

    print("\n--- PII Classification Test ---")
    for text in test_texts:
        results = classifier.classify(text)
        print(f"\nText: {text[:60]}...")
        print(f"PII Types: {results['pii_types']}")
        print(f"Categories: {results['categories']}")
        print(f"Confidence: {results['confidence']}")
