"""
RMIT Hackathon 2026 - Challenge 1: Multilingual Prompt-Attack Classification

Chosen model: jhu-clsp/mmBERT-base  (approved list) + TF-IDF/LogisticRegression blend (no pretrained weights)
Holdout (15%, stratified label x language) macro-F1: mmBERT-base 0.969 -> + TF-IDF + bias tuning 0.973

One file, three ways to run:
  Kaggle  : paste as a Script kernel, Save & Run All (uses DEFAULT_CFG)
            add data "rmit-hackathon-2026" + model aisuko/mmbert-base, GPU T4/P100 on
            title: RMIT_SGS_Overfitters_C1
  Modal   : modal run challenge1/RMIT_SGS_Overfitters_C1.py --config configs/c1_modal_xlmr_large.yaml
            modal run challenge1/RMIT_SGS_Overfitters_C1.py --config a.yaml,b.yaml --folds 5   (one GPU per fold, parallel)
            modal run challenge1/RMIT_SGS_Overfitters_C1.py --combine "runA_f0+runA_f1+...,runB"  (blend finished runs)
            C1_GPU=L4 modal run ...   (default A100-40GB; any >=16 GB GPU fits mmBERT-base)
  Local   : python challenge1/RMIT_SGS_Overfitters_C1.py --config configs/c1_debug.yaml

Pipeline:
  holdout or k-fold split (stratified label x language) -> fine-tune with class-weighted CE
  -> keep best epoch by val macro-F1 -> blend with TF-IDF + LR (weight tuned on out-of-fold)
  -> tune per-class logit bias on out-of-fold -> predict test -> submission.csv
"""
import argparse
import contextlib
import glob
import itertools
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
    from scipy.sparse import hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, f1_score
    from sklearn.model_selection import StratifiedKFold, train_test_split
    from torch import nn
    from torch.utils.data import DataLoader
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              PreTrainedTokenizerFast, get_cosine_schedule_with_warmup)

DEFAULT_CFG = dict(
    model_hint="mmbert-base",        # substring of the model folder under /kaggle/input
    model_path=None,                 # explicit local dir or HF id; overrides model_hint
    data_dir=None,                   # folder with train.csv/test.csv; None = auto-search
    max_rows=None,                   # subsample train for quick debugging
    max_len=512,                     # p90 ~260 tokens, ~2% of prompts truncated (head + tail kept)
    batch_size=16,                   # fits a 16 GB T4 in fp16; use 8 x grad_accum 2 if OOM
    grad_accum=1,
    epochs=4,                        # best epoch is kept (epoch 2 of 0-3 on holdout)
    lr=3e-5,
    weight_decay=0.01,
    warmup_ratio=0.1,
    val_size=0.15,                   # holdout size when n_folds <= 1
    n_folds=0,                       # >1 = k-fold CV (out-of-fold preds on all rows, test averaged)
    fold=None,                       # run only this fold (Modal runs folds in parallel); None = all
    seed=42,                         # training seed (init, shuffling)
    split_seed=42,                   # keep fixed so runs can be ensembled on the same rows
    class_weight_power=0.5,          # 0 = no weighting, 1 = full inverse frequency
    fp16=True,
    tfidf=True,                      # blend with TF-IDF + LR (5-fold CV ~0.927 macro-F1 alone)
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


SPECIAL_TOKENS = {
    "pad_token": ["[PAD]", "<pad>"], "cls_token": ["[CLS]", "<s>", "<cls>"],
    "sep_token": ["[SEP]", "</s>", "<sep>"], "unk_token": ["[UNK]", "<unk>"], "mask_token": ["[MASK]", "<mask>"],
}


def load_tokenizer(model_dir, model_config):
    try:
        return AutoTokenizer.from_pretrained(model_dir)
    except (ValueError, AttributeError) as e:
        # Checkpoints saved with transformers v5 use a tokenizer_config v4 can't parse;
        # the raw tokenizer.json (incl. its post-processor) still loads as a plain fast tokenizer.
        print("AutoTokenizer failed, loading tokenizer.json directly:", repr(e))
        if os.path.isdir(model_dir):
            path = os.path.join(model_dir, "tokenizer.json")
        else:
            from huggingface_hub import hf_hub_download
            path = hf_hub_download(model_dir, "tokenizer.json")
        tok = PreTrainedTokenizerFast(tokenizer_file=path)
        vocab = tok.get_vocab()
        for attr, cands in SPECIAL_TOKENS.items():
            hit = next((c for c in cands if c in vocab), None)
            if hit:
                setattr(tok, attr, hit)
        if tok.pad_token is None and model_config.pad_token_id is not None:
            tok.pad_token = tok.convert_ids_to_tokens(model_config.pad_token_id)
        return tok


def load_data():
    train = pd.read_csv(find_input("train.csv"))
    test_path = find_input("test.csv", required=False)
    test = pd.read_csv(test_path) if test_path else None
    if test is None:
        print("test.csv not found -> train + validate only, no submission")
    if CFG["max_rows"] and CFG["max_rows"] < len(train):
        train = train.sample(CFG["max_rows"], random_state=CFG["split_seed"])
    train = train.reset_index(drop=True)
    for df in (train, test):
        if df is not None:
            df["text"] = df["text"].fillna("").astype(str)
    train["y"] = train["label"].map(L2I)
    assert train["y"].notna().all(), f"Unknown labels: {set(train['label']) - set(LABELS)}"
    return train, test


def make_folds(train, n_folds, seed):
    """Fold id per row. Holdout (n_folds <= 1): val rows = 0, train rows = -1."""
    key = train["label"] + "_" + train["language"].astype(str)
    fold = np.full(len(train), -1)
    if n_folds > 1:
        skf = StratifiedKFold(n_folds, shuffle=True, random_state=seed)
        for k, (_, v) in enumerate(skf.split(train, key)):
            fold[v] = k
    else:
        _, va = train_test_split(np.arange(len(train)), test_size=CFG["val_size"],
                                 random_state=seed, stratify=key)
        fold[va] = 0
    return fold


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


# ---------------------------------------------------------------- metrics / blending
def macro_f1(y, pred):
    return f1_score(y, pred, average="macro", labels=list(range(len(LABELS))))


def log_softmax(x):
    x = x - x.max(1, keepdims=True)
    return x - np.log(np.exp(x).sum(1, keepdims=True))


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


def blend(members, y):
    """Grid-search simplex weights (step 0.1) over member log-probs to maximise macro-F1."""
    if len(members) == 1:
        return np.ones(1), macro_f1(y, members[0].argmax(1))
    steps = np.round(np.arange(0, 1.01, 0.1), 2)
    best = (-1.0, None)
    for w in itertools.product(steps, repeat=len(members) - 1):
        if sum(w) > 1 + 1e-9:
            continue
        w = np.array(list(w) + [1 - sum(w)])
        s = macro_f1(y, sum(wi * m for wi, m in zip(w, members)).argmax(1))
        if s > best[0]:
            best = (s, w)
    return best[1], best[0]


def tfidf_predict(train, test, n_folds=5):
    """TF-IDF (word 1-2 + char 2-5) + LR: out-of-fold log-probs on train, full-fit log-probs on test."""
    def fit_predict(tr_text, tr_y, pred_texts):
        w = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200000)
        c = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True,
                            max_features=300000)
        X = hstack([w.fit_transform(tr_text), c.fit_transform(tr_text)]).tocsr()
        clf = LogisticRegression(C=8, max_iter=3000, class_weight="balanced").fit(X, tr_y)
        return [np.log(np.clip(clf.predict_proba(hstack([w.transform(t), c.transform(t)]).tocsr()), 1e-9, 1))
                for t in pred_texts]

    t0 = time.time()
    oof = np.zeros((len(train), len(LABELS)))
    fold = make_folds(train, n_folds, CFG["split_seed"] + 1)
    for k in range(n_folds):
        v = fold == k
        oof[v] = fit_predict(train["text"][~v], train["y"][~v], [train["text"][v]])[0]
    te = fit_predict(train["text"], train["y"], [test["text"]])[0] if test is not None else None
    print(f"TF-IDF OOF macro-F1 {macro_f1(train['y'], oof.argmax(1)):.4f} | {time.time() - t0:.0f}s")
    return oof, te


def finalize(train, test, members, test_members, names, out):
    """members: OOF log-probs aligned to `train` rows (NaN where missing). Blend, tune bias, write submission."""
    mask = np.all([~np.isnan(m[:, 0]) for m in members], axis=0)
    y = train["y"].values[mask]
    ms = [m[mask] for m in members]
    for n, m in zip(names, ms):
        print(f"  member {n:<40} macro-F1 {macro_f1(y, m.argmax(1)):.4f}")
    weights, f1_blend = blend(ms, y)
    logp = sum(w * m for w, m in zip(weights, ms))
    bias, tuned = np.zeros(len(LABELS)), f1_blend
    if CFG["tune_bias"]:
        bias, tuned = tune_bias(logp, y)
    print(f"Blend weights {dict(zip(names, weights.round(2)))} | macro-F1 {f1_blend:.4f} "
          f"-> bias-tuned {tuned:.4f} | bias {bias.round(2)} | n={mask.sum()}")

    pred = (logp + bias).argmax(1)
    print(classification_report(y, pred, labels=range(len(LABELS)), target_names=LABELS,
                                digits=4, zero_division=0))
    per_lang = {}
    for lang, g in train[mask].assign(pred=pred).groupby("language"):
        per_lang[lang] = round(macro_f1(g["y"], g["pred"]), 4)
        print(f"  {lang:>4}: macro-F1 {per_lang[lang]:.4f} (n={len(g)})")
    metrics = {"members": names, "weights": weights.round(2).tolist(), "val_f1_blend": round(f1_blend, 4),
               "val_f1_tuned": round(tuned, 4), "bias": bias.round(2).tolist(), "per_lang": per_lang,
               "n_eval": int(mask.sum())}
    if test is not None and all(t is not None for t in test_members):
        te = sum(w * t for w, t in zip(weights, test_members)) + bias
        sub = pd.DataFrame({"id": test["id"], "label": [LABELS[i] for i in te.argmax(1)]})
        assert len(sub) == len(test) and sub["label"].isin(LABELS).all()
        sub.to_csv(os.path.join(out, "submission.csv"), index=False)
        metrics["test_dist"] = sub["label"].value_counts(normalize=True).round(4).to_dict()
        print(sub["label"].value_counts(normalize=True))
        print("Wrote", os.path.join(out, "submission.csv"))
    return metrics


# ---------------------------------------------------------------- transformer
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


def train_transformer(tr, va, test):
    """Fine-tune on tr, keep best epoch by va macro-F1. Returns (va_logp, test_logp | None, best_f1)."""
    seed_everything(CFG["seed"])
    model_dir = find_model_dir()
    print("Model:", model_dir, "| train", len(tr), "| val", len(va))
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I,
        ignore_mismatched_sizes=True,  # safety-tuned backbones ship their own head
    ).to(DEVICE)
    tok = load_tokenizer(model_dir, model.config)

    enc = Encoder(tok, CFG["max_len"])
    lens = np.array([len(x) for x in tok(tr["text"].tolist(), add_special_tokens=False)["input_ids"]])
    print("Token length p50/p90/p99/max:", np.percentile(lens, [50, 90, 99, 100]).astype(int),
          f"| truncated: {np.mean(lens > enc.body):.1%}")
    tr_ids, va_ids = enc(tr["text"]), enc(va["text"])
    collate = make_collate(tok.pad_token_id)
    bs_eval = CFG["batch_size"] * 4

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

        va_logits = predict_logits(model, va_ids, bs_eval, collate)
        f1 = macro_f1(va["y"], va_logits.argmax(1))
        print(f"Epoch {epoch}: loss {running / max(1, len(loader)):.4f} | val macro-F1 {f1:.4f} | {time.time() - t0:.0f}s")
        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    va_logp = log_softmax(predict_logits(model, va_ids, bs_eval, collate))
    te_logp = log_softmax(predict_logits(model, enc(test["text"]), bs_eval, collate)) if test is not None else None
    del model, opt
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    return va_logp, te_logp, best_f1


def main():
    global DEVICE
    DEVICE = pick_device()
    out = out_dir()
    os.makedirs(out, exist_ok=True)
    print("CFG:", CFG, "| device:", DEVICE, "| out:", out)

    train, test = load_data()
    print("train", train.shape, "test", None if test is None else test.shape)
    print(pd.crosstab(train["language"], train["label"], margins=True))

    fold = make_folds(train, CFG["n_folds"], CFG["split_seed"])
    folds = [CFG["fold"]] if CFG["fold"] is not None else sorted(set(fold) - {-1})
    oof = np.full((len(train), len(LABELS)), np.nan)
    te_parts, fold_f1 = [], {}
    for k in folds:
        va_mask = fold == k
        v, t, f1 = train_transformer(train[~va_mask], train[va_mask], test)
        oof[va_mask] = v
        fold_f1[int(k)] = round(f1, 4)
        if t is not None:
            te_parts.append(t)
    te_logp = np.mean(te_parts, axis=0) if te_parts else None

    have = ~np.isnan(oof[:, 0])
    np.save(os.path.join(out, "oof_logp.npy"), oof[have])
    np.save(os.path.join(out, "oof_ids.npy"), np.asarray(train["id"].astype(str).tolist(), dtype="U")[have])
    if te_logp is not None:
        np.save(os.path.join(out, "test_logp.npy"), te_logp)
    metrics = {"model": find_model_dir(), "fold_f1": fold_f1, "cfg": CFG}

    if CFG["fold"] is not None:  # partial run of a parallel k-fold job; blended later by --combine
        print("Fold", CFG["fold"], "done:", fold_f1)
    else:
        members, tests, names = [oof], [te_logp], ["transformer"]
        if CFG["tfidf"]:
            tf_oof, tf_te = tfidf_predict(train, test)
            members.append(tf_oof)
            tests.append(tf_te)
            names.append("tfidf")
        metrics.update(finalize(train, test, members, tests, names, out))
    with open(os.path.join(out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)


def combine(member_specs, out, use_tfidf=True, runs_root="/vol/runs"):
    """Blend finished runs. member_specs: list of lists of run names (folds of one model are concatenated)."""
    train, test = load_data()
    row = {i: n for n, i in enumerate(train["id"].astype(str))}
    members, tests, names = [], [], []
    for runs in member_specs:
        m = np.full((len(train), len(LABELS)), np.nan)
        te = []
        for r in runs:
            d = os.path.join(runs_root, r)
            ids_f = "oof_ids.npy" if os.path.exists(os.path.join(d, "oof_ids.npy")) else "val_ids.npy"
            lp_f = "oof_logp.npy" if os.path.exists(os.path.join(d, "oof_logp.npy")) else "val_logp.npy"
            m[[row[str(i)] for i in np.load(os.path.join(d, ids_f), allow_pickle=True)]] = np.load(os.path.join(d, lp_f))
            if os.path.exists(os.path.join(d, "test_logp.npy")):
                te.append(np.load(os.path.join(d, "test_logp.npy")))
        members.append(m)
        tests.append(np.mean(te, axis=0) if len(te) == len(runs) else None)
        names.append("+".join(runs) if len(runs) == 1 else f"{runs[0]}(x{len(runs)})")
    if use_tfidf:
        tf_oof, tf_te = tfidf_predict(train, test)
        members.append(tf_oof)
        tests.append(tf_te)
        names.append("tfidf")
    os.makedirs(out, exist_ok=True)
    metrics = finalize(train, test, members, tests, names, out)
    with open(os.path.join(out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


# ---------------------------------------------------------------- Modal (ignored on Kaggle)
if USE_MODAL:
    vol = modal.Volume.from_name("rmit-c1", create_if_missing=True)
    app = modal.App("rmit-c1", image=image)

    def _collect(d):
        return {name: open(os.path.join(d, name), "rb").read() for name in os.listdir(d)
                if os.path.isfile(os.path.join(d, name))}

    @app.function(gpu=os.environ.get("C1_GPU", "A100-40GB"), timeout=4 * 3600, volumes={"/vol": vol})
    def train_remote(config_text: str, run: str) -> dict:
        os.environ["C1_OUT_DIR"] = f"/vol/runs/{run}"
        CFG.update({"data_dir": "/root/data", **parse_config(config_text)})
        main()
        vol.commit()
        return _collect(out_dir())

    @app.function(cpu=8, memory=16384, timeout=3600, volumes={"/vol": vol})
    def combine_remote(member_specs: list, name: str, use_tfidf: bool = True) -> dict:
        vol.reload()
        CFG.update({"data_dir": "/root/data"})
        out = f"/vol/combine/{name}"
        combine(member_specs, out, use_tfidf)
        vol.commit()
        return _collect(out)

    def _save(name, files, sub="outputs"):
        local = os.path.join(HERE, sub, name)
        os.makedirs(local, exist_ok=True)
        for fname, data in files.items():
            with open(os.path.join(local, fname), "wb") as f:
                f.write(data)
        print("Saved:", local, sorted(files))

    @app.local_entrypoint()
    def modal_main(config: str = "", run: str = "", folds: int = 0, combine: str = "", tfidf: bool = True):
        """
        --config a.yaml,b.yaml   each config in its own GPU container, in parallel
        --folds 5                split every config into 5 parallel fold containers, then blend all
        --combine "r1_f0+r1_f1,r2"  blend finished runs ('+' joins folds of one model, ',' separates models)
        """
        stamp = time.strftime("%m%d_%H%M")
        if combine:
            specs = [s.split("+") for s in combine.split(",") if s]
            name = run or f"combine_{stamp}"
            files = combine_remote.remote(specs, name, tfidf)
            _save(name, files)
            print(json.loads(files["metrics.json"]))
            return

        configs = [c.strip() for c in config.split(",") if c.strip()] or [""]
        jobs = []  # (model_group, run_name, call)
        for c in configs:
            text = ""
            if c:
                with open(c, encoding="utf-8") as f:
                    text = f.read()
            base = os.path.splitext(os.path.basename(c or "default"))[0]
            if folds > 1:
                for k in range(folds):
                    name = f"{base}_f{k}_{stamp}"
                    jobs.append((base, name, train_remote.spawn(f"{text}\nn_folds: {folds}\nfold: {k}\n", name)))
                    print("Spawned", name)
            else:
                name = run if run and len(configs) == 1 else f"{base}_{stamp}"
                jobs.append((base, name, train_remote.spawn(text, name)))
                print("Spawned", name)

        done = {}
        for base, name, call in jobs:
            try:
                files = call.get()
            except Exception as e:
                print(f"FAILED {name}: {e!r}")
                continue
            _save(name, files)
            done.setdefault(base, []).append(name)
            m = json.loads(files["metrics.json"])
            print(f"  {name}: fold F1 {m.get('fold_f1')} | blended {m.get('val_f1_tuned', '-')}")

        if folds > 1:
            specs = [runs for base, runs in done.items() if len(runs) == folds]
            if len(specs) < len(done):
                print("Some folds failed; blending only complete models:", [s[0] for s in specs])
            if specs:
                name = f"combine_{stamp}"
                files = combine_remote.remote(specs, name, tfidf)
                _save(name, files)
                print(json.loads(files["metrics.json"]))


if __name__ == "__main__":
    CFG.update(load_config_file())
    main()
