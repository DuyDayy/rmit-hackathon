# rmit-hackathon

> One-line pitch of the project. _(TBD — track: Generative AI / Cybersecurity)_

## Problem

_What problem are we solving, and for whom?_

## Solution

_What we built and how it works._

## Architecture

_Diagram / short description (see [`docs/`](docs/))._

## Tech Stack

| Layer | Tools |
|---|---|
| Model / AI | _TBD_ |
| Backend | _TBD_ |
| Frontend | _TBD_ |
| Data / Storage | _TBD_ |
| Deployment | _TBD_ |

## Project Structure

```
rmit-hackathon/
├── app/            # Frontend / demo UI
├── configs/        # Config files (no secrets)
├── data/           # raw / interim / processed / external datasets
├── deployment/     # Docker, infra
├── docs/           # Documentation, diagrams, pitch
├── evaluation/     # Evals, benchmarks, red-teaming
├── models/         # Weights & checkpoints (git-ignored)
├── notebooks/      # Exploration notebooks
├── prompts/        # Prompt templates
├── scripts/        # Utility scripts
├── src/
│   ├── core/       # Config, logging, schemas
│   ├── llm/        # LLM providers & prompting
│   ├── rag/        # Retrieval-Augmented Generation
│   ├── agents/     # Agents & tools
│   ├── ml/         # Classical ML / DL
│   ├── security/   # Detection, scanning, guardrails
│   ├── api/        # Backend API
│   └── utils/      # Helpers
└── tests/          # Tests
```

## Getting Started

```bash
git clone https://github.com/DuyDayy/rmit-hackathon.git
cd rmit-hackathon
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

## Usage

_How to run the app / demo._

## Team

| Name | Role |
|---|---|
| | |

## License

_TBD_
