"""
analyser.py — Conversation history pattern analysis

Analyses transcripts from completed agent conversations to surface
operational insights: containment rate, escalation triggers, turn depth
distribution, and the most common customer opening intents.
"""

from collections import Counter
from datetime import datetime, timezone

ESCALATION_MARKER = "connect you with one of our specialists"


def analyse(conversations: list[dict]) -> dict:
    """
    Analyse a list of enriched conversation dicts (from history.fetch_with_transcripts).

    Returns:
        A structured analysis dict with summary metrics and pattern data.
    """
    if not conversations:
        return _empty_analysis()

    total            = len(conversations)
    escalated        = []
    contained        = []
    turn_counts      = []
    durations        = []
    opening_intents  = []

    for conv in conversations:
        transcript = conv.get("transcript", [])

        # ── Turn count (user messages only) ──────────────────────────────
        user_turns = [m for m in transcript if m.get("role") == "user"]
        turn_counts.append(len(user_turns))

        # ── Escalation detection ─────────────────────────────────────────
        is_escalated = any(
            ESCALATION_MARKER in m.get("message", "").lower()
            for m in transcript
            if m.get("role") == "agent"
        )
        (escalated if is_escalated else contained).append(conv)

        # ── Duration ─────────────────────────────────────────────────────
        dur = conv.get("call_duration_secs")
        if dur:
            durations.append(dur)

        # ── Opening intent (first user message) ──────────────────────────
        first_user = next(
            (m.get("message", "").strip() for m in transcript if m.get("role") == "user"),
            None,
        )
        if first_user:
            opening_intents.append(_truncate(first_user, 80))

    avg_turns    = round(sum(turn_counts) / len(turn_counts), 1) if turn_counts else 0
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    # ── Turn depth distribution ───────────────────────────────────────────
    turn_distribution = {
        "1–2 turns":  sum(1 for t in turn_counts if 1 <= t <= 2),
        "3–5 turns":  sum(1 for t in turn_counts if 3 <= t <= 5),
        "6–10 turns": sum(1 for t in turn_counts if 6 <= t <= 10),
        "10+ turns":  sum(1 for t in turn_counts if t > 10),
    }

    # ── Most common opening intents ───────────────────────────────────────
    intent_counts = Counter(opening_intents).most_common(8)

    # ── Recent sessions for the report table ─────────────────────────────
    recent = []
    for conv in conversations[:10]:
        transcript = conv.get("transcript", [])
        user_turns = [m for m in transcript if m.get("role") == "user"]
        is_esc = any(
            ESCALATION_MARKER in m.get("message", "").lower()
            for m in transcript
            if m.get("role") == "agent"
        )
        start_unix = conv.get("start_time_unix_secs")
        start_str  = (
            datetime.fromtimestamp(start_unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            if start_unix else "—"
        )
        recent.append({
            "conversation_id": conv.get("conversation_id", "—"),
            "start_time":      start_str,
            "duration_secs":   conv.get("call_duration_secs", 0),
            "turn_count":      len(user_turns),
            "escalated":       is_esc,
        })

    return {
        "total_conversations":  total,
        "contained_count":      len(contained),
        "escalated_count":      len(escalated),
        "containment_rate":     round(len(contained) / total * 100, 1),
        "escalation_rate":      round(len(escalated) / total * 100, 1),
        "avg_turns":            avg_turns,
        "avg_duration_secs":    avg_duration,
        "turn_distribution":    turn_distribution,
        "top_opening_intents":  intent_counts,
        "recent_sessions":      recent,
    }


def generate_recommendations(stt_agg: dict | None, history_agg: dict | None) -> list[str]:
    """
    Auto-generate actionable recommendations from eval results.

    Returns:
        List of recommendation strings for the report.
    """
    recs = []

    if stt_agg:
        if stt_agg.get("fail_count", 0) > 0:
            recs.append(
                f"{stt_agg['fail_count']} utterance(s) failed STT accuracy (WER > 30%). "
                "Review flagged phrases and consider adding phonetic variations to your "
                "agent's knowledge base or system prompt."
            )
        if stt_agg.get("warn_count", 0) > 0:
            recs.append(
                f"{stt_agg['warn_count']} utterance(s) scored in the warning range (WER 10–30%). "
                "Test these phrases in your target deployment environment (phone/web) before go-live."
            )
        acc = stt_agg.get("overall_accuracy")
        if acc and acc >= 95:
            recs.append(
                "STT accuracy is excellent (≥ 95%). The voice model handles your domain "
                "vocabulary reliably — no pre-launch remediation required."
            )

    if history_agg:
        if history_agg.get("containment_rate", 100) < 70:
            recs.append(
                f"Containment rate is {history_agg['containment_rate']}% — below the recommended "
                "70% threshold. Review escalation triggers and expand the agent's knowledge base "
                "to cover unhandled query types."
            )
        if history_agg.get("avg_turns", 0) > 7:
            recs.append(
                f"Average session length is {history_agg['avg_turns']} turns — higher than expected "
                "for a self-service agent. Review the agent's response conciseness and "
                "consider adding structured decision flows for high-frequency intents."
            )
        if history_agg.get("escalation_rate", 0) > 30:
            recs.append(
                f"Escalation rate is {history_agg['escalation_rate']}% — consider reviewing the "
                "top opening intents to identify query types the agent is not handling."
            )

    if not recs:
        recs.append("No critical issues detected. Agent is performing within acceptable parameters.")

    return recs


def _empty_analysis() -> dict:
    return {
        "total_conversations": 0,
        "contained_count": 0,
        "escalated_count": 0,
        "containment_rate": 0.0,
        "escalation_rate": 0.0,
        "avg_turns": 0.0,
        "avg_duration_secs": 0.0,
        "turn_distribution": {},
        "top_opening_intents": [],
        "recent_sessions": [],
    }


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"
