# 🚀 AI-Powered Cover Letter & Application Generator

An intelligent, multi-flow Streamlit application built with Python and the Google Gemini 2.5 API. This tool is designed specifically to automate and optimize the MBA recruiting process for Product Management, AI Strategist, and Strategy & Operations roles.

## ✨ Features

This application features three distinct, context-aware AI generation flows:

1. **Standard Cover Letter Flow:** 
   Fully analyzes a target Job Description against a custom story bank/CV, devises a tailored strategy, drafts a precise 4-paragraph cover letter, rigorously self-critiques against absolute writing rules (no em-dashes, exact word counts), allows for human-in-the-loop revision prompts, and finally exports a perfectly formatted one-page PDF.
2. **⚡ Quick Generation Flow:** 
   Bypasses the human-in-the-loop strategy check and jumps straight to generating the final, polished PDF, optimizing for extreme speed.
3. **📝 Application Questions Flow:** 
   Accepts both a Job Description and a list of open-ended application questions. The agent contextualizes the role's tone and requirements, and writes succinct, metrics-driven operator answers perfectly tailored to the open-ended responses.

## 🛠️ Tech Stack & Architecture

- **Frontend:** Streamlit (Mobile-responsive UI, Session State management)
- **AI/LLM:** Google Gemini 2.5 Flash API (with rigorous system prompts and multi-turn drafting/critique cycles)
- **PDF Generation:** ReportLab (for highly precise, single-page PDF outputs)
- **Deployment:** Streamlit Community Cloud (connected via GitHub CI/CD)

## 🔒 Security Note
This project utilizes a `.streamlit/secrets.toml` file to manage the Gemini API key. This file is explicitly excluded via `.gitignore` to prevent credential leakage on GitHub.

## 🏃‍♂️ How to Run Locally

1. Clone this repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Add your `secrets.toml` file inside the `.streamlit` folder with your Gemini API key:
   ```toml
   [gemini]
   api_key = "YOUR_API_KEY_HERE"
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```
