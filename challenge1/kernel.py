"""
RMIT Hackathon 2026 - Challenge 1: Multilingual Prompt-Attack Classification

Chosen model: FacebookAI/xlm-roberta-large  (approved list)

One file, three ways to run:
  Kaggle  : paste as a Script kernel, Save & Run All (uses DEFAULT_CFG)
            add data "rmit-hackathon-2026" + model aisuko/xlm-roberta-large, GPU on
            title: <university>_<campus>_<team>_C1, e.g. RMIT_SGS_myteam_C1
  Modal   : modal run challenge1/kernel.py --config configs/c1_modal_xlmr_large.yaml
            C1_GPU=H100 modal run challenge1/kernel.py ...   (default A100-40GB)
  Local   : python challenge1/kernel.py --config configs/c1_debug.yaml

Pipeline:
  stratified holdout (label x language) -> fine-tune with class-weighted CE
  -> keep best epoch by val macro-F1 -> tune per-class logit bias on val
  -> predict test -> submission.csv
"""
import argparse
import contextlib
import glob
import json
import os
import random
import time

try:
    import modal
except ImportError:
    modal = None

ON_KAGGLE = os.path.isdir("/kaggle/input")
USE_MODAL = modal is not None and not ON_KAGGLE
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
REPO_ROOT = os.path.dirname(HERE)

if USE_MODAL:
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install(
            "torch==2.8.0", "transformers==4.57.1", "accelerate", "sentencepiece", "protobuf",
            "scikit-learn", "pandas", "pyyaml",
        )
        .env({"HF_HOME": "/vol/hf"})
        .add_local_dir(os.path.join(REPO_ROOT, "data"), "/root/data")
    )
    _imports = image.imports()  # heavy deps only needed inside the container
else:
    _imports = contextlib.nullcontext()

with _imports:
    import numpy as np
    import pandas as pd
    import torch
    from sklearn.metrics import classification_report, f1_score
    from sklearn.model_selection import train_test_split
    from torch import nn
    from torch.utils.data import DataLoader
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              get_cosine_schedule_with_warmup)

DEFAULT_CFG = dict(
    model_hint="xlm-roberta-large",  # substring of the model folder under /kaggle/input
    model_path=None,                 # explicit local dir or HF id; overrides model_hint
    data_dir=None,                   # folder with train.csv/test.csv; None = auto-search
    max_rows=None,                   # subsample train for quick debugging
    max_len=512,                     # p90 ~270 tokens, p99 ~700
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
# Approved checkpoints on the HF hub, used when the Kaggle copy is not mounted (Modal / local).
HF_IDS = {
    "distilbert-base-multilingual-cased": "distilbert/distilbert-base-multilingual-cased",
    "mmbert-small": "jhu-clsp/mmBERT-small",
    "mmbert-base": "jhu-clsp/mmBERT-base",
    "xlm-roberta-base": "FacebookAI/xlm-roberta-base",
    "xlm-roberta-large": "FacebookAI/xlm-roberta-large",
    "rembert": "google/rembert",
    "deberta-v3-base-prompt-injection-v2": "protectai/deberta-v3-base-prompt-injection-v2",
    "wolf-defender-prompt-injection": "patronus-studio/wolf-defender-prompt-injection",
}
LABELS = ["BENIGN", "JAILBREAK", "PROMPT_INJECTION"]
L2I = {l: i for i, l in enumerate(LABELS)}
CFG = dict(DEFAULT_CFG)
DEVICE = "cpu"


def out_dir():
    if os.environ.get("C1_OUT_DIR"):
        return os.environ["C1_OUT_DIR"]
    return "/kaggle/working" if ON_KAGGLE else os.path.join(HERE, "outputs")


def parse_config(text, path=""):
    if path.endswith(".json"):
        override = json.loads(text)
    else:
        import yaml
        override = yaml.safe_load(text) or {}
    unknown = set(override) - set(DEFAULT_CFG)
    if unknown:
        raise KeyError(f"Unknown config keys in {path or 'config'}: {unknown}")
    return override


def load_config_file():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("C1_CONFIG"))
    args, _ = parser.parse_known_args()  # ignore notebook kernel args
    path = args.config
    if path is None and ON_KAGGLE:
        hits = sorted(glob.glob("/kaggle/input/**/c1_config.*", recursive=True))
        path = hits[0] if hits else None
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        print("Loaded config:", path)
        return parse_config(f.read(), path)


def pick_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def find_input(name, required=True):
    if CFG["data_dir"]:
        root = CFG["data_dir"]
    elif ON_KAGGLE:
        root = "/kaggle/input"
    else:
        root = os.path.join(REPO_ROOT, "data")
    hits = sorted(glob.glob(os.path.join(root, "**", name), recursive=True))
    if hits:
        return hits[0]
    if required:
        raise FileNotFoundError(f"{name} not found under {root}")
    return None


def find_model_dir():
    if CFG["model_path"]:
        return CFG["model_path"]
    hint = CFG["model_hint"].lower()
    if ON_KAGGLE:
        configs = glob.glob("/kaggle/input/**/config.json", recursive=True)
        hits = sorted(os.path.dirname(c) for c in configs if hint in c.lower())
        if hits:
            return hits[0]
        raise FileNotFoundError(f"No model matching '{hint}' under /kaggle/input. Found: {configs}")
    if hint in HF_IDS:
        return HF_IDS[hint]
    raise ValueError(f"Unknown model_hint '{hint}', set model_path. Known: {list(HF_IDS)}")


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


class TextDataset:
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
def use_amp():
    return CFG["fp16"] and DEVICE == "cuda"


def predict_logits(model, ids, bs, collate):
    model.eval()
    loader, order = sorted_loader(ids, bs, collate)
    chunks = []
    for input_ids, mask, _ in loader:
        with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp()):
            logits = model(input_ids=input_ids.to(DEVICE), attention_mask=mask.to(DEVICE)).logits
        chunks.append(logits.float().cpu())
    logits = torch.cat(chunks).numpy()
    out = np.empty_like(logits)
    out[order] = logits
    return out


def macro_f1(y, pred):
    return f1_score(y, pred, average="macro")


def tune_bias(logp, y):
    """Coordinate search for per-class additive bias on log-probs to maximise macro-F1."""
    grid = np.arange(-3.0, 3.01, 0.1)
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
    global DEVICE
    DEVICE = pick_device()
    seed_everything(CFG["seed"])
    out = out_dir()
    os.makedirs(out, exist_ok=True)
    print("CFG:", CFG, "| device:", DEVICE, "| out:", out)

    train = pd.read_csv(find_input("train.csv"))
    test_path = find_input("test.csv", required=False)
    test = pd.read_csv(test_path) if test_path else None
    if test is None:
        print("test.csv not found -> train + validate only, no submission")
    if CFG["max_rows"] and CFG["max_rows"] < len(train):
        train = train.sample(CFG["max_rows"], random_state=CFG["seed"])
    for df in (train, test):
        if df is not None:
            df["text"] = df["text"].fillna("").astype(str)
    train["y"] = train["label"].map(L2I)
    assert train["y"].notna().all(), f"Unknown labels: {set(train['label']) - set(LABELS)}"
    print("train", train.shape, "test", None if test is None else test.shape)
    print(pd.crosstab(train["language"], train["label"], margins=True))

    tr, va = train_test_split(
        train, test_size=CFG["val_size"], random_state=CFG["seed"],
        stratify=train["label"] + "_" + train["language"].astype(str),
    )

    model_dir = find_model_dir()
    print("Model:", model_dir)
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I,
        ignore_mismatched_sizes=True,  # safety-tuned backbones ship their own head
    ).to(DEVICE)

    enc = Encoder(tok, CFG["max_len"])
    lens = [len(x) for x in tok(train["text"].tolist(), add_special_tokens=False)["input_ids"]]
    print("Token length p50/p90/p99/max:", np.percentile(lens, [50, 90, 99, 100]).astype(int),
          f"| truncated: {np.mean(np.array(lens) > enc.body):.1%}")
    tr_ids, va_ids = enc(tr["text"]), enc(va["text"])
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
    total = max(1, len(loader) // CFG["grad_accum"] * CFG["epochs"])
    sched = get_cosine_schedule_with_warmup(opt, int(total * CFG["warmup_ratio"]), total)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp())

    best_f1, best_state = -1.0, None
    for epoch in range(CFG["epochs"]):
        model.train()
        t0, running = time.time(), 0.0
        for step, (input_ids, mask, labels) in enumerate(loader):
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp()):
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
        print(f"Epoch {epoch}: loss {running / max(1, len(loader)):.4f} | val macro-F1 {f1:.4f} | {time.time() - t0:.0f}s")
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
    print(classification_report(va["y"], va_pred, labels=range(len(LABELS)), target_names=LABELS,
                                digits=4, zero_division=0))
    for lang, g in va.assign(pred=va_pred).groupby("language"):
        print(f"  {lang:>4}: macro-F1 {macro_f1(g['y'], g['pred']):.4f} (n={len(g)})")
    np.save(os.path.join(out, "val_logp.npy"), va_logp)

    if test is None:
        return
    te_logp = log_softmax(predict_logits(model, enc(test["text"]), CFG["batch_size"] * 4, collate))
    np.save(os.path.join(out, "test_logp.npy"), te_logp)
    sub = pd.DataFrame({"id": test["id"], "label": [LABELS[i] for i in (te_logp + bias).argmax(1)]})
    assert len(sub) == len(test) and sub["label"].isin(LABELS).all()
    sub.to_csv(os.path.join(out, "submission.csv"), index=False)
    print(sub["label"].value_counts(normalize=True))
    print("Wrote", os.path.join(out, "submission.csv"))


# ---------------------------------------------------------------- Modal (ignored on Kaggle)
if USE_MODAL:
    vol = modal.Volume.from_name("rmit-c1", create_if_missing=True)
    app = modal.App("rmit-c1", image=image)

    @app.function(gpu=os.environ.get("C1_GPU", "A100-40GB"), timeout=4 * 3600, volumes={"/vol": vol})
    def train_remote(config_text: str, run: str) -> dict:
        os.environ["C1_OUT_DIR"] = f"/vol/runs/{run}"
        CFG.update({"data_dir": "/root/data", **parse_config(config_text)})
        main()
        vol.commit()
        d = out_dir()
        return {name: open(os.path.join(d, name), "rb").read() for name in os.listdir(d)}

    @app.local_entrypoint()
    def modal_main(config: str = "", run: str = ""):
        text = ""
        if config:
            with open(config, encoding="utf-8") as f:
                text = f.read()
        run = run or f"{os.path.splitext(os.path.basename(config or 'default'))[0]}_{time.strftime('%m%d_%H%M')}"
        files = train_remote.remote(text, run)
        local = os.path.join(HERE, "outputs", run)
        os.makedirs(local, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(local, name), "wb") as f:
                f.write(data)
        print("Saved:", local, sorted(files))


if __name__ == "__main__":
    CFG.update(load_config_file())
    main()
