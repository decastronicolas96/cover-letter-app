"""
logger.py

Session logging for offline evaluation and longitudinal quality tracking.
Logs each session's inputs, outputs, and metrics to a local JSON Lines file.
"""

import json
import os
import uuid
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "session_logs")
LOG_FILE = os.path.join(LOG_DIR, "sessions.jsonl")


def log_session(
    jd_text,
    workflow,
    matching_matrix="",
    draft_text="",
    critique_results=None,
    deterministic_critique=None,
    revision_count=0,
    quality_score=0,
    burstiness=0.0,
    keyword_coverage_pct=0.0,
    token_log=None,
    qa_answers="",
):
    """Append a session record to the JSONL log file."""
    os.makedirs(LOG_DIR, exist_ok=True)

    total_tokens = 0
    total_api_calls = 0
    if token_log:
        total_tokens = sum(
            t.get("input_tokens", 0) + t.get("output_tokens", 0) for t in token_log
        )
        total_api_calls = len(token_log)

    record = {
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "workflow": workflow,
        "jd_text_length": len(jd_text),
        "matching_matrix_length": len(matching_matrix),
        "draft_text": draft_text,
        "critique_results": critique_results or [],
        "deterministic_critique": deterministic_critique or [],
        "revision_count": revision_count,
        "quality_score": quality_score,
        "burstiness_score": burstiness,
        "keyword_coverage": keyword_coverage_pct,
        "total_tokens": total_tokens,
        "total_api_calls": total_api_calls,
        "token_log": token_log or [],
        "qa_answers_length": len(qa_answers),
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record["session_id"]
