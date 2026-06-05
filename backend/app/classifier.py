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
        """Initialize classifier with ONNX model."""
        self.model_path = model_path
        self.session = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """Load ONNX model and tokenizer."""
        try:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=['CPUExecutionProvider']
            )
            self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
            logger.info("✓ ONNX model loaded successfully")
        except Exception as e:
            logger.warning(f"ONNX model load failed: {e}. Using regex fallback.")
            self.session = None

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
        """NER-based PII classification using DistilBERT."""
        results = {
            'types': [],
            'confidence': [],
            'excerpts': [],
            'categories': set()
        }

        if not self.session:
            return results

        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors='np',
                truncation=True,
                max_length=512,
                padding=True
            )

            # Run inference
            input_names = [input.name for input in self.session.get_inputs()]
            input_feed = {name: inputs[key].numpy() for name, key in zip(input_names, inputs.keys())}
            outputs = self.session.run(None, input_feed)

            # Parse outputs
            logits = outputs[0]
            predictions = np.argmax(logits, axis=2)
            
            # Simple entity extraction (this is a simplified version)
            # In production, you'd decode the token predictions properly
            entity_labels = {0: 'O', 1: 'B-PER', 2: 'I-PER', 3: 'B-ORG', 4: 'I-ORG', 
                             5: 'B-LOC', 6: 'I-LOC'}
            
            for i, pred in enumerate(predictions[0]):
                label = entity_labels.get(pred, 'O')
                if label != 'O':
                    results['types'].append(label)
                    results['confidence'].append(float(np.max(logits[0][i])))
                    results['categories'].add(self._map_entity_to_category(label))

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
