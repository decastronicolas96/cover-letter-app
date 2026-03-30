# AI-Powered Cover Letter & Application Generator

A production-grade Streamlit application that automates cover letter generation for MBA recruiting using multi-agent prompt orchestration, hybrid deterministic/LLM evaluation, and real-time quality observability. Built with Python and the Google Gemini API.

## Problem Statement

Cover letters in 2026 face a paradox: candidates use AI to write them while recruiters use AI to detect and reject generic AI output. Research shows 88% of job seekers believe cover letters improve interview chances, yet recruiter tolerance for detectable AI-generated content has dropped sharply. This application solves the problem by engineering outputs that are structurally optimized for ATS parsers, linguistically authentic to bypass AI detection, and narratively compelling for human readers.

## Architecture Overview

```
                        +------------------+
                        |   Streamlit UI   |
                        |   (app.py)       |
                        +--------+---------+
                                 |
              +------------------+------------------+
              |                  |                  |
     +--------v-------+ +-------v--------+ +-------v--------+
     | Standard Flow  | | Quick Flow     | | QA Flow        |
     | (4-step HITL)  | | (Direct PDF)   | | (Text answers) |
     +--------+-------+ +-------+--------+ +-------+--------+
              |                  |                  |
              v                  v                  v
     +--------------------------------------------------+
     |         Multi-Agent Prompt Pipeline               |
     |  Research -> Match -> Draft -> Critique -> Revise |
     +--------------------------------------------------+
              |                  |
     +--------v-------+ +-------v--------+
     | Deterministic  | | LLM Subjective |
     | Critique       | | Critique       |
     | (evaluator.py) | | (Gemini Flash) |
     +--------+-------+ +-------+--------+
              |                  |
              v                  v
     +--------------------------------------------------+
     |          Quality Dashboard (Sidebar)              |
     |  Score | Burstiness | Keywords | Cost Tracking    |
     +--------------------------------------------------+
              |
     +--------v---------+
     |  Session Logger   |  -->  eval_runner.py (offline)
     |  (logger.py)      |       LLM-as-Judge batch eval
     +-------------------+
```

## Key Technical Decisions

### Multi-Agent Prompt Pipeline
Each LLM call has a specialized persona and constrained scope, preventing the quality degradation that occurs with monolithic prompts:

| Agent | Role | Model | Purpose |
|-------|------|-------|---------|
| Researcher | Company Intel | gemini-2.5-flash + Google Search | Fetches recent news, product launches, and market context for authentic hooks |
| Strategist | JD Analyst | gemini-2.5-pro | Extracts core requirements, matches to story bank, identifies gaps, extracts ATS keywords |
| Copywriter | Drafter | gemini-2.5-pro | Generates the letter using approved strategy, golden examples, and enriched context |
| Editor | Deterministic QA | Python (no LLM) | Checks 7 mechanical rules with zero hallucination risk |
| Critic | Subjective QA | gemini-2.5-flash | Evaluates hook specificity, narrative depth, sentence rhythm, closing quality |
| Corrector | Reviser | gemini-2.5-pro | Applies user feedback + critique failures while preserving valid sections |

### Hybrid Evaluation System
The critique system splits mechanical checks (deterministic Python) from subjective checks (LLM), solving the problem of LLMs hallucinating "PASS" on objective rules:

- **Deterministic checks** (instant, 0 tokens): em dashes, 40+ banned words/phrases, formatting, generic openings, word count, "I" sentence frequency, work authorization mentions
- **LLM checks** (1 API call): metrics density, structure validation, timeline accuracy, hook specificity, narrative depth, sentence rhythm, closing specificity

### Anti-AI Detection Engineering
The system prompt embeds linguistic rules derived from AI detection research on perplexity and burstiness:

- **Burstiness enforcement**: Mandatory sentence length variation (4-8 word punchy sentences mixed with 25+ word complex ones)
- **Perplexity engineering**: Banned 40+ high-probability AI tokens (delve, robust, seamless, leverage, etc.) plus 10+ cliche phrase patterns
- **Structural variation**: No 3 consecutive sentences with same grammatical structure or opening word

### Real-Time Quality Observability
A sidebar dashboard provides instant feedback on every draft:

- **Quality Score** (0-100): Composite of deterministic checks, burstiness, and keyword coverage
- **Burstiness Score**: Sentence length standard deviation (human writing >7, AI typically 3-5)
- **JD Keyword Coverage**: Percentage of top JD-specific terms embedded in the letter
- **Session Cost**: Per-step USD cost estimate based on Gemini pricing (pro: $1.25/$10 per 1M tokens in/out; flash: $0.15/$0.60)
- **Token tracking**: Input/output tokens per API call with model attribution

## Features

### Three Generation Workflows

1. **Standard Flow (Human-in-the-Loop)**
   Company research -> JD matching -> strategy review -> drafting -> hybrid critique -> iterative revision (up to 5x) -> PDF export

2. **Quick Flow (Direct to PDF)**
   Company research -> JD matching -> drafting -> deterministic critique -> PDF export. Optimized for speed while still running mechanical quality checks.

3. **Application Questions Flow**
   Generates concise, metrics-driven answers to open-ended application questions, contextualized to the target role.

### Company Research via Google Search Grounding
The app auto-extracts the company name from the JD and queries Gemini with Google Search grounding to fetch recent news, product launches, and market context. This data feeds into both the matching and drafting steps, producing hooks that reference real, verifiable company-specific facts.

### Session Logging & Offline Evaluation
Every session logs inputs, outputs, quality metrics, and token usage to a local JSONL file. An offline batch evaluator (`eval_runner.py`) scores historical outputs on 5 dimensions using LLM-as-Judge methodology, enabling longitudinal quality tracking across prompt iterations.

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit | Multi-step UI with session state management |
| LLM Engine | Google Gemini 2.5 (Pro + Flash) | Dual-model architecture: Pro for quality-critical steps, Flash for speed-optimized steps |
| Search Grounding | Google Search API (via Gemini) | Real-time company intelligence for authentic hooks |
| Evaluation | Python stdlib + Gemini Flash | Hybrid deterministic/LLM critique pipeline |
| PDF Generation | ReportLab + pypdf | CBS-standard formatting (8.5x11, 0.75" margins, Times-Roman 12pt) with page count validation |
| Logging | JSON Lines (local) | Session-level observability for offline analysis |
| Deployment | Streamlit Community Cloud | GitHub-connected CI/CD |

## Project Structure

```
cover-letter-app/
  app.py              # Main application: UI, workflow orchestration, API calls, dashboard
  prompts.py          # All LLM prompts: system, matching, drafting, critique, revision, QA, research
  context_data.py     # Embedded data: CV, 16 STAR stories, story index, golden examples, positioning guide
  evaluator.py        # Deterministic critique engine, quality score, burstiness, keyword coverage
  logger.py           # Session-level JSONL logger for offline evaluation
  eval_runner.py      # LLM-as-Judge batch evaluator (5-dimension scoring)
  pdf_generator.py    # ReportLab PDF builder with page count validation
  requirements.txt    # Dependencies
  .gitignore          # Excludes secrets, cache, session logs
```

## Running Locally

```bash
pip install -r requirements.txt
```

Add your Gemini API key in `.streamlit/secrets.toml`:
```toml
[gemini]
api_key = "YOUR_API_KEY_HERE"
```

```bash
streamlit run app.py
```

### Running Offline Evaluations

```bash
# Evaluate all logged sessions using LLM-as-Judge
python eval_runner.py session_logs/sessions.jsonl

# Use a specific model
python eval_runner.py session_logs/sessions.jsonl --model gemini-2.5-pro
```

## Security

- API keys managed via `.streamlit/secrets.toml` (git-ignored)
- All prompts include security guardrails against prompt injection via JD text
- Session logs exclude raw JD text (only length stored) to avoid PII leakage
