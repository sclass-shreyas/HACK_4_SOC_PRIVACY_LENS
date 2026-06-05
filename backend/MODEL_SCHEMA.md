# MODEL_SCHEMA.md - PrivacyLens NER Model

## Status Checklist
| Task | Status |
|---|---|
| ONNX model loading | PASS - implemented in `test_onnx_inference.py` and `PIIClassifier._load_model()` |
| Regex patterns (6 PII types) | PASS - Aadhaar, SSN, CreditCard, Email, Phone, PAN |
| Basic Privacy Debt Score | PASS - implemented in `backend/app/scorer.py` |
| INT8 quantization + speed validation | PASS - `download_model.py` exports and quantizes; `test_onnx_inference.py` validates latency |
| Text chunking for 512 token limit | PASS - classifier chunks text before NER and uses `max_length=512` |
| Async regex first / NER second | PASS - regex always runs first; NER runs only after model backend is loaded |
| Labelmap + entity mapping | PASS - CoNLL labels map PER/ORG/LOC to Name/Organization/Location |
| Confidence scoring per detection | PASS - regex uses 0.95; NER uses token softmax confidence |
| Deduplication logic | PASS - duplicate detections are collapsed by type/value/span |
| Score category breakdown | PASS - scorer returns identity/financial/contact/credentials/medical/location/bonus breakdown |
| MODEL_SCHEMA.md updated | PASS - this file documents schema, fallback, and status |

## Model Identity
| Field | Value |
|---|---|
| Base model | `elastic/distilbert-base-uncased-finetuned-conll03-english` |
| Task | Token classification / NER |
| Primary runtime | ONNX Runtime INT8 |
| Fallback runtime | PyTorch model, then regex-only |
| ONNX path | `assets/models/distilbert-ner.onnx` |
| Local tokenizer/model path | `assets/models/distilbert-ner/` |

## Input Schema
| Name | Shape | dtype | Notes |
|---|---|---|---|
| `input_ids` | `(batch, seq_len)` | `int64` | Token IDs |
| `attention_mask` | `(batch, seq_len)` | `int64` | 1 for real tokens |
| `token_type_ids` | `(batch, seq_len)` | `int64` | Included for ONNX compatibility |

Classifier chunks long text and sends at most 512 tokens per NER pass.

## Output Schema
| Name | Shape | dtype | Notes |
|---|---|---|---|
| `logits` | `(batch, seq_len, 9)` | `float32` | Softmax is applied for per-token confidence |

## Label Map
| ID | Label | PII Mapping |
|---|---|---|
| 0 | O | none |
| 1 | B-PER | Name / identity |
| 2 | I-PER | Name / identity |
| 3 | B-ORG | Organization / contact |
| 4 | I-ORG | Organization / contact |
| 5 | B-LOC | Location |
| 6 | I-LOC | Location |
| 7 | B-MISC | ignored |
| 8 | I-MISC | ignored |

## Validation Commands
```powershell
cd backend
python -m app.classifier
python -m app.scorer
python test_onnx_inference.py
```

Expected model status line:

```text
Model test: PASS
```

If the ONNX artifact or Python ML dependencies are unavailable, the acceptable fallback status is:

```text
Model test: FALLBACK TO PYTORCH - export steps documented
```

## Notes
- Regex detects structured PII: Aadhaar, SSN, CreditCard, Email, Phone, PAN, BankAccount, RoutingCode, Secret/APIKey, and Medical keywords.
- NER detects names, organizations, and locations only; it does not detect Aadhaar/SSN/credit-card numbers by itself.
- `download_model.py` is responsible for downloading, exporting ONNX, and INT8 quantization.
