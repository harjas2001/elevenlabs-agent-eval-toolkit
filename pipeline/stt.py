"""
stt.py — ElevenLabs Speech-to-Text transcription

Transcribes MP3 audio bytes back to text using the ElevenLabs STT API (Scribe v1).
Used in the eval pipeline to measure how accurately the STT layer handles
domain-specific telco vocabulary before an agent goes live.
"""

import httpx
from rich.console import Console

console = Console()

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def transcribe(audio_bytes: bytes, api_key: str) -> str:
    """
    Transcribe raw MP3 audio bytes to text.

    Args:
        audio_bytes: MP3 audio bytes from the TTS module.
        api_key:     ElevenLabs API key.

    Returns:
        Transcribed text string.

    Raises:
        RuntimeError: If the ElevenLabs API returns a non-200 status.
    """
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            ELEVENLABS_STT_URL,
            headers={"xi-api-key": api_key},
            files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            data={"model_id": "scribe_v1"},
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"STT API error {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    return data.get("text", "").strip()


def transcribe_batch(
    synthesized: list[dict],
    api_key: str,
) -> list[dict]:
    """
    Transcribe a batch of synthesized utterances.

    Args:
        synthesized: Output from tts.synthesize_batch — each dict includes
                     "audio_bytes" and "tts_error".
        api_key:     ElevenLabs API key.

    Returns:
        List of dicts with added "transcription" and "stt_error" keys.
    """
    results = []
    total = len(synthesized)

    for i, item in enumerate(synthesized, 1):
        if item.get("tts_error"):
            results.append({**item, "transcription": None, "stt_error": "skipped (TTS failed)"})
            continue

        text_preview = item["text"][:60]
        console.print(
            f"  [dim]STT[/dim] [{i}/{total}] {text_preview}{'…' if len(item['text']) > 60 else ''}"
        )
        try:
            transcription = transcribe(item["audio_bytes"], api_key)
            results.append({**item, "transcription": transcription, "stt_error": None})
        except RuntimeError as e:
            console.print(f"    [red]✗ STT failed:[/red] {e}")
            results.append({**item, "transcription": None, "stt_error": str(e)})

    return results
