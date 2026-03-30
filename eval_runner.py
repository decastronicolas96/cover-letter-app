"""
eval_runner.py

LLM-as-Judge evaluation for cover letters.
Scores letters on 5 dimensions using an external model to avoid self-evaluation bias.
Run offline against batches of generated letters to track quality over time.

Usage:
    python eval_runner.py <sessions_jsonl_path> [--model gemini-2.5-flash]
"""

import json
import sys
import os

EVAL_PROMPT = """
You are an expert recruiter and hiring manager evaluating a cover letter for a Product Management role in the tech industry.

COVER LETTER:
{letter_text}

Score this letter on each of the following 5 dimensions from 1-10. Be rigorous and specific in your reasoning.

1. **Hook Specificity** (1-10): How company-specific and attention-grabbing is the opening paragraph? Does it reference something concrete about the company (a product, market move, recent news), or is it generic praise that could apply to any company?

2. **Narrative Authenticity** (1-10): Does this read like a real human wrote it, or does it have AI tells? Look for: uniform sentence length, corporate buzzwords, hedging language, overly polished transitions, lack of personality.

3. **JD Alignment** (1-10): How well does the letter address the job description's core requirements? Are the right skills and experiences highlighted? Are relevant keywords naturally embedded?

4. **Metric Density & Impact** (1-10): How specific and impactful are the quantitative claims? Are metrics tied to business outcomes? Do they demonstrate real ownership and results?

5. **Differentiation** (1-10): Would this letter stand out from 100 other PM applicants? Does it reveal something unique about the candidate that a resume alone wouldn't convey?

OUTPUT FORMAT (JSON only, no other text):
```json
{{
  "hook_specificity": {{"score": 7, "reasoning": "..."}},
  "narrative_authenticity": {{"score": 6, "reasoning": "..."}},
  "jd_alignment": {{"score": 8, "reasoning": "..."}},
  "metric_density": {{"score": 7, "reasoning": "..."}},
  "differentiation": {{"score": 5, "reasoning": "..."}},
  "overall_score": 6.6,
  "top_improvement": "The opening paragraph needs a concrete company-specific observation instead of generic praise."
}}
```
"""


def evaluate_letter(letter_text, client, model_name="gemini-2.5-flash"):
    """Evaluate a single letter using LLM-as-Judge."""
    prompt = EVAL_PROMPT.format(letter_text=letter_text)
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt],
        config={"temperature": 0.3},
    )
    text = response.text
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


def run_batch_eval(sessions_path, api_key, model_name="gemini-2.5-flash"):
    """Evaluate all sessions in a JSONL file."""
    from google import genai
    client = genai.Client(api_key=api_key)

    results = []
    with open(sessions_path, "r", encoding="utf-8") as f:
        for line in f:
            session = json.loads(line.strip())
            draft = session.get("draft_text", "")
            if not draft:
                continue

            print(f"Evaluating session {session['session_id']}...")
            try:
                eval_result = evaluate_letter(draft, client, model_name)
                eval_result["session_id"] = session["session_id"]
                eval_result["timestamp"] = session["timestamp"]
                eval_result["deterministic_quality_score"] = session.get("quality_score", 0)
                eval_result["burstiness"] = session.get("burstiness_score", 0)
                results.append(eval_result)
                print(f"  Overall: {eval_result.get('overall_score', 'N/A')}")
            except Exception as e:
                print(f"  Error: {e}")

    # Save results
    output_path = sessions_path.replace(".jsonl", "_eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval_runner.py <sessions.jsonl> [--model gemini-2.5-flash]")
        sys.exit(1)

    sessions_file = sys.argv[1]
    model = "gemini-2.5-flash"
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        model = sys.argv[idx + 1]

    # Get API key from environment or secrets
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            with open(secrets_path) as f:
                for line in f:
                    if "api_key" in line and "=" in line:
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        print("Error: Set GEMINI_API_KEY env var or ensure .streamlit/secrets.toml exists")
        sys.exit(1)

    run_batch_eval(sessions_file, api_key, model)
