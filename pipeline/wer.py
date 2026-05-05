"""
wer.py — Word Error Rate calculation and result classification

Computes WER between the original utterance and the STT transcription.
WER = (Substitutions + Deletions + Insertions) / Total reference words

Classification thresholds:
    PASS     WER < 0.10   — production-ready accuracy
    WARN     0.10–0.30    — review recommended before launch
    FAIL     WER > 0.30   — likely to cause bad customer experience
"""

import re


def _normalise(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into word tokens."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.split()


def _edit_distance(ref: list[str], hyp: list[str]) -> int:
    """
    Compute the Levenshtein edit distance between two word sequences.
    Standard dynamic programming implementation.
    """
    m, n = len(ref), len(hyp)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion
                    dp[i][j - 1],      # insertion
                    dp[i - 1][j - 1],  # substitution
                )

    return dp[m][n]


def compute_wer(reference: str, hypothesis: str) -> float:
    """
    Compute Word Error Rate between reference and hypothesis strings.

    Returns:
        WER as a float (0.0 = perfect, 1.0 = completely wrong).
        Returns 1.0 if reference is empty.
    """
    ref_tokens = _normalise(reference)
    hyp_tokens = _normalise(hypothesis) if hypothesis else []

    if not ref_tokens:
        return 1.0

    distance = _edit_distance(ref_tokens, hyp_tokens)
    return round(min(distance / len(ref_tokens), 1.0), 4)


def classify(wer_score: float) -> str:
    """Classify a WER score as PASS, WARN, or FAIL."""
    if wer_score < 0.10:
        return "PASS"
    elif wer_score <= 0.30:
        return "WARN"
    else:
        return "FAIL"


def score_batch(transcribed: list[dict]) -> list[dict]:
    """
    Compute WER and classification for each transcribed utterance.

    Args:
        transcribed: Output from stt.transcribe_batch.

    Returns:
        List of dicts with added "wer", "classification", and "word_count" keys.
    """
    results = []
    for item in transcribed:
        if item.get("stt_error") or item.get("tts_error"):
            results.append({
                **item,
                "wer": None,
                "classification": "ERROR",
                "word_count": len(item["text"].split()),
            })
            continue

        wer_score = compute_wer(item["text"], item["transcription"])
        results.append({
            **item,
            "wer": wer_score,
            "classification": classify(wer_score),
            "word_count": len(_normalise(item["text"])),
        })

    return results


def aggregate(scored: list[dict]) -> dict:
    """
    Compute aggregate STT accuracy metrics across all scored utterances.

    Returns:
        Dict with overall_accuracy, avg_wer, pass/warn/fail counts,
        and a list of flagged utterances (WARN or FAIL).
    """
    valid = [s for s in scored if s["wer"] is not None]

    if not valid:
        return {
            "total": len(scored),
            "valid": 0,
            "avg_wer": None,
            "overall_accuracy": None,
            "pass_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "error_count": len(scored),
            "flagged": [],
        }

    avg_wer = sum(s["wer"] for s in valid) / len(valid)
    pass_count = sum(1 for s in valid if s["classification"] == "PASS")
    warn_count = sum(1 for s in valid if s["classification"] == "WARN")
    fail_count = sum(1 for s in valid if s["classification"] == "FAIL")
    error_count = len(scored) - len(valid)
    overall_accuracy = round((1 - avg_wer) * 100, 1)

    flagged = [s for s in valid if s["classification"] in ("WARN", "FAIL")]

    return {
        "total": len(scored),
        "valid": len(valid),
        "avg_wer": round(avg_wer, 4),
        "overall_accuracy": overall_accuracy,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "error_count": error_count,
        "flagged": flagged,
    }
