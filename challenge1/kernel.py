"""
RMIT Hackathon 2026 - Challenge 1: Multilingual Prompt-Attack Classification

Chosen model: FacebookAI/xlm-roberta-large  (approved list)

Kaggle setup:
  - Add data: competition "rmit-hackathon-2026"
  - Add model: aisuko/xlm-roberta-large (Models tab, Transformers/default)
  - Accelerator: GPU (T4 / P100), Internet off is fine
  - Kernel title: <university>_<campus>_<team>_C1, e.g. RMIT_SGS_myteam_C1

Pipeline:
  stratified holdout (label x language) -> fine-tune with class-weighted CE
  -> keep best epoch by val macro-F1 -> tune per-class logit bias on val
  -> predict test -> submission.csv
To switch backbone, change CFG["model_hint"] (e.g. "mmbert-base", "xlm-roberta-base").
"""
import glob
import os
import random
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_cosine_schedule_with_warmup)

CFG = dict(
    model_hint="xlm-roberta-large",  # substring of the model folder under /kaggle/input
    max_len=256,
    batch_size=8,
    grad_accum=2,                    # effective batch = 16
    epochs=3,
    lr=1e-5,
    weight_decay=0.01,
    warmup_ratio=0.1,
    val_size=0.15,
    seed=42,
    class_weight_power=0.5,          # 0 = no weighting, 1 = full inverse frequency
    fp16=True,
    tune_bias=True,
)
LABELS = ["BENIGN", "JAILBREAK", "PROMPT_INJECTION"]
L2I = {l: i for i, l in enumerate(LABELS)}
OUT_DIR = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def find_input(name):
    hits = sorted(glob.glob(f"/kaggle/input/**/{name}", recursive=True))
    if not hits:
        raise FileNotFoundError(f"{name} not found under /kaggle/input")
    return hits[0]


def find_model_dir(hint):
    configs = glob.glob("/kaggle/input/**/config.json", recursive=True)
    hits = sorted(os.path.dirname(c) for c in configs if hint.lower() in c.lower())
    if not hits:
        raise FileNotFoundError(f"No model matching '{hint}' under /kaggle/input. Found: {configs}")
    return hits[0]


# ---------------------------------------------------------------- data
class Encoder:
    """Tokenizes with head+tail truncation: attacks often sit at the end of long prompts."""

    def __init__(self, tok, max_len):
        self.tok = tok
        plain = tok("x", add_special_tokens=False)["input_ids"]
        full = tok("x")["input_ids"]
        i = full.index(plain[0])
        self.prefix, self.suffix = full[:i], full[i + len(plain):]
        self.body = max_len - len(self.prefix) - len(self.suffix)

    def __call__(self, texts):
        out = []
        for ids in self.tok(list(texts), add_special_tokens=False)["input_ids"]:
            if len(ids) > self.body:
                head = self.body // 2
                ids = ids[:head] + ids[-(self.body - head):]
            out.append(self.prefix + ids + self.suffix)
        return out


class TextDataset(Dataset):
    def __init__(self, ids, labels=None):
        self.ids, self.labels = ids, labels

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        return self.ids[i], (-1 if self.labels is None else self.labels[i])


def make_collate(pad_id):
    def collate(batch):
        n = max(len(x) for x, _ in batch)
        input_ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
        mask = torch.zeros((len(batch), n), dtype=torch.long)
        for j, (x, _) in enumerate(batch):
            input_ids[j, :len(x)] = torch.tensor(x)
            mask[j, :len(x)] = 1
        labels = torch.tensor([y for _, y in batch], dtype=torch.long)
        return input_ids, mask, labels
    return collate


def sorted_loader(ids, bs, collate):
    """Inference loader sorted by length (less padding); returns order to undo the sort."""
    order = np.argsort([len(x) for x in ids])
    ds = TextDataset([ids[i] for i in order])
    return DataLoader(ds, batch_size=bs, shuffle=False, collate_fn=collate), order


# ---------------------------------------------------------------- train / eval
@torch.no_grad()
def predict_logits(model, ids, bs, collate):
    model.eval()
    loader, order = sorted_loader(ids, bs, collate)
    chunks = []
    for input_ids, mask, _ in loader:
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=CFG["fp16"] and DEVICE == "cuda"):
            logits = model(input_ids=input_ids.to(DEVICE), attention_mask=mask.to(DEVICE)).logits
        chunks.append(logits.float().cpu())
    logits = torch.cat(chunks).numpy()
    out = np.empty_like(logits)
    out[order] = logits
    return out


def macro_f1(y, pred):
    return f1_score(y, pred, average="macro")


def tune_bias(logp, y, grid=np.arange(-3.0, 3.01, 0.1)):
    """Coordinate search for per-class additive bias on log-probs to maximise macro-F1."""
    bias = np.zeros(logp.shape[1])
    best = macro_f1(y, logp.argmax(1))
    for _ in range(3):
        for c in range(1, logp.shape[1]):
            for v in grid:
                b = bias.copy()
                b[c] = v
                s = macro_f1(y, (logp + b).argmax(1))
                if s > best + 1e-6:
                    best, bias = s, b
    return bias, best


def log_softmax(x):
    x = x - x.max(1, keepdims=True)
    return x - np.log(np.exp(x).sum(1, keepdims=True))


def main():
    seed_everything(CFG["seed"])
    print("CFG:", CFG, "| device:", DEVICE)

    train = pd.read_csv(find_input("train.csv"))
    test = pd.read_csv(find_input("test.csv"))
    for df in (train, test):
        df["text"] = df["text"].fillna("").astype(str)
    train["y"] = train["label"].map(L2I)
    assert train["y"].notna().all(), f"Unknown labels: {set(train['label']) - set(LABELS)}"
    print(train.shape, test.shape)
    print(pd.crosstab(train["language"], train["label"], margins=True))

    tr, va = train_test_split(
        train, test_size=CFG["val_size"], random_state=CFG["seed"],
        stratify=train["label"] + "_" + train["language"].astype(str),
    )

    model_dir = find_model_dir(CFG["model_hint"])
    print("Model dir:", model_dir)
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I,
        ignore_mismatched_sizes=True,  # safety-tuned backbones ship their own head
    ).to(DEVICE)

    enc = Encoder(tok, CFG["max_len"])
    lens = [len(x) for x in tok(train["text"].tolist(), add_special_tokens=False)["input_ids"]]
    print("Token length p50/p90/p99/max:", np.percentile(lens, [50, 90, 99, 100]).astype(int))
    tr_ids, va_ids, te_ids = enc(tr["text"]), enc(va["text"]), enc(test["text"])
    collate = make_collate(tok.pad_token_id)

    counts = np.bincount(tr["y"], minlength=len(LABELS))
    w = (counts.sum() / counts) ** CFG["class_weight_power"]
    w = torch.tensor(w / w.mean(), dtype=torch.float, device=DEVICE)
    print("Class weights:", w.tolist())
    loss_fn = nn.CrossEntropyLoss(weight=w)

    loader = DataLoader(TextDataset(tr_ids, tr["y"].tolist()), batch_size=CFG["batch_size"],
                        shuffle=True, collate_fn=collate, drop_last=True)
    no_decay = ("bias", "LayerNorm.weight", "norm.weight")
    params = [
        {"params": [p for n, p in model.named_parameters() if not any(k in n for k in no_decay)],
         "weight_decay": CFG["weight_decay"]},
        {"params": [p for n, p in model.named_parameters() if any(k in n for k in no_decay)],
         "weight_decay": 0.0},
    ]
    opt = torch.optim.AdamW(params, lr=CFG["lr"])
    total = len(loader) // CFG["grad_accum"] * CFG["epochs"]
    sched = get_cosine_schedule_with_warmup(opt, int(total * CFG["warmup_ratio"]), total)
    use_amp = CFG["fp16"] and DEVICE == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_f1, best_state = -1.0, None
    for epoch in range(CFG["epochs"]):
        model.train()
        t0, running = time.time(), 0.0
        for step, (input_ids, mask, labels) in enumerate(loader):
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                logits = model(input_ids=input_ids.to(DEVICE), attention_mask=mask.to(DEVICE)).logits
            loss = loss_fn(logits.float(), labels.to(DEVICE)) / CFG["grad_accum"]
            scaler.scale(loss).backward()
            running += loss.item() * CFG["grad_accum"]
            if (step + 1) % CFG["grad_accum"] == 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
            if (step + 1) % 200 == 0:
                print(f"  ep{epoch} step {step + 1}/{len(loader)} loss {running / (step + 1):.4f}")

        va_logits = predict_logits(model, va_ids, CFG["batch_size"] * 4, collate)
        f1 = macro_f1(va["y"], va_logits.argmax(1))
        print(f"Epoch {epoch}: loss {running / len(loader):.4f} | val macro-F1 {f1:.4f} | {time.time() - t0:.0f}s")
        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    va_logp = log_softmax(predict_logits(model, va_ids, CFG["batch_size"] * 4, collate))
    bias = np.zeros(len(LABELS))
    if CFG["tune_bias"]:
        bias, tuned = tune_bias(va_logp, va["y"].values)
        print(f"Val macro-F1 raw {best_f1:.4f} -> bias-tuned {tuned:.4f} | bias {bias.round(2)}")

    va_pred = (va_logp + bias).argmax(1)
    print(classification_report(va["y"], va_pred, target_names=LABELS, digits=4))
    for lang, g in va.assign(pred=va_pred).groupby("language"):
        print(f"  {lang:>4}: macro-F1 {macro_f1(g['y'], g['pred']):.4f} (n={len(g)})")

    te_logp = log_softmax(predict_logits(model, te_ids, CFG["batch_size"] * 4, collate))
    np.save(os.path.join(OUT_DIR, "val_logp.npy"), va_logp)
    np.save(os.path.join(OUT_DIR, "test_logp.npy"), te_logp)

    sub = pd.DataFrame({"id": test["id"], "label": [LABELS[i] for i in (te_logp + bias).argmax(1)]})
    assert len(sub) == len(test) and sub["label"].isin(LABELS).all()
    sub.to_csv(os.path.join(OUT_DIR, "submission.csv"), index=False)
    print(sub["label"].value_counts(normalize=True))
    print("Wrote", os.path.join(OUT_DIR, "submission.csv"))


if __name__ == "__main__":
    main()
