import os
import random
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    AdamW,
)


LABELS = [
    "O",
    "B-PER",
    "I-PER",
    "B-ORG",
    "I-ORG",
    "B-LOC",
    "I-LOC",
    "B-MISC",
    "I-MISC",
]


class SimpleNERDataset(Dataset):
    def __init__(self, examples, tokenizer, max_length=128):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]
        words = ex["words"]
        word_labels = ex["labels"]

        enc = self.tokenizer(
            words,
            is_split_into_words=True,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        # align labels to tokenized output
        labels = []
        word_ids = enc.word_ids(batch_index=0)
        for wid in word_ids:
            if wid is None:
                labels.append(-100)
            else:
                label = word_labels[wid]
                labels.append(LABELS.index(label))

        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(labels, dtype=torch.long)
        return item


def build_synthetic_examples():
    # Positive examples with entities
    examples = []
    examples.append(
        {"words": "Aarav Malhotra was admitted to St Marys Hospital".split(), "labels": [
            "B-PER", "I-PER", "O", "O", "O", "B-ORG", "I-ORG"
        ]}
    )
    examples.append(
        {"words": "Contact +91 9845012345 or email sjenkins@securemail.net".split(), "labels": [
            "O", "O", "B-MISC", "O", "O"
        ]}
    )
    examples.append(
        {"words": "Passport Z1234567 expires 2028".split(), "labels": ["O", "B-MISC", "O", "O"]}
    )

    # Negative examples (config lines, adblock lists, numeric dumps)
    examples.append({"words": ["!", "Adblock", "filter", "list"], "labels": ["O", "O", "O", "O"]})
    examples.append({"words": ["www.example.com", "##", "ad", "banner"], "labels": ["O", "O", "O", "O"]})
    examples.append({"words": list("1234567890123456"), "labels": ["O"] * 16})

    # Add variations
    for _ in range(40):
        if random.random() < 0.6:
            # sample positive-like
            examples.append({"words": "Neha Rao Phone +91 9876543210 Email neha.rao@example.in".split(),
                             "labels": ["B-PER","I-PER","O","O","B-MISC","O","B-MISC"]})
        else:
            examples.append({"words": "adserver.com##.popup data-rule 0 1 2 3".split(), "labels": ["O"] * 6})

    random.shuffle(examples)
    return examples


def collate_fn(batch):
    keys = [k for k in batch[0].keys()]
    out = {k: torch.stack([b[k] for b in batch]) for k in keys}
    return out


def train(output_dir: str = "assets/models/distilbert-ner-finetuned", epochs: int = 3, batch_size: int = 8):
    os.makedirs(output_dir, exist_ok=True)
    model_name = "elastic/distilbert-base-uncased-finetuned-conll03-english"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_name, num_labels=len(LABELS))

    # set label mapping in config
    model.config.label2id = {l: i for i, l in enumerate(LABELS)}
    model.config.id2label = {i: l for i, l in enumerate(LABELS)}

    examples = build_synthetic_examples()
    ds = SimpleNERDataset(examples, tokenizer)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    optim = AdamW(model.parameters(), lr=5e-5)

    model.train()
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        start = time.time()
        for batch in dl:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            loss.backward()
            optim.step()
            optim.zero_grad()

            epoch_loss += float(loss.item())

        elapsed = time.time() - start
        print(f"Epoch {epoch}/{epochs} loss={epoch_loss:.4f} time={elapsed:.1f}s")

    print("Saving fine-tuned model...")
    tokenizer.save_pretrained(output_dir)
    model.save_pretrained(output_dir)

    # Export to ONNX (overwrite existing fast runtime file)
    try:
        from torch import ones

        wrapper = None
        # The download_model wrapper expects token_type_ids in forward signature
        class Wrapper(torch.nn.Module):
            def __init__(self, model):
                super().__init__()
                self.model = model

            def forward(self, input_ids, attention_mask, token_type_ids):
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits
                keep_token_type_ids = token_type_ids.to(dtype=logits.dtype).sum() * 0.0
                return logits + keep_token_type_ids

        wrapper = Wrapper(model)
        wrapper.eval()

        dummy_input_ids = torch.ones((1, 128), dtype=torch.long)
        dummy_attention_mask = torch.ones((1, 128), dtype=torch.long)
        dummy_token_type_ids = torch.zeros((1, 128), dtype=torch.long)

        onnx_path = "assets/models/distilbert-ner.onnx"
        torch.onnx.export(
            wrapper,
            (dummy_input_ids, dummy_attention_mask, dummy_token_type_ids),
            onnx_path,
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
        print(f"ONNX exported to: {onnx_path}")
    except Exception as exc:
        print(f"ONNX export failed: {exc}")


if __name__ == "__main__":
    print("Starting lightweight NER fine-tune (quick local run)...")
    train(epochs=3, batch_size=8)
