import streamlit as st
import json
from datetime import datetime
from google import genai
try:
    from google.genai import types
    HAS_GOOGLE_SEARCH = hasattr(types, "GoogleSearch")
except ImportError:
    HAS_GOOGLE_SEARCH = False

from prompts import SYSTEM_PROMPT, MATCHING_PROMPT, DRAFTING_PROMPT, CRITIQUE_PROMPT, REVISION_PROMPT, QA_PROMPT, COMPANY_RESEARCH_PROMPT
from context_data import CV_TEXT, STORY_BANK, STORY_INDEX, GOLDEN_EXAMPLES, POSITIONING_GUIDE
from pdf_generator import generate_pdf
from evaluator import run_deterministic_critique, compute_quality_score, burstiness_score, keyword_coverage
from logger import log_session

# Configure page
st.set_page_config(page_title="Nicolas' Cover Letter Generator", layout="centered")

# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = 1
if "matching_matrix" not in st.session_state:
    st.session_state.matching_matrix = ""
if "draft_text" not in st.session_state:
    st.session_state.draft_text = ""
if "critique_results" not in st.session_state:
    st.session_state.critique_results = []
if "critique_failures_text" not in st.session_state:
    st.session_state.critique_failures_text = ""
if "revision_count" not in st.session_state:
    st.session_state.revision_count = 0
if "quick_mode" not in st.session_state:
    st.session_state.quick_mode = False
if "qa_answers" not in st.session_state:
    st.session_state.qa_answers = ""
if "token_log" not in st.session_state:
    st.session_state.token_log = []
if "deterministic_critique" not in st.session_state:
    st.session_state.deterministic_critique = []
if "company_research" not in st.session_state:
    st.session_state.company_research = ""

@st.cache_resource
def get_gemini_client():
    try:
        api_key = st.secrets["gemini"]["api_key"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client. Check sequence in .streamlit/secrets.toml. {e}")
        return None

def call_gemini(client, user_prompt, model_name="gemini-2.5-flash", step_name="unknown"):
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[user_prompt],
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.7,
            }
        )
        # Track token usage
        try:
            usage = response.usage_metadata
            st.session_state.token_log.append({
                "step": step_name,
                "model": model_name,
                "input_tokens": getattr(usage, "prompt_token_count", 0),
                "output_tokens": getattr(usage, "candidates_token_count", 0),
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass  # Don't break flow if usage metadata unavailable
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            if "PerDay" in error_msg or "Daily" in error_msg:
                st.error("🛑 **Daily Limit Reached!** You've exhausted Google's free allowance of 50 requests per day for Gemini 1.5 Pro. You must wait until tomorrow, or use a faster Flash model.")
            else:
                st.error("⏳ **Rate Limit Hit!** You've requested too much too fast. Please wait 10 seconds and try again!")
        elif "400" in error_msg or "API_KEY_INVALID" in error_msg or "INVALID_ARGUMENT" in error_msg:
            st.error("🔑 **Invalid API Key!** Your Gemini API key is expired, invalid, or missing. Please check your Google AI Studio account and update your connection.")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            st.error("🛡️ **API Key Blocked!** Google detected this key as leaked and disabled it. Please generate a brand new key on Google AI Studio.")
        else:
            st.error(f"⚠️ **Unexpected AI Error:** {error_msg}")
        return None

def research_company(client, company_name):
    """Use Gemini with Google Search grounding to research a company."""
    try:
        prompt = COMPANY_RESEARCH_PROMPT.format(company_name=company_name)
        config = {"temperature": 0.3}
        if HAS_GOOGLE_SEARCH:
            config["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=config,
        )
        # Track token usage
        try:
            usage = response.usage_metadata
            st.session_state.token_log.append({
                "step": "company_research",
                "model": "gemini-2.5-flash",
                "input_tokens": getattr(usage, "prompt_token_count", 0),
                "output_tokens": getattr(usage, "candidates_token_count", 0),
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass
        return response.text
    except Exception as e:
        st.warning(f"Company research unavailable: {e}")
        return ""


def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title("🚀 Cover Letter Generator")
st.markdown("Targeting: Product Management, AI Strategist, Strategy & Ops")

client = get_gemini_client()

# ==========================================
# SIDEBAR: Quality Dashboard & Token Tracking
# ==========================================
with st.sidebar:
    st.header("Quality Dashboard")

    if st.session_state.draft_text:
        draft = st.session_state.draft_text
        jd = st.session_state.get("jd_text", "")

        # Quality Score
        q_score = compute_quality_score(draft, jd if jd else None)
        st.metric("Quality Score", f"{q_score}/100")

        # Burstiness
        burst = burstiness_score(draft)
        burst_label = "Low (AI-like)" if burst < 5 else "Medium" if burst < 8 else "Good (Human-like)"
        st.metric("Burstiness", f"{burst}", delta=burst_label)

        # Keyword Coverage
        if jd:
            cov, matched, missed = keyword_coverage(draft, jd)
            st.metric("JD Keyword Coverage", f"{int(cov * 100)}%")
            with st.expander("Keyword Details"):
                if matched:
                    st.caption(f"Matched: {', '.join(matched[:10])}")
                if missed:
                    st.caption(f"Missing: {', '.join(missed[:10])}")

        # Word count
        wc = len(draft.split())
        st.metric("Word Count", wc, delta=f"{'OK' if 300 <= wc <= 380 else 'Out of range'}")
    else:
        st.caption("Generate a draft to see quality metrics.")

    st.markdown("---")
    st.header("Token Usage")
    if st.session_state.token_log:
        total_input = sum(t.get("input_tokens", 0) for t in st.session_state.token_log)
        total_output = sum(t.get("output_tokens", 0) for t in st.session_state.token_log)
        st.metric("Total Input Tokens", f"{total_input:,}")
        st.metric("Total Output Tokens", f"{total_output:,}")
        st.metric("API Calls", len(st.session_state.token_log))

        with st.expander("Per-Step Breakdown"):
            for entry in st.session_state.token_log:
                st.caption(f"**{entry['step']}** ({entry['model']}): {entry.get('input_tokens', 0):,} in / {entry.get('output_tokens', 0):,} out")
    else:
        st.caption("No API calls yet.")

# ==========================================
# STEP 1: INPUT
# ==========================================
if st.session_state.step == 1:
    st.header("Step 1: Input Job Details")
    
    with st.container():
        st.session_state.company_name = st.text_input("Company Name", placeholder="e.g., FanDuel, Google, Stripe...")
        st.session_state.jd_text = st.text_area("Job Description", height=200, max_chars=15000)
        st.session_state.app_questions = st.text_area("Application Questions (For 'Answer App Questions' flow only)", height=150, max_chars=3000)
        st.session_state.user_context = st.text_area("Additional Context (Optional)", placeholder="Recent news, why you care, personal connection...", max_chars=2000)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            analyze_clicked = st.button("Analyze & Match (Standard)", use_container_width=True)
        with col2:
            quick_clicked = st.button("🏎️ Quick Generation (Direct to PDF)", use_container_width=True)
        with col3:
            qa_clicked = st.button("📝 Answer App Questions", use_container_width=True)
            
        if analyze_clicked or quick_clicked or qa_clicked:
            if not st.session_state.jd_text:
                st.warning("Please provide the Job Description.")
            elif qa_clicked and not st.session_state.get("app_questions"):
                st.warning("Please provide the Application Questions.")
            elif client:
                if qa_clicked:
                    st.session_state.quick_mode = False
                    with st.spinner("📝 Generating strategic answers..."):
                        qa_prompt = QA_PROMPT.format(
                            story_bank=STORY_BANK,
                            cv_text=CV_TEXT,
                            jd_text=st.session_state.jd_text,
                            questions=st.session_state.app_questions,
                            user_context=st.session_state.user_context
                        )
                        qa_result = call_gemini(client, qa_prompt, model_name="gemini-2.5-pro", step_name="qa")
                        if qa_result:
                            st.session_state.qa_answers = qa_result
                            st.session_state.step = 5
                            st.rerun()
                elif quick_clicked:
                    st.session_state.quick_mode = True
                    with st.spinner("⚡ Generating perfect cover letter directly..."):
                        # 0. Company research (if company name provided)
                        if st.session_state.get("company_name") and client:
                            research = research_company(client, st.session_state.company_name)
                            st.session_state.company_research = research or ""

                        enriched_context = st.session_state.user_context or ""
                        if st.session_state.company_research:
                            enriched_context += f"\n\nCOMPANY RESEARCH (use for hook):\n{st.session_state.company_research}"

                        # 1. Matching
                        match_prompt = MATCHING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            story_index=STORY_INDEX,
                            cv_text=CV_TEXT,
                            user_context=enriched_context,
                            positioning_guide=POSITIONING_GUIDE
                        )
                        match_result = call_gemini(client, match_prompt, step_name="matching_quick")
                        st.session_state.matching_matrix = match_result

                        # 2. Drafting
                        draft_prompt = DRAFTING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            matching_matrix=st.session_state.matching_matrix,
                            selected_stories=STORY_BANK,
                            cv_text=CV_TEXT,
                            user_context=enriched_context,
                            golden_examples=GOLDEN_EXAMPLES
                        )
                        draft_result = call_gemini(client, draft_prompt, step_name="drafting_quick")
                        if draft_result:
                            st.session_state.draft_text = draft_result
                            # Run deterministic critique on quick mode too
                            det_results, _ = run_deterministic_critique(draft_result)
                            st.session_state.deterministic_critique = det_results
                            st.session_state.step = 4
                            st.rerun()
                else:
                    st.session_state.quick_mode = False
                    # Company research (if company name provided)
                    if st.session_state.get("company_name") and client:
                        with st.spinner("Researching company..."):
                            research = research_company(client, st.session_state.company_name)
                            st.session_state.company_research = research or ""

                    with st.spinner("Matching stories to JD requirements..."):
                        # Append company research to user context
                        enriched_context = st.session_state.user_context or ""
                        if st.session_state.company_research:
                            enriched_context += f"\n\nCOMPANY RESEARCH (use for hook):\n{st.session_state.company_research}"

                        prompt = MATCHING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            story_index=STORY_INDEX,
                            cv_text=CV_TEXT,
                            user_context=enriched_context,
                            positioning_guide=POSITIONING_GUIDE
                        )
                        result = call_gemini(client, prompt, model_name="gemini-2.5-pro", step_name="matching")
                        if result:
                            st.session_state.matching_matrix = result
                            st.session_state.step = 2
                            st.rerun()

# ==========================================
# STEP 2: MATCHING MATRIX
# ==========================================
elif st.session_state.step == 2:
    st.header("Step 2: Strategy Review")
    
    with st.expander("View extracted JD matching & red flags", expanded=True):
        st.markdown(st.session_state.matching_matrix)
        
    st.info("Edit the strategy below if necessary before drafting.")
    st.session_state.approved_strategy = st.text_area("Strategy / Matching Matrix", value=st.session_state.matching_matrix, height=300)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Draft Cover Letter", use_container_width=True, type="primary"):
            if client:
                with st.spinner("Drafting cover letter..."):
                    enriched_context = st.session_state.user_context or ""
                    if st.session_state.company_research:
                        enriched_context += f"\n\nCOMPANY RESEARCH (use for hook):\n{st.session_state.company_research}"

                    prompt = DRAFTING_PROMPT.format(
                        jd_text=st.session_state.jd_text,
                        matching_matrix=st.session_state.approved_strategy,
                        selected_stories=STORY_BANK,
                        cv_text=CV_TEXT,
                        user_context=enriched_context,
                        golden_examples=GOLDEN_EXAMPLES
                    )
                    draft_result = call_gemini(client, prompt, model_name="gemini-2.5-pro", step_name="drafting")

                    if draft_result:
                        st.session_state.draft_text = draft_result

                        # 1. Run deterministic critique (instant, no API call)
                        det_results, _ = run_deterministic_critique(draft_result)
                        st.session_state.deterministic_critique = det_results

                        # 2. Run LLM critique for subjective checks
                        with st.spinner("Running quality critique..."):
                            critique_prompt = CRITIQUE_PROMPT.format(draft_text=draft_result)
                            critique_res = call_gemini(client, critique_prompt, model_name="gemini-2.5-flash", step_name="critique")

                            if critique_res:
                                try:
                                    clean_json = critique_res.replace("```json", "").replace("```", "").strip()
                                    critique_dict = json.loads(clean_json)
                                    st.session_state.critique_results = critique_dict.get("critique_results", [])
                                except Exception:
                                    st.warning("Could not parse critique JSON.")

                        # Collect ALL failures (deterministic + LLM)
                        all_failures = []
                        for f in det_results:
                            if f["status"] == "FAIL":
                                all_failures.append(f["rule"] + ": " + f["details"])
                        for f in st.session_state.critique_results:
                            if str(f.get("status")).upper() == "FAIL":
                                all_failures.append(f["rule"] + ": " + f["details"])
                        st.session_state.critique_failures_text = "\n".join(all_failures)

                        st.session_state.step = 3
                        st.rerun()

# ==========================================
# STEP 3: DRAFT REVIEW
# ==========================================
elif st.session_state.step == 3:
    st.header("Step 3: Draft Review")
    st.caption(f"Revision {st.session_state.revision_count} of 5")
    
    word_count = len(st.session_state.draft_text.split())
    char_count = len(st.session_state.draft_text)
    st.info(f"**Length Check:** {word_count} words | {char_count} characters. *(Aim for < 380 words / 2400 chars to fit perfectly on 1 page with CBS PDF specs)*")
    
    st.text_area("Current Draft", value=st.session_state.draft_text, height=400, disabled=False, key="editable_draft")
    # Updating session state manually just in case user edits the text area directly:
    if st.session_state.editable_draft != st.session_state.draft_text:
         st.session_state.draft_text = st.session_state.editable_draft
    
    # Show deterministic critique results
    if st.session_state.deterministic_critique:
        with st.expander("Mechanical Checks (Deterministic)", expanded=any(r["status"] == "FAIL" for r in st.session_state.deterministic_critique)):
            for res in st.session_state.deterministic_critique:
                icon = "✅" if res["status"] == "PASS" else "❌"
                st.markdown(f"**{icon} {res['rule']}**: {res['details']}")

    # Show LLM critique results
    if st.session_state.critique_results:
        with st.expander("Quality Checks (LLM)", expanded=any(str(r.get('status')).upper() == "FAIL" for r in st.session_state.critique_results)):
            for res in st.session_state.critique_results:
                icon = "✅" if str(res.get('status')).upper() == "PASS" else "❌"
                st.markdown(f"**{icon} {res.get('rule')}**: {res.get('details')}")
                
    st.markdown("---")
    st.session_state.user_feedback = st.text_area("Your feedback (e.g. 'Make opening more specific', 'Too long')", placeholder="Approve or list changes...")
    
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Revise", use_container_width=True):
            if st.session_state.revision_count >= 5:
                st.error("Max revisions reached. Please approve.")
            elif client:
                with st.spinner("Revising draft..."):
                    rev_prompt = REVISION_PROMPT.format(
                        draft_text=st.session_state.draft_text,
                        user_feedback=st.session_state.user_feedback,
                        critique_failures=st.session_state.critique_failures_text
                    )
                    revised = call_gemini(client, rev_prompt, model_name="gemini-2.5-pro", step_name="revision")
                    if revised:
                        st.session_state.draft_text = revised
                        st.session_state.editable_draft = revised

                        st.session_state.revision_count += 1

                        # 1. Deterministic critique (instant)
                        det_results, _ = run_deterministic_critique(revised)
                        st.session_state.deterministic_critique = det_results

                        # 2. LLM critique for subjective checks
                        with st.spinner("Running quality critique..."):
                            critique_prompt = CRITIQUE_PROMPT.format(draft_text=revised)
                            critique_res = call_gemini(client, critique_prompt, model_name="gemini-2.5-flash", step_name="critique")
                            try:
                                clean_json = critique_res.replace("```json", "").replace("```", "").strip()
                                critique_dict = json.loads(clean_json)
                                st.session_state.critique_results = critique_dict.get("critique_results", [])
                            except Exception:
                                pass

                        # Collect ALL failures
                        all_failures = []
                        for f in det_results:
                            if f["status"] == "FAIL":
                                all_failures.append(f["rule"] + ": " + f["details"])
                        for f in st.session_state.critique_results:
                            if str(f.get("status")).upper() == "FAIL":
                                all_failures.append(f["rule"] + ": " + f["details"])
                        st.session_state.critique_failures_text = "\n".join(all_failures)

                        st.rerun()
    with b2:
        if st.button("Approve & Generate PDF", use_container_width=True, type="primary"):
            st.session_state.step = 4
            st.rerun()

# ==========================================
# STEP 4: PDF DOWNLOAD
# ==========================================
elif st.session_state.step == 4:
    st.header("Step 4: PDF Ready")
    st.success("Cover letter finalized!")

    pdf_bytes, warning = generate_pdf(st.session_state.draft_text, "Unknown Company")

    if warning:
        st.warning(warning)

    # Show deterministic critique warnings (especially for quick mode)
    if st.session_state.deterministic_critique:
        det_failures = [r for r in st.session_state.deterministic_critique if r["status"] == "FAIL"]
        if det_failures:
            with st.expander(f"⚠️ {len(det_failures)} Mechanical Check(s) Failed", expanded=True):
                for res in det_failures:
                    st.markdown(f"**❌ {res['rule']}**: {res['details']}")

    st.text_area("Final Text", value=st.session_state.draft_text, height=300, disabled=True)

    filename = "Nicolas_De_Castro_CoverLetter.pdf"

    dl_clicked = st.download_button(
        label="📥 Download PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

    # Log session on download
    if dl_clicked:
        jd = st.session_state.get("jd_text", "")
        cov_pct = keyword_coverage(st.session_state.draft_text, jd)[0] if jd else 0.0
        log_session(
            jd_text=jd,
            workflow="quick" if st.session_state.get("quick_mode") else "standard",
            matching_matrix=st.session_state.get("matching_matrix", ""),
            draft_text=st.session_state.draft_text,
            critique_results=st.session_state.get("critique_results", []),
            deterministic_critique=st.session_state.get("deterministic_critique", []),
            revision_count=st.session_state.get("revision_count", 0),
            quality_score=compute_quality_score(st.session_state.draft_text, jd if jd else None),
            burstiness=burstiness_score(st.session_state.draft_text),
            keyword_coverage_pct=cov_pct,
            token_log=st.session_state.get("token_log", []),
        )

    if st.button("Start New Cover Letter", use_container_width=True):
        reset_app()

# ==========================================
# STEP 5: QA RESULTS
# ==========================================
elif st.session_state.step == 5:
    st.header("Step 5: Application Answers")
    st.success("Answers generated successfully!")

    st.text_area("Your Answers (Copy/Paste ready)", value=st.session_state.qa_answers, height=500)

    if st.button("Start New Session", use_container_width=True, type="primary"):
        # Log QA session
        log_session(
            jd_text=st.session_state.get("jd_text", ""),
            workflow="qa",
            qa_answers=st.session_state.qa_answers,
            token_log=st.session_state.get("token_log", []),
        )
        reset_app()
# Trigger reload 3
