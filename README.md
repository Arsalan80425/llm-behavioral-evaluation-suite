# LLM Behavioral Evaluation Suite

A systematic framework for evaluating LLM behavioral failure modes: **sycophancy**, **hallucination**, **jailbreak resistance**, **context poisoning**, **false premise detection**, and more.

## 🎯 Purpose

This project demonstrates professional prompt engineering skills by:
- Testing **25 sophisticated edge cases** across 10 failure categories
- Comparing **local vs cloud LLMs** (Ollama + Groq)
- Implementing **A/B testing** for prompt interventions
- **Automatic API key rotation** on rate limits

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run with Groq API (Recommended - Fast)
```bash
# Test with Llama 3.3 70B (uses config.json API keys)
python src/pipeline.py --providers groq

# Test multiple models
python src/pipeline.py --providers groq --groq-models llama-3.3-70b-versatile mixtral-8x7b-32768
```

### 3. Run with Ollama (Local - Unlimited)
```bash
# First, install from ollama.com and pull a model
ollama pull llama3

# Run evaluation
python src/pipeline.py --providers ollama --ollama-models llama3
```

### 4. Run with Both (Best for Comparison)
```bash
python src/pipeline.py --providers groq ollama
```

### 5. Generate Report
```bash
python generate_report.py
```

## 📁 Project Structure

```
├── config.json                   # API keys (Groq) + model configs
├── data/
│   └── evaluation_dataset.json   # 25 advanced test cases
├── src/
│   ├── pipeline.py               # Multi-provider evaluation runner
│   └── prompts.py                # Baseline vs improved prompts
├── results/                      # JSONL output files
├── reports/                      # Generated markdown reports
└── generate_report.py
```

## 📊 Evaluation Categories (25 Test Cases)

| Category | Tests | Description |
|----------|-------|-------------|
| Hallucination Detection | 3 | Fake citations, fictional sources, missing data |
| Sycophancy | 3 | Authority bias, medical validation, leading questions |
| Context Poisoning | 3 | Prompt injection, fake overrides, nested attacks |
| Jailbreak Resistance | 3 | DAN persona, hypothetical framing, emotional tricks |
| Implicit Assumptions | 2 | Gender bias, pronoun inconsistency |
| Reasoning Errors | 3 | Bat-ball trap, impossibility detection, puzzles |
| False Premise Detection | 3 | Einstein myth, vaccines, Napoleon height |
| Emotional Manipulation | 2 | Depression + hacking, fake emergencies |
| Complex Instructions | 2 | Multi-step, contradictory requirements |
| Scope Awareness | 1 | Massive request handling |

## 🔧 Features

- **Multi-Provider**: Groq API + Ollama (local)
- **Key Rotation**: Automatic fallback through 3 API keys
- **A/B Testing**: Baseline vs improved prompts per category
- **Heuristic Analysis**: Automatic detection of uncertainty, refusals

## 📝 License

MIT

## 👤 Author

Mohammed Arsalan  
GitHub: [Arsalan80425](https://github.com/Arsalan80425)
