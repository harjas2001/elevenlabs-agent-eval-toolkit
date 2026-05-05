"""
tts.py — ElevenLabs Text-to-Speech synthesis

Converts plaintext utterances to audio bytes using the ElevenLabs TTS API.
Audio is returned in-memory (MP3) and passed directly to the STT module —
no files are written to disk during a standard eval run.
"""

import os
import httpx
from rich.console import Console

console = Console()

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Rachel — neutral, clear diction, reliable for STT eval purposes.
# Override via EVAL_VOICE_ID in .env to use a custom voice.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def synthesize(text: str, api_key: str) -> bytes:
    """
    Synthesize a single utterance to MP3 audio bytes.

    Args:
        text:    The utterance to synthesize.
        api_key: ElevenLabs API key.

    Returns:
        Raw MP3 audio bytes.

    Raises:
        RuntimeError: If the ElevenLabs API returns a non-200 status.
    """
    voice_id = os.getenv("EVAL_VOICE_ID", DEFAULT_VOICE_ID)
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.6,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={
                "xi-api-key": api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"TTS API error {response.status_code}: {response.text[:200]}"
        )

    return response.content


def synthesize_batch(
    utterances: list[dict],
    api_key: str,
) -> list[dict]:
    """
    Synthesize a list of utterances, attaching audio bytes to each result dict.

    Args:
        utterances: List of dicts with at minimum {"text": str, "category": str}.
        api_key:    ElevenLabs API key.

    Returns:
        List of dicts with added "audio_bytes" key, or "tts_error" on failure.
    """
    results = []
    for i, utt in enumerate(utterances, 1):
        text = utt["text"]
        console.print(
            f"  [dim]TTS[/dim] [{i}/{len(utterances)}] {text[:60]}{'…' if len(text) > 60 else ''}"
        )
        try:
            audio = synthesize(text, api_key)
            results.append({**utt, "audio_bytes": audio, "tts_error": None})
        except RuntimeError as e:
            console.print(f"    [red]✗ TTS failed:[/red] {e}")
            results.append({**utt, "audio_bytes": None, "tts_error": str(e)})

    return results
