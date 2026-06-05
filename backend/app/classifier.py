import logging
import re
from typing import Dict

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    from transformers import AutoTokenizer
except ImportError:
    AutoTokenizer = None

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)

class PIIClassifier:
    """Classifies PII in text using DistilBERT NER + regex patterns."""

    # PII category definitions
    PII_CATEGORIES = {
        'identity': ['name', 'aadhaar', 'pan', 'ssn', 'passport', 'license'],
        'financial': ['account', 'card', 'credit', 'bank', 'routing', 'swift', 'iban'],
        'contact': ['phone', 'email', 'address', 'zip', 'postcode'],
        'medical': ['hospital', 'doctor', 'prescription', 'diagnosis', 'medication', 'surgery', 'patient'],
        'location': ['address', 'city', 'state', 'country', 'latitude', 'longitude'],
        'credentials': ['password', 'api_key', 'access_key', 'token', 'secret']
    }

    # Regex patterns for common PII
    REGEX_PATTERNS = {
        'aadhaar': r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        'pan': r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b',
        'phone_in': r'\b(?:\+?91[\s-]?|0)?[6-9]\d{9}\b',
        # False negative risk: unformatted US 10-digit phone numbers are skipped to avoid matching account IDs.
        'phone_us': r'\b(?:\+?1[\s-]\d{3}[\s-]\d{4}|(?:\+?1[\s-]?)?(?:\(\d{3}\)|\d{3}[\s.-])\d{3}[\s.-]\d{4})\b',
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'dob': r'\b(?:DOB|date of birth)\s*[:=-]?\s*\d{4}-\d{2}-\d{2}\b',
        'bank_account': r'\b(?:account|acct|bank_account_num)\D{0,20}\d{8,18}\b',
        'routing_code': r'\b(?:(?:routing(?:_code)?|ifsc)\D{0,40})?[A-Z]{4}0[A-Z0-9]{6}\b',
        'address': r"\b(?:address[ \t]*[:=-]?[ \t]*)?\d{1,6}[ \t]+[A-Za-z0-9 .'-]{1,80}[ \t]+(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Terrace|Lane|Ln\.?|Drive)\b",
        'api_key': r'\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b',
        'secret': r'\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z0-9_]*\s*[:=]\s*\S+',
        'database_url': r'\b[a-z]+:\/\/[^:\s]+:[^\s@]+@[^\s]+',
        'medical_record': r'\b(?:patient|diagnosed|diagnosis|prescribed|prescription|hospital|doctor|dr\.|asthma|diabetes|surgery)\b',
        # False positive risk: this flags RFC1918 addresses, including benign local service config.
        'ipv4': r'\b(?:192\.168|172\.(?:1[6-9]|2\d|3[0-1])|10)\.\d{1,3}\.\d{1,3}\b'
    }

    PATTERN_CATEGORIES = {
        'aadhaar': 'identity',
        'pan': 'identity',
        'ssn': 'identity',
        'dob': 'identity',
        'credit_card': 'financial',
        'bank_account': 'financial',
        'routing_code': 'financial',
        'phone_in': 'contact',
        'phone_us': 'contact',
        'email': 'contact',
        'address': 'location',
        'api_key': 'credentials',
        'secret': 'credentials',
        'database_url': 'credentials',
        'medical_record': 'medical',
        'ipv4': 'location',
    }

    def __init__(self, model_path: str = 'assets/models/distilbert-ner.onnx'):
        """Initialize classifier with ONNX model."""
        self.model_path = model_path
        self.session = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """Load ONNX model and tokenizer."""
        if not ort or not AutoTokenizer:
            logger.warning("ONNX dependencies unavailable. Using regex fallback.")
            self.session = None
            return

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
                if self._should_skip_regex_match(pattern_name, match, text):
                    continue

                excerpt = text[max(0, match.start()-50):min(len(text), match.end()+50)]
                results['types'].append(pattern_name)
                results['confidence'].append(0.95)  # Regex has high confidence
                results['excerpts'].append(excerpt)

                category = self.PATTERN_CATEGORIES.get(pattern_name)
                if category:
                    results['categories'].add(category)
                    continue

                # False negative risk: unlabeled account-like numbers are ignored to avoid flagging every long ID.
                for category, keywords in self.PII_CATEGORIES.items():
                    if pattern_name in keywords or any(kw in pattern_name for kw in keywords):
                        results['categories'].add(category)

        return results

    def _should_skip_regex_match(self, pattern_name: str, match: re.Match, text: str) -> bool:
        """Suppress known regex false positives without hiding the documented risk."""
        context = text[max(0, match.start()-100):min(len(text), match.end()+100)].lower()
        line_start = text.rfind('\n', 0, match.start()) + 1
        line_end = text.find('\n', match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        line_has_financial_csv_shape = line.count(',') >= 3 and re.search(
            r'\b[A-Z]{4}0[A-Z0-9]{6}\b', line, re.IGNORECASE
        )

        if pattern_name == 'aadhaar':
            # False positive logged: 12-digit bank account fields can look exactly like Aadhaar.
            financial_context = ['bank_account', 'account_num', 'routing_code', 'employee_id', 'salary']
            return line_has_financial_csv_shape or any(marker in context for marker in financial_context)

        if pattern_name == 'phone_in':
            # False positive logged: Indian account numbers can contain 10-digit phone-like substrings.
            return line_has_financial_csv_shape

        return False

    def _classify_ner(self, text: str) -> Dict:
        """NER-based PII classification using DistilBERT."""
        results = {
            'types': [],
            'confidence': [],
            'excerpts': [],
            'categories': set()
        }

        if not self.session or np is None:
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
