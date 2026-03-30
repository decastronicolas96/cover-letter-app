"""
evaluator.py

Deterministic quality checks and scoring for cover letters.
Handles mechanical rules that don't need LLM evaluation,
plus quality metrics (burstiness, keyword coverage, quality score).
"""

import re
import statistics
from collections import Counter

# ---------------------------------------------------------------
# Banned words & phrases (expanded from AI best practices research)
# ---------------------------------------------------------------
BANNED_WORDS = [
    # Enthusiasm clichés
    "energized", "energize", "excited", "thrilled", "passionate",
    "deeply passionate",
    # Corporate buzzwords
    "synergy", "utilize", "spearhead", "streamline", "foster",
    "hone", "elevate", "pivotal",
    # AI-overused words
    "delve", "robust", "seamless", "cutting-edge", "dynamic",
    "innovative", "tapestry", "realm", "testament", "multifaceted",
    "underscores",
]

# Context-sensitive: only ban metaphorical uses (matched as standalone words)
BANNED_CONTEXTUAL = ["landscape", "navigate"]

BANNED_PHRASES = [
    "leverage",  # as verb - checked in context
    "aligns perfectly",
    "positions me to contribute",
    "strengthens my fit",
    "i am confident i can",
    "i am keen to",
    "i am drawn to",
    "i am eager to",
    "instilled a disciplined approach",
    "delivering tangible value",
    "uniquely positioned",
    "my background in",  # when followed by "positions me"
    "furthermore,",
    "moreover,",
    "in conclusion,",
    "it is worth noting",
    "notably,",
]

GENERIC_OPENINGS = [
    "i am writing to apply",
    "i am writing to express",
    "dear hiring manager, i am interested",
    "i am applying for",
    "i wish to apply",
]

WORK_AUTH_KEYWORDS = [
    "work authorization", "visa status", "sponsorship",
    "right to work", "work permit", "immigration",
    "h-1b", "stem opt", "f-1 visa",
]
# "opt" removed - too many false positives (e.g., "optimizing", "optional")


def _split_sentences(text):
    """Split text into sentences, handling common abbreviations."""
    # Remove header (name, email, phone, Dear...) for body analysis
    lines = text.strip().split("\n")
    body_lines = []
    in_body = False
    for line in lines:
        if line.strip().startswith("Dear "):
            in_body = True
            continue
        if in_body and line.strip() and line.strip() not in ("Best,", "Nicolas De Castro"):
            body_lines.append(line.strip())
    body = " ".join(body_lines)
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', body)
    return [s.strip() for s in sentences if s.strip()]


def _get_body_paragraphs(text):
    """Extract body paragraphs (after Dear..., before Best,)."""
    lines = text.strip().split("\n")
    body_lines = []
    in_body = False
    for line in lines:
        if line.strip().startswith("Dear "):
            in_body = True
            continue
        if in_body and line.strip() in ("Best,", "Nicolas De Castro"):
            break
        if in_body:
            body_lines.append(line)

    # Group into paragraphs by blank lines
    paragraphs = []
    current = []
    for line in body_lines:
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


# ---------------------------------------------------------------
# Deterministic Critique Checks
# ---------------------------------------------------------------

def check_em_dashes(text):
    """Rule: No em dashes (—) allowed."""
    found = "—" in text
    return {
        "rule": "No em dashes",
        "status": "FAIL" if found else "PASS",
        "details": "Found em dash (—) in text." if found else "No em dashes found."
    }


def check_banned_words(text):
    """Rule: No banned words or phrases."""
    text_lower = text.lower()
    found = []

    for word in BANNED_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            found.append(word)

    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            found.append(phrase)

    # Check contextual bans (metaphorical use of landscape/navigate)
    for word in BANNED_CONTEXTUAL:
        # Only flag if not preceded by technical context
        pattern = r'\b' + re.escape(word) + r'\b'
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            start = max(0, match.start() - 30)
            context = text_lower[start:match.end() + 20]
            # Skip if clearly literal (e.g., "navigate the AWS console")
            if not any(tech in context for tech in ["aws", "api", "ui", "database", "code", "repo"]):
                found.append(f"{word} (metaphorical)")

    return {
        "rule": "No banned words/phrases",
        "status": "FAIL" if found else "PASS",
        "details": f"Found: {', '.join(found)}" if found else "No banned words or phrases found."
    }


def check_formatting(text):
    """Rule: No bold, headers, or bullet points in body."""
    issues = []
    if "**" in text:
        issues.append("bold text (**)")
    if re.search(r'^#{1,6}\s', text, re.MULTILINE):
        issues.append("headers (#)")
    if re.search(r'^\s*[-•*]\s', text, re.MULTILINE):
        issues.append("bullet points")

    return {
        "rule": "No formatting",
        "status": "FAIL" if issues else "PASS",
        "details": f"Found: {', '.join(issues)}" if issues else "No formatting issues."
    }


def check_generic_opening(text):
    """Rule: No generic openings."""
    text_lower = text.lower()
    for opening in GENERIC_OPENINGS:
        if opening in text_lower:
            return {
                "rule": "No generic opening",
                "status": "FAIL",
                "details": f"Found generic opening: '{opening}'"
            }
    return {
        "rule": "No generic opening",
        "status": "PASS",
        "details": "No generic openings detected."
    }


def check_word_count(text):
    """Rule: 300-380 words."""
    words = len(text.split())
    in_range = 300 <= words <= 380
    return {
        "rule": "Word count (300-380)",
        "status": "PASS" if in_range else "FAIL",
        "details": f"Word count: {words}" + ("" if in_range else f" ({'under' if words < 300 else 'over'} limit)")
    }


def check_i_sentences(text):
    """Rule: Max 3 sentences starting with 'I' per paragraph."""
    paragraphs = _get_body_paragraphs(text)
    worst_count = 0
    worst_para = 0

    for i, para in enumerate(paragraphs, 1):
        sentences = re.split(r'(?<=[.!?])\s+', para)
        i_count = sum(1 for s in sentences if s.strip().startswith("I ") or s.strip() == "I")
        if i_count > worst_count:
            worst_count = i_count
            worst_para = i

    failed = worst_count > 3
    return {
        "rule": "Max 3 'I' sentences per paragraph",
        "status": "FAIL" if failed else "PASS",
        "details": f"Paragraph {worst_para} has {worst_count} sentences starting with 'I'." if failed
                   else f"Max 'I' starts in any paragraph: {worst_count}."
    }


def check_work_authorization(text):
    """Rule: No work authorization mentions."""
    text_lower = text.lower()
    found = [kw for kw in WORK_AUTH_KEYWORDS if kw in text_lower]
    return {
        "rule": "No work authorization mentions",
        "status": "FAIL" if found else "PASS",
        "details": f"Found: {', '.join(found)}" if found else "No work authorization mentions."
    }


def run_deterministic_critique(text):
    """Run all deterministic (non-LLM) checks. Returns list of results + critical_failure bool."""
    checks = [
        check_em_dashes(text),
        check_banned_words(text),
        check_formatting(text),
        check_generic_opening(text),
        check_word_count(text),
        check_i_sentences(text),
        check_work_authorization(text),
    ]
    critical_failure = any(c["status"] == "FAIL" for c in checks)
    return checks, critical_failure


# ---------------------------------------------------------------
# Quality Metrics
# ---------------------------------------------------------------

def burstiness_score(text):
    """
    Measure sentence length variation (standard deviation).
    Human writing typically has stdev > 7-8. AI writing clusters around 3-5.
    """
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return 0.0
    lengths = [len(s.split()) for s in sentences]
    return round(statistics.stdev(lengths), 2)


def keyword_coverage(letter_text, jd_text, top_n=15):
    """
    Measure what fraction of JD-specific keywords appear in the letter.
    Uses simple frequency analysis to extract non-trivial keywords.
    """
    # Common words to exclude
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "and", "or",
        "but", "not", "no", "nor", "so", "yet", "both", "each", "every",
        "all", "any", "few", "more", "most", "other", "some", "such", "than",
        "too", "very", "just", "also", "about", "up", "out", "if", "then",
        "that", "this", "these", "those", "it", "its", "they", "their",
        "them", "we", "our", "you", "your", "he", "she", "him", "her", "his",
        "who", "which", "what", "when", "where", "how", "why", "i", "my", "me",
        "including", "across", "within", "using", "ensuring", "working",
        "role", "team", "experience", "ability", "work", "position",
        "company", "business", "strong", "years", "skills",
    }

    # Extract words from JD (2+ chars, alpha only)
    jd_words = re.findall(r'\b[a-zA-Z]{3,}\b', jd_text.lower())
    jd_words = [w for w in jd_words if w not in stopwords]
    freq = Counter(jd_words)

    # Get top N keywords by frequency
    top_keywords = [word for word, _ in freq.most_common(top_n)]

    if not top_keywords:
        return 0.0, [], []

    letter_lower = letter_text.lower()
    matched = [kw for kw in top_keywords if kw in letter_lower]
    missed = [kw for kw in top_keywords if kw not in letter_lower]

    coverage = len(matched) / len(top_keywords)
    return round(coverage, 2), matched, missed


def compute_quality_score(text, jd_text=None):
    """
    Compute a 0-100 deterministic quality score.
    Deductions for each failing criterion.
    """
    score = 100

    # Run deterministic checks
    checks, _ = run_deterministic_critique(text)
    for check in checks:
        if check["status"] == "FAIL":
            if "word count" in check["rule"].lower():
                score -= 10
            elif "em dash" in check["rule"].lower():
                score -= 10
            elif "banned" in check["rule"].lower():
                score -= 15
            elif "'i' sentences" in check["rule"].lower():
                score -= 10
            else:
                score -= 5

    # Burstiness penalty
    burst = burstiness_score(text)
    if burst < 4:
        score -= 15  # Very AI-like
    elif burst < 6:
        score -= 10  # Below human average
    elif burst < 8:
        score -= 5   # Slightly low

    # Keyword coverage penalty (only if JD provided)
    if jd_text:
        coverage, _, _ = keyword_coverage(text, jd_text)
        if coverage < 0.2:
            score -= 15
        elif coverage < 0.35:
            score -= 10
        elif coverage < 0.5:
            score -= 5

    return max(0, score)
