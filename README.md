# elevenlabs-agent-eval-toolkit

QA and evaluation pipeline for ElevenLabs voice agents — STT accuracy testing and conversation history analysis, with self-contained HTML report output.

---

## Background

Deploying a voice agent without validating STT accuracy against your domain vocabulary is one of the most common failure modes in enterprise contact centre AI. A model that mishears "roaming" as "Roman" or "iiNet" as "I net" creates a broken customer experience that is invisible until it's in production.

This toolkit provides a pre-launch validation pipeline and a post-launch feedback loop — the two instruments an operations team needs to manage a voice agent with confidence. Built as a reference implementation for enterprise ElevenLabs deployments in high-volume customer service contexts.

---

## What it does

```
Mode A — STT Accuracy (pre-launch)
YAML utterances → TTS synthesis → STT transcription → WER per utterance → HTML report

Mode B — Conversation History (post-launch)
ElevenLabs API → fetch sessions → analyse transcripts → containment/escalation/turn metrics → HTML report

Mode C — Full pipeline (both)
```

The output is a **single self-contained HTML file** — no server required. Open it in a browser, email it to a stakeholder, attach it to a PR.

---

## Pipeline modules

| Module | Description |
|---|---|
| `pipeline/tts.py` | Synthesizes utterances to MP3 audio via ElevenLabs TTS API |
| `pipeline/stt.py` | Transcribes audio back to text via ElevenLabs STT (Scribe v1) |
| `pipeline/wer.py` | Word Error Rate calculation — no external dependencies, pure Python |
| `pipeline/history.py` | Fetches conversation history with cursor-based pagination |
| `pipeline/analyser.py` | Pattern analysis: containment rate, turn depth, opening intents |
| `pipeline/reporter.py` | Self-contained HTML report with KPI cards, tables, recommendations |

---

## Setup

```bash
git clone https://github.com/your-username/elevenlabs-agent-eval-toolkit
cd elevenlabs-agent-eval-toolkit

python -m venv .venv && source .venv/Scripts/activate   # Windows
# python -m venv .venv && source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Fill in ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID

cp test_cases/utterances.example.yaml test_cases/utterances.yaml
# Customise utterances.yaml with your domain vocabulary
```

---

## Usage

```bash
# STT accuracy test only
python eval.py stt

# Conversation history analysis only
python eval.py history

# Full pipeline (recommended)
python eval.py full

# Full pipeline with custom options
python eval.py full --utterances test_cases/custom.yaml --limit 50
```

Open the generated report from the `output/` directory in any browser.

---

## Configuration

| Variable | Description |
|---|---|
| `ELEVENLABS_API_KEY` | ElevenLabs API key — needs TTS, STT, ElevenAgents Read access |
| `ELEVENLABS_AGENT_ID` | Agent to pull conversation history from |
| `EVAL_VOICE_ID` | Optional — TTS voice for utterance synthesis (default: Rachel) |

### WER classification thresholds

| Range | Classification | Meaning |
|---|---|---|
| < 10% | ✓ PASS | Production-ready |
| 10–30% | ⚠ WARN | Review before launch |
| > 30% | ✗ FAIL | Likely to cause poor CX |

---

## Report sections

**STT Accuracy** — per-utterance table with original text, STT transcription, WER score, and pass/warn/fail classification. Overall accuracy percentage with visual bar.

**Conversation History** — KPI cards (containment rate, avg turns, avg duration, escalations), turn depth distribution, top customer opening intents, recent session table.

**Recommendations** — auto-generated from eval results: flagged vocabulary, containment improvement suggestions, turn depth analysis.

---

## Extending

**Push reports to cloud storage:**
```python
# After report generation, upload to GCS:
# from google.cloud import storage
# bucket.blob(f"eval-reports/{report_path.name}").upload_from_filename(report_path)
```

**Schedule regular eval runs:**
```bash
# Add to cron or GitHub Actions:
# python eval.py history --limit 100 --output reports/
```

**Add custom WER thresholds per category:**
```yaml
# In utterances.yaml — tag utterances by sensitivity:
billing:
  - text: "I'd like to dispute a charge."
    tags: [billing, high-sensitivity]
```

---

## Stack

`Python · httpx · click · PyYAML · Rich · ElevenLabs TTS API · ElevenLabs STT API (Scribe v1) · ElevenLabs Conversations API`
