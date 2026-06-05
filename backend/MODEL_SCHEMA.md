# DistilBERT NER Model Schema

## Model Info
- Model Name: [INSERT MODEL NAME]
- Source: Hugging Face
- Task: Named Entity Recognition (NER)
- Framework: ONNX Runtime
- Input: Tokenized text (input_ids, attention_mask, token_type_ids)
- Output: Logits of shape [batch_size, sequence_length, num_labels]

## Expected Entity Labels
- B-PER (Beginning of Person)
- I-PER (Inside Person)
- B-ORG (Organization)
- I-ORG
- B-LOC (Location)
- I-LOC
- O (Outside)
- [Others: check model card]

## Input Format
```json
{
  "input_ids": [101, 2054, 2003, ...],
  "attention_mask": [1, 1, 1, ...],
  "token_type_ids": [0, 0, 0, ...]
}
```

## Output Format
```json
{
  "logits": [[...], [...], ...]  // shape: [1, seq_len, num_labels]
}
```

## Tokenization
- Tokenizer: distilbert-base-uncased
- Max Length: 512
- Truncation: Required

## Entity Mapping to PII Categories
- PERSON + "account" nearby → Financial PII
- PERSON + "phone" → Contact PII
- PERSON (standalone) → Identity PII
- ORG → Contact PII
- LOC → Location PII
