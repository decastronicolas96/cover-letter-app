import streamlit as st
import json
from google import genai

from prompts import SYSTEM_PROMPT, MATCHING_PROMPT, DRAFTING_PROMPT, CRITIQUE_PROMPT, REVISION_PROMPT, QA_PROMPT
from context_data import CV_TEXT, STORY_BANK, STORY_INDEX, GOLDEN_EXAMPLES, POSITIONING_GUIDE
from pdf_generator import generate_pdf

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

@st.cache_resource
def get_gemini_client():
    try:
        api_key = st.secrets["gemini"]["api_key"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client. Check sequence in .streamlit/secrets.toml. {e}")
        return None

def call_gemini(client, user_prompt, model_name="gemini-2.0-flash"):
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[user_prompt],
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.7,
            }
        )
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            st.error("⏳ **Rate Limit Hit!** You've requested too much too fast (Google Free Tier allows ~15 requests per minute). Please wait 10 seconds and try again!")
        elif "400" in error_msg or "API_KEY_INVALID" in error_msg or "INVALID_ARGUMENT" in error_msg:
            st.error("🔑 **Invalid API Key!** Your Gemini API key is expired, invalid, or missing. Please check your Google AI Studio account and update your connection.")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            st.error("🛡️ **API Key Blocked!** Google detected this key as leaked and disabled it. Please generate a brand new key on Google AI Studio.")
        else:
            st.error(f"⚠️ **Unexpected AI Error:** {error_msg}")
        return None

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title("🚀 Cover Letter Generator")
st.markdown("Targeting: Product Management, AI Strategist, Strategy & Ops")

client = get_gemini_client()

# ==========================================
# STEP 1: INPUT
# ==========================================
if st.session_state.step == 1:
    st.header("Step 1: Input Job Details")
    
    with st.container():
        st.session_state.jd_text = st.text_area("Job Description", height=200, max_chars=8000)
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
                            questions=st.session_state.app_questions
                        )
                        qa_result = call_gemini(client, qa_prompt, model_name="gemini-1.5-pro")
                        if qa_result:
                            st.session_state.qa_answers = qa_result
                            st.session_state.step = 5
                            st.rerun()
                elif quick_clicked:
                    st.session_state.quick_mode = True
                    with st.spinner("⚡ Generating perfect cover letter directly..."):
                        # 1. Matching
                        match_prompt = MATCHING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            story_index=STORY_INDEX,
                            positioning_guide=POSITIONING_GUIDE
                        )
                        match_result = call_gemini(client, match_prompt)
                        st.session_state.matching_matrix = match_result
                        
                        # 2. Drafting
                        draft_prompt = DRAFTING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            matching_matrix=st.session_state.matching_matrix,
                            selected_stories=STORY_BANK,
                            cv_text=CV_TEXT,
                            user_context=st.session_state.user_context,
                            golden_examples=GOLDEN_EXAMPLES
                        )
                        draft_result = call_gemini(client, draft_prompt)
                        if draft_result:
                            st.session_state.draft_text = draft_result
                            st.session_state.step = 4
                            st.rerun()
                else:
                    st.session_state.quick_mode = False
                    with st.spinner("Matching stories to JD requirements..."):
                        prompt = MATCHING_PROMPT.format(
                            jd_text=st.session_state.jd_text,
                            story_index=STORY_INDEX,
                            positioning_guide=POSITIONING_GUIDE
                        )
                        result = call_gemini(client, prompt, model_name="gemini-1.5-pro")
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
                    # For simplicity and token management, we send the entire STORY_BANK. 
                    # Gemini 2.5 Flash easily manages this within a small window.
                    prompt = DRAFTING_PROMPT.format(
                        jd_text=st.session_state.jd_text,
                        matching_matrix=st.session_state.approved_strategy,
                        selected_stories=STORY_BANK,
                        cv_text=CV_TEXT,
                        user_context=st.session_state.user_context,
                        golden_examples=GOLDEN_EXAMPLES
                    )
                    draft_result = call_gemini(client, prompt, model_name="gemini-1.5-pro")
                    
                    if draft_result:
                        st.session_state.draft_text = draft_result
                        
                        # Trigger critique immediately
                        with st.spinner("Running self-critique..."):
                            critique_prompt = CRITIQUE_PROMPT.format(draft_text=draft_result)
                            critique_res = call_gemini(client, critique_prompt, model_name="gemini-1.5-pro")
                            
                            # Parse JSON
                            if critique_res:
                                try:
                                    clean_json = critique_res.replace("```json", "").replace("```", "").strip()
                                    critique_dict = json.loads(clean_json)
                                    st.session_state.critique_results = critique_dict.get("critique_results", [])
                                    
                                    # Collect failures
                                    failures = [f['rule'] + ": " + f['details'] for f in st.session_state.critique_results if str(f.get('status')).upper() == "FAIL"]
                                    st.session_state.critique_failures_text = "\n".join(failures)
                                        
                                except Exception as e:
                                    st.warning("Could not parse critique JSON.")
                            
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
    
    if st.session_state.critique_results:
        with st.expander("Critique Checklist Results", expanded=bool(st.session_state.critique_failures_text)):
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
                    revised = call_gemini(client, rev_prompt, model_name="gemini-1.5-pro")
                    if revised:
                        st.session_state.draft_text = revised
                        st.session_state.revision_count += 1
                        
                        with st.spinner("Running self-critique..."):
                            critique_prompt = CRITIQUE_PROMPT.format(draft_text=revised)
                            critique_res = call_gemini(client, critique_prompt, model_name="gemini-1.5-pro")
                            try:
                                clean_json = critique_res.replace("```json", "").replace("```", "").strip()
                                critique_dict = json.loads(clean_json)
                                st.session_state.critique_results = critique_dict.get("critique_results", [])
                                failures = [f['rule'] + ": " + f['details'] for f in st.session_state.critique_results if str(f.get('status')).upper() == "FAIL"]
                                st.session_state.critique_failures_text = "\n".join(failures)
                            except:
                                pass
                        
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
        
    st.text_area("Final Text", value=st.session_state.draft_text, height=300, disabled=True)
    
    filename = "Nicolas_De_Castro_CoverLetter.pdf"
    
    st.download_button(
        label="📥 Download PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        type="primary",
        use_container_width=True
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
        reset_app()
# Trigger reload 2
