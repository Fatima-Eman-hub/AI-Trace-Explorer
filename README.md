# 🧠 AI Trace Explorer

**A full-stack LLMOps observability platform** that traces, evaluates, and analyzes every stage of an LLM request pipeline across multiple providers (Claude, Groq, Gemini) in real time.

> Open the black box of your LLM calls — full pipeline tracing, quality evaluation, and cost analytics.

<!-- 🎬 DEMO: replace this with a GIF or screenshot once recorded -->
<!-- ![demo](docs/demo.gif) -->

**🔗 Live Demo:** _[coming soon]_ &nbsp;•&nbsp; **📹 Video Walkthrough:** _[coming soon]_

---

## 🎯 The Problem

When you call an LLM API, everything between your prompt and the response is a black box — you can't see how the prompt was formatted, how many tokens were used, which provider handled it, how long each internal step took, or whether the response can actually be trusted. In production AI systems, this makes debugging failures and controlling cost extremely difficult.

**AI Trace Explorer** makes that pipeline fully observable — every request is broken into 7 traced stages, each one timed, logged, and inspectable after the fact.

---

## ✨ Features

- **7-stage traced pipeline** — prompt building → tokenization → provider routing → LLM call → response parsing → quality evaluation → cost calculation
- **Multi-provider support** — Anthropic Claude, Groq (free tier), Google Gemini (free tier), added through a provider-agnostic gateway pattern
- **Dependency-free quality evaluation** — relevancy, hallucination risk, and faithfulness scored with pure-Python heuristics (no heavy ML dependencies)
- **Automatic failure classification** — errors are categorized (auth, rate limits, deprecated models, timeouts...) with suggested root-cause fixes
- **Real-time streaming** — watch each pipeline stage complete live via WebSocket
- **Cost & latency analytics** — aggregated trends by model, by hour, with quality distribution breakdowns
- **Search, export (CSV/JSON), rate limiting, optional API-key auth**
- **Interactive frontend** — built in vanilla HTML/CSS/JS, including animated visualizations of what each stage is actually doing (prompt assembly, tokenization, evaluation scoring)

---

## 🏗️ Architecture

```
┌─────────────┐      HTTP / WebSocket      ┌──────────────────────────┐
│  Frontend   │ ─────────────────────────▶ │      FastAPI Backend     │
│ (HTML/CSS/  │                            │                          │
│     JS)     │ ◀───────────────────────── │  ┌────────────────────┐  │
└─────────────┘                            │  │  7-Stage Pipeline  │  │
                                            │  │  1. Prompt Builder │  │
                                            │  │  2. Tokenizer      │  │
                                            │  │  3. LLM Gateway    │──┼──▶ Claude / Groq / Gemini
                                            │  │  4. LLM Call       │  │
                                            │  │  5. Response Parser│  │
                                            │  │  6. Evaluator      │  │
                                            │  │  7. Cost Calculator│  │
                                            │  └────────┬───────────┘  │
                                            │           ▼              │
                                            │   SQLAlchemy + SQLite    │
                                            └──────────────────────────┘
```

Every stage inherits from a shared `BaseStage` class (Template Method pattern) that handles timing, error capture, and database logging centrally — each stage only implements its own logic.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite (dev) |
| LLM Providers | Anthropic SDK, Groq SDK, Google Generative AI SDK |
| Frontend | HTML5, CSS3 (custom design system), vanilla JavaScript |
| Testing | Pytest (models, stages, API, analytics, evaluator) |
| Real-time | Native WebSockets (FastAPI + browser WebSocket API) |

---

## 📂 Project Structure

```
AITraceExplorer/
├── backend/
│   ├── app/
│   │   ├── api/            # REST route handlers
│   │   ├── models/         # SQLAlchemy models
│   │   ├── stages/         # The 7 pipeline stages
│   │   ├── config.py
│   │   ├── security.py     # Auth + rate limiting
│   │   ├── failure_classifier.py
│   │   ├── pipeline.py     # Orchestrator
│   │   └── seed.py
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
└── frontend/
    ├── assets/
    │   ├── style.css
    │   └── app.js
    ├── index.html           # Dashboard
    ├── traces.html          # Trace history
    ├── trace.html           # Trace detail
    ├── new-request.html     # Live pipeline test
    ├── analytics.html
    └── models.html
```

---

## 🚀 Getting Started

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\Activate.ps1        # Windows
# source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
cp .env.example .env             # then fill in your API keys
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000` — interactive API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
python -m http.server 5173
```

Open `http://localhost:5173/index.html`.

### Free API keys (no credit card needed)
- **Groq:** https://console.groq.com
- **Google Gemini:** https://aistudio.google.com/apikey

---

## 🧪 Testing

```bash
cd backend
pytest -v
```

Covers: database models, all 7 pipeline stages, REST API endpoints, analytics aggregation, and the evaluation engine's scoring logic.

---

## 📊 Design Decisions & Known Limitations

- **Evaluation is heuristic, not ML-based.** Relevancy/hallucination/faithfulness scores use pure-Python word-overlap and claim-verification heuristics rather than embedding models — this keeps the system dependency-free and fast, at the cost of true semantic understanding. Documented as an intentional MVP trade-off with a clear upgrade path to embedding-based scoring.
- **Failure classification is rule-based.** Errors are categorized via keyword matching, not an LLM judge — same reasoning as above.
- **Rate limiting is in-memory**, which resets on restart and doesn't scale across multiple server processes — acceptable for this project's scope, would move to Redis for a multi-instance deployment.
- **LLM provider model IDs change.** During development, both Groq and Google deprecated model IDs mid-project (`llama-3.3-70b-versatile`, `gemini-2.0-flash`) — the provider layer is intentionally isolated in `llm_call.py` so these are one-line updates.

---

## 📝 License

MIT (or: not licensed, all rights reserved — update to match your repo)

## 👤 Author

**Fatima Eman** — BS Artificial Intelligence, Air University, Islamabad
[GitHub](https://github.com/Fatima-Eman-hub) • [LinkedIn](https://linkedin.com/in/fatima-eman01)
