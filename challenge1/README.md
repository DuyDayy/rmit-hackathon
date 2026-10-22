# Challenge 1 — Multilingual Prompt-Attack Classification

Kaggle: https://www.kaggle.com/competitions/rmit-hackathon-2026 · Metric: **macro F1** · 6 submissions max.
Team **Overfitters** · RMIT SGS · kernel **`RMIT_SGS_Overfitters_C1`**

Classify prompts (PT / FR / IT / EN) as `BENIGN` (62%), `JAILBREAK` (31%), `PROMPT_INJECTION` (7%).
Everything lives in one file, [`RMIT_SGS_Overfitters_C1.py`](RMIT_SGS_Overfitters_C1.py) — the same file is the Kaggle kernel and the Modal job.

## Approach

| Decision | Choice | Why |
|---|---|---|
| Backbone | `jhu-clsp/mmBERT-base` | Best approved model on holdout (0.969), 2× faster than XLM-R large (0.964) |
| Second member | TF-IDF (word 1-2 + char 2-5) + LogisticRegression | No pretrained weights; 0.927–0.938 alone, catches keyword attacks |
| Imbalance | Class-weighted CE (√ inverse freq) | Macro F1 weighs the 7% class equally |
| Threshold | Per-class logit bias tuned on validation | Directly optimises macro F1 |
| Length | `max_len` 512, head + tail truncation | ~2% of prompts truncated; injections often sit at the end |
| Validation | 15% holdout stratified by label × language (or `--folds 5`) | Per-language F1 reported |

Zero-shot (no fine-tuning) with the safety-tuned models scores only 0.43–0.50 macro F1: they are binary
and never predict `PROMPT_INJECTION`, so fine-tuning is required.

## Run

Put `train.csv` and `test.csv` in [`data/`](../data/).

### Modal (training)

```bash
source .venv/bin/activate          # pip install -r requirements.txt
modal run challenge1/RMIT_SGS_Overfitters_C1.py                                   # DEFAULT_CFG = final model
modal run challenge1/RMIT_SGS_Overfitters_C1.py --config a.yaml,b.yaml            # parallel, one GPU each
modal run challenge1/RMIT_SGS_Overfitters_C1.py --config a.yaml --folds 5         # 5 parallel folds + blend
modal run challenge1/RMIT_SGS_Overfitters_C1.py --combine "runA,runB"             # blend finished runs
C1_GPU=L4 modal run challenge1/RMIT_SGS_Overfitters_C1.py --config configs/c1_debug.yaml   # smoke test
```

Outputs land in `challenge1/outputs/<run>/` and the Modal volume `rmit-c1` (`/runs/<run>`, `/combine/<run>`).

GPU (`C1_GPU`, default `A100-40GB`) is not required to be an A100: mmBERT-base fits any ≥16 GB GPU
(`L4`, `A10G`, Kaggle T4). XLM-R large with bs 16 × 512 needs ≥24 GB (`L40S`, `A100`).

### Kaggle (official kernel)

1. New Notebook → paste [`RMIT_SGS_Overfitters_C1.py`](RMIT_SGS_Overfitters_C1.py) as a **Script**.
2. Add input: competition data + model `aisuko/mmbert-base`. Accelerator: GPU T4/P100.
3. Title: `RMIT_SGS_Overfitters_C1`.
4. Save & Run All → submit `/kaggle/working/submission.csv`.

The Modal block is skipped automatically on Kaggle; `DEFAULT_CFG` (bs 16, fp16) is sized for a 16 GB GPU.

## Experiment log (holdout 15%, n = 2100, same split for all runs)

| # | Members | Where | Val macro-F1 | + bias tuning | LB |
|---|---|---|---|---|---|
| 0 | TF-IDF + LR (5-fold CV, all rows) | local CPU | 0.927 | — | — |
| 1 | XLM-R large | Modal A100 | 0.964 | 0.966 | |
| 2 | mmBERT-base | Modal A100 | 0.969 | 0.971 | |
| 3 | **mmBERT-base + TF-IDF** (submitted) | Modal | 0.971 | **0.973** | |
| 4 | mmBERT-base + XLM-R large (+ TF-IDF w=0) | Modal | 0.975 | 0.977 | |
