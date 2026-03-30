# Technical Architecture & Implementation Notes

This document provides an in-depth overview of the technical architecture, logic flows, agentic prompts, and internal functions of the Nicolas Cover Letter Generator application.

## 1. High-Level Architecture

The application is a stateless-turned-stateful web application built with **Streamlit** for the frontend and **Google Gemini API** (`google-genai` SDK) for the intelligent backend. Session state (`st.session_state`) is heavily utilized to manage the user's progression through a multi-step workflow.

### Core Stack
- **Frontend/Routing:** Streamlit (`app.py`)
- **LLM Engine:** Google Gemini (models: `gemini-2.5-flash` and `gemini-2.5-pro`)
- **PDF Construction:** `reportlab` (for drawing layout/text) and `pypdf` (for real-time page-count validation)
- **Data Layer:** Static Python variables (`context_data.py` and `prompts.py`) to hold context, CV data, and system instructions. 

---

## 2. Workflows & Application State

The application operates on a 5-step state machine tracked by `st.session_state.step`. 

### State Machine Overview
- **Step 1: Input:** Users paste the Job Description (JD), Application Questions, and Additional Context.
- **Step 2: Strategy Review:** (Standard flow only) Displays the AI's "Matching Matrix" strategy for user approval.
- **Step 3: Draft Review:** Displays the drafted letter + critique results. Allows the user to provide feedback and trigger AI revisions.
- **Step 4: PDF Ready:** Confirms the letter is finalized and triggers the `reportlab` PDF generator for download.
- **Step 5: QA Results:** (Application Questions flow only) Displays generated answers for copy-pasting.

### 3 Distinct End-to-End Workflows 

1. **Standard Generative Flow (Human-in-the-Loop)**
   - **Step 1 → Step 2:** AI matches JD to context and creates a strategy matrix. User reviews/edits strategy.
   - **Step 2 → Step 3:** AI drafts the letter based on the approved strategy, immediately runs a self-critique, and presents the draft + evaluation to the user. User can iteratively refine (up to 5 times) by providing text feedback.
   - **Step 3 → Step 4:** User approves the latest draft, and the PDF is generated.

2. **Quick Generation Flow (🏎️ Direct to PDF)**
   - Skips Step 2 completely. 
   - **Step 1 → Step 4:** AI analyzes the JD, creates the strategy matrix in the background, drafts the cover letter out of sight, and lands the user immediately on Step 4 (Draft Review) allowing them to quickly revise or download.

3. **Answer App Questions Flow (📝 Text Only)**
   - Used for open-ended application text boxes.
   - **Step 1 → Step 5:** Ingests JD and specific questions. Uses the `QA_PROMPT` to formulate tight, metric-driven answers drawing from the user's CV/Experience.

---

## 3. Agentic Design & LLM Calls

The system utilizes an agent-like progression where specialized prompts act on the outputs of previous LLM calls.

### The Prompts (`prompts.py`)
- **SYSTEM PROMPT:** Defines the persona (Nicolas De Castro, MBA student), background structure, strict writing rules (no em dashes, no specific buzzwords, 4-paragraph limit), and chronological constraints.
- **MATCHING PROMPT:** Acts as the *Strategist Analyst*. Extracts core JD requirements, matches them to Nicolas's "Story Index" and CV, and flags any gaps or red flags. Outputs a matrix.
- **DRAFTING PROMPT:** Acts as the *Copywriter*. Takes the output of the Matching Matrix, the specific selected stories, and Golden Examples to generate a tailored 4-paragraph letter.
- **CRITIQUE PROMPT:** Acts as the *Automated Editor*. Evaluates the drafted text strictly against a 10-point checklist (banned words, formatting rules, length criteria, 'I' sentence limits). Outputs a deterministic JSON payload with Pass/Fail for each rule.
- **REVISION PROMPT:** Acts as the *Corrector*. Ingests the draft, the user's feedback, and the critique failures to output a new version.
- **QA PROMPT:** Acts as the *Career Strategist*. Focuses on brief, factual responses to recruiter questions.

### The Wrapper Function (`app.py`)
All LLM interaction is handled via `call_gemini(client, user_prompt, model_name)`:
- Centralized exception handling.
- Maps specific Gemini `Exception` error codes (429, 400, 403) to tailored, user-friendly Streamlit errors (e.g., Daily Limit Hit, Invalid API Key, Blocked Key).

---

## 4. Specific Internal Functions

### `pdf_generator.py`
- **`generate_pdf(cover_letter_text, company_name)`**
  - Uses `reportlab.platypus.SimpleDocTemplate` to create an 8.5" x 11" letter with 0.75-inch margins (CBS standard).
  - Automatically parses the generated text, segregating the Header block, the Body, and the Closing block ("Best, Nicolas De Castro") to assign appropriate spacing and alignment (`TA_JUSTIFY` for body, `TA_LEFT` for headers).
  - Uses `BytesIO` to keep file generation entirely within RAM, bypassing disk writes.
  - **Sanity check feature:** Pipes the resulting bytes into `pypdf.PdfReader` to count the pages. If the output exceeds 1 page (violating standard cover letter rules), it returns a warning string to alert the Streamlit UI to display a warning to the user.

### `context_data.py` (Data Models)
- **`CV_TEXT`**: The raw text extraction of the user's full chronological resume.
- **`STORY_BANK` & `STORY_INDEX`**: Modularized breakdown of specific impact stories (e.g., the Treinta Series A story, the Mastercard churn model story). This ensures the LLM retrieves high-fidelity details rather than hallucinating generic PM actions.
- **`POSITIONING_GUIDE`**: A hardcoded matrix helping the Strategy AI decide which "flavor" of the candidate to pitch (e.g., Growth PM vs. AI Strategist).
- **`GOLDEN_EXAMPLES`**: Pre-written, highly calibrated examples of perfect past cover letters to ground the LLM's tonal output (few-shot prompting).

---

## 5. Areas for Potential Architectural Improvement

1. **Token Efficiency:** The full `STORY_BANK` and `CV_TEXT` are injected into several prompt stages. Transitioning to a lightweight Retrieval-Augmented Generation (RAG) implementation or chunking could lower API latency and token usage.
2. **State Management Extensibility:** `st.session_state` keys are somewhat hardcoded. Refactoring state into a Pydantic model (`AppState`) would improve type safety.
3. **Structured Outputs for Matrix:** The `MATCHING_PROMPT` currently returns unstructured text. Enforcing a JSON schema for the matching matrix would allow developers to systematically render the strategy (e.g., in a Streamlit table) rather than a raw text block.
4. **Critique Logic Stability:** The Critique prompt currently asks the model to emit Markdown JSON. `gemini-2.5-pro` supports `response_mime_type="application/json"` natively via Configuration which would remove the need to parse raw string JSON containing markdown backticks.
