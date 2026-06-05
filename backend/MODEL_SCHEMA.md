# MODEL_SCHEMA.md — PrivacyLens NER Model

## Model Identity
| Field        | Value                                                    |
|--------------|----------------------------------------------------------|
| Base model   | elastic/distilbert-base-uncased-finetuned-conll03-english |
| Source       | HuggingFace Hub (downloaded once, stored locally)        |
| Task         | Token classification — Named Entity Recognition (NER)    |
| Format       | ONNX Runtime (INT8 quantized)  +  PyTorch fallback       |
| Quantization | Post-training dynamic INT8 via onnxruntime.quantization  |
| ONNX opset   | 13                                                       |

## Local File Paths
| File                                  | Description                        |
|---------------------------------------|------------------------------------|
| assets/models/distilbert-ner/         | PyTorch weights + tokenizer files  |
| assets/models/distilbert-ner.onnx     | INT8 quantized ONNX model (primary)|

## ONNX Input Schema
| Name             | Shape              | dtype  | Description             |
|------------------|--------------------|--------|-------------------------|
| input_ids        | (batch, seq_len)   | int64  | Tokenized input ids      |
| attention_mask   | (batch, seq_len)   | int64  | 1 = real token, 0 = pad |
| token_type_ids   | (batch, seq_len)   | int64  | Always 0 for single seq |

- batch: dynamic (always 1 at inference time in PrivacyLens)
- seq_len: dynamic, max 512 tokens

## ONNX Output Schema
| Name    | Shape                    | dtype   | Description                     |
|---------|--------------------------|---------|---------------------------------|
| logits  | (batch, seq_len, 9)      | float32 | Raw class scores per token      |

Apply softmax over axis=2 to get per-class probabilities.
Take argmax over axis=2 to get predicted label index per token.

## Label Map (CoNLL-03, 9 classes)
| ID | Label  | Meaning                        | PII Relevance     |
|----|--------|--------------------------------|-------------------|
| 0  | O      | Outside any entity             | Not PII           |
| 1  | B-PER  | Beginning of person name       | identity          |
| 2  | I-PER  | Inside person name             | identity          |
| 3  | B-ORG  | Beginning of organisation      | contact           |
| 4  | I-ORG  | Inside organisation            | contact           |
| 5  | B-LOC  | Beginning of location          | location          |
| 6  | I-LOC  | Inside location                | location          |
| 7  | B-MISC | Beginning of miscellaneous     | unknown           |
| 8  | I-MISC | Inside miscellaneous           | unknown           |

## Inference Backend Fallback Chain
```
1. ONNX (primary)   → assets/models/distilbert-ner.onnx
2. PyTorch          → assets/models/distilbert-ner/
3. Regex-only       → NER disabled, structured PII patterns still active
```

## Performance Targets
| Metric              | Target     | Condition                     |
|---------------------|------------|-------------------------------|
| Latency per chunk   | < 500ms    | INT8 ONNX, CPU, 512 tokens    |
| Latency per chunk   | < 2000ms   | PyTorch fallback, CPU         |
| Max sequence length | 512 tokens | Hard truncation applied       |

## Verification Status
| Field        | Value             |
|--------------|-------------------|
| Runtime used | ONNX Runtime INT8 |
| Latency      | 8ms mean, tested locally on 5 sample texts |
| Status       | Model test: PASS  |

## Known Limitations
- Model detects PER, ORG, LOC, MISC — not Aadhaar/SSN/CC numbers directly
- Structured PII (Aadhaar, PAN, phone, email, credit card) is handled by the
  regex layer in classifier.py, not by this model
- False positives possible on numeric strings in financial documents
- Model was trained on English (CoNLL-03); Indian-language text will degrade accuracy
