# Challenge 1 — Multilingual Prompt-Attack Classification

Kaggle: https://www.kaggle.com/competitions/rmit-hackathon-2026 · Metric: **macro F1** · 6 submissions max.

Classify prompts (PT / FR / IT / EN) as `BENIGN` (62%), `JAILBREAK` (31%), `PROMPT_INJECTION` (7%).

## Approach

| Decision | Choice | Why |
|---|---|---|
| Backbone | `FacebookAI/xlm-roberta-large` | Strongest approved multilingual encoder; fits a Kaggle T4/P100 in fp16 |
| Fallback | `jhu-clsp/mmBERT-base` | Faster; switch via `CFG["model_hint"]` |
| Imbalance | Class-weighted CE (√ inverse freq) | Macro F1 weighs the 7% class equally |
| Threshold | Per-class logit bias tuned on val | Directly optimises macro F1 |
| Truncation | Head + tail tokens | Injections often appear at the end of long prompts |
| Validation | 15% holdout stratified by label × language | Report per-language F1 |

## Run on Kaggle

1. New Notebook → File → Import / paste [`kernel.py`](kernel.py) as a **Script**.
2. Add input: competition data + model `aisuko/xlm-roberta-large`.
3. Accelerator: GPU. Title: `<university>_<campus>_<team>_C1` (e.g. `RMIT_SGS_myteam_C1`).
4. Save & Run All → submit `/kaggle/working/submission.csv`.

## Experiment log

| # | Model | Changes | Val macro-F1 | LB |
|---|---|---|---|---|
| 1 | xlm-roberta-large | baseline | | |
