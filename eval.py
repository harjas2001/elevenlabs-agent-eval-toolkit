"""
eval.py — ElevenLabs Agent Eval Toolkit

CLI entry point for running STT accuracy tests and conversation history
analysis against a deployed ElevenLabs voice agent.

Usage:
    python eval.py stt                  # STT accuracy test only
    python eval.py history              # Conversation history analysis only
    python eval.py full                 # Both pipelines
    python eval.py full --limit 30      # History: fetch last 30 conversations
    python eval.py stt --utterances test_cases/custom.yaml

Options:
    --utterances  Path to YAML test case file  [default: test_cases/utterances.yaml]
    --limit       Max conversations to fetch for history analysis  [default: 20]
    --output      Output directory for HTML report  [default: output/]
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule

load_dotenv()
console = Console()


def _require_env(*keys: str) -> dict[str, str]:
    """Load and validate required environment variables."""
    values = {}
    missing = []
    for key in keys:
        val = os.getenv(key)
        if not val:
            missing.append(key)
        else:
            values[key] = val
    if missing:
        console.print(f"\n[red]✗ Missing environment variables:[/red] {', '.join(missing)}")
        console.print("  Copy .env.example to .env and fill in the values.\n")
        sys.exit(1)
    return values


def _load_utterances(path: Path) -> list[dict]:
    """Load and flatten utterances from a YAML file into a list of dicts."""
    if not path.exists():
        console.print(f"\n[red]✗ Test case file not found:[/red] {path}")
        console.print(
            f"  Copy test_cases/utterances.example.yaml to {path} and customise it.\n"
        )
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    utterances = []
    for category, items in data.items():
        for item in items:
            utterances.append({
                "category": category,
                "text":     item["text"],
                "tags":     item.get("tags", []),
            })

    return utterances


def _run_report(
    mode: str,
    agent_id: str,
    stt_scored=None,
    stt_agg=None,
    history_agg=None,
    recommendations=None,
    output_dir: Path = Path("output"),
) -> Path:
    from pipeline.reporter import generate

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"eval_report_{mode}_{timestamp}.html"

    return generate(
        agent_id=agent_id,
        mode=mode,
        stt_scored=stt_scored,
        stt_agg=stt_agg,
        history_agg=history_agg,
        recommendations=recommendations or [],
        output_path=output_path,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """ElevenLabs Agent Eval Toolkit — STT accuracy + conversation history analysis."""
    pass


@cli.command()
@click.option("--utterances", default="test_cases/utterances.yaml", show_default=True,
              help="Path to YAML utterance test cases.")
@click.option("--output", default="output", show_default=True,
              help="Directory to write the HTML report.")
def stt(utterances, output):
    """Run STT accuracy test: TTS → STT → WER per utterance."""
    from pipeline import tts as tts_mod
    from pipeline import stt as stt_mod
    from pipeline import wer as wer_mod
    from pipeline.analyser import generate_recommendations

    env = _require_env("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID")
    api_key  = env["ELEVENLABS_API_KEY"]
    agent_id = env["ELEVENLABS_AGENT_ID"]

    console.print(Rule("[bold]STT Accuracy Pipeline[/bold]"))
    utt_list = _load_utterances(Path(utterances))
    console.print(f"  Loaded [bold]{len(utt_list)}[/bold] utterances from [dim]{utterances}[/dim]\n")

    console.print("[bold]Step 1/3[/bold] — Synthesizing utterances via TTS…")
    synthesized = tts_mod.synthesize_batch(utt_list, api_key)

    console.print("\n[bold]Step 2/3[/bold] — Transcribing audio via STT…")
    transcribed = stt_mod.transcribe_batch(synthesized, api_key)

    console.print("\n[bold]Step 3/3[/bold] — Scoring WER…")
    scored = wer_mod.score_batch(transcribed)
    agg    = wer_mod.aggregate(scored)

    _print_stt_summary(agg)
    recs  = generate_recommendations(agg, None)
    path  = _run_report("stt", agent_id, stt_scored=scored, stt_agg=agg,
                         recommendations=recs, output_dir=Path(output))
    console.print(f"\n[green]✓ Report written to:[/green] [bold]{path}[/bold]\n")


@cli.command()
@click.option("--limit", default=20, show_default=True,
              help="Maximum number of conversations to fetch.")
@click.option("--output", default="output", show_default=True,
              help="Directory to write the HTML report.")
def history(limit, output):
    """Analyse conversation history from a deployed agent."""
    from pipeline.history import fetch_with_transcripts
    from pipeline.analyser import analyse, generate_recommendations

    env = _require_env("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID")
    api_key  = env["ELEVENLABS_API_KEY"]
    agent_id = env["ELEVENLABS_AGENT_ID"]

    console.print(Rule("[bold]Conversation History Pipeline[/bold]"))
    console.print(f"  Agent: [bold]{agent_id}[/bold] | Limit: {limit}\n")

    console.print("[bold]Step 1/2[/bold] — Fetching conversations…")
    conversations = fetch_with_transcripts(agent_id, api_key, limit=limit)

    console.print("\n[bold]Step 2/2[/bold] — Analysing patterns…")
    agg = analyse(conversations)

    _print_history_summary(agg)
    recs = generate_recommendations(None, agg)
    path = _run_report("history", agent_id, history_agg=agg,
                        recommendations=recs, output_dir=Path(output))
    console.print(f"\n[green]✓ Report written to:[/green] [bold]{path}[/bold]\n")


@cli.command()
@click.option("--utterances", default="test_cases/utterances.yaml", show_default=True,
              help="Path to YAML utterance test cases.")
@click.option("--limit", default=20, show_default=True,
              help="Maximum number of conversations to fetch for history analysis.")
@click.option("--output", default="output", show_default=True,
              help="Directory to write the HTML report.")
def full(utterances, limit, output):
    """Run full pipeline: STT accuracy test + conversation history analysis."""
    from pipeline import tts as tts_mod
    from pipeline import stt as stt_mod
    from pipeline import wer as wer_mod
    from pipeline.history import fetch_with_transcripts
    from pipeline.analyser import analyse, generate_recommendations

    env = _require_env("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID")
    api_key  = env["ELEVENLABS_API_KEY"]
    agent_id = env["ELEVENLABS_AGENT_ID"]

    console.print(Rule("[bold]Full Evaluation Pipeline[/bold]"))

    # ── STT ──────────────────────────────────────────────────────────────
    console.print("\n[bold cyan]── STT Accuracy ────────────────────────────────────[/bold cyan]")
    utt_list    = _load_utterances(Path(utterances))
    console.print(f"  Loaded [bold]{len(utt_list)}[/bold] utterances\n")

    synthesized = tts_mod.synthesize_batch(utt_list, api_key)
    transcribed = stt_mod.transcribe_batch(synthesized, api_key)
    scored      = wer_mod.score_batch(transcribed)
    stt_agg     = wer_mod.aggregate(scored)
    _print_stt_summary(stt_agg)

    # ── History ───────────────────────────────────────────────────────────
    console.print("\n[bold cyan]── Conversation History ─────────────────────────────[/bold cyan]")
    conversations = fetch_with_transcripts(agent_id, api_key, limit=limit)
    history_agg   = analyse(conversations)
    _print_history_summary(history_agg)

    # ── Report ────────────────────────────────────────────────────────────
    recs = generate_recommendations(stt_agg, history_agg)
    path = _run_report("full", agent_id, stt_scored=scored, stt_agg=stt_agg,
                        history_agg=history_agg, recommendations=recs, output_dir=Path(output))
    console.print(f"\n[green]✓ Report written to:[/green] [bold]{path}[/bold]\n")


# ── Terminal summary printers ─────────────────────────────────────────────────

def _print_stt_summary(agg: dict) -> None:
    acc = agg.get("overall_accuracy")
    colour = "green" if (acc or 0) >= 90 else ("yellow" if (acc or 0) >= 70 else "red")
    console.print(f"\n  Overall accuracy: [{colour}]{acc}%[/{colour}]")
    console.print(f"  Pass: {agg.get('pass_count',0)}  "
                  f"Warn: {agg.get('warn_count',0)}  "
                  f"Fail: {agg.get('fail_count',0)}  "
                  f"Error: {agg.get('error_count',0)}")
    if agg.get("flagged"):
        console.print(f"  [yellow]Flagged utterances:[/yellow]")
        for f in agg["flagged"]:
            console.print(f"    [{f['classification']}] {f['text'][:70]}")


def _print_history_summary(agg: dict) -> None:
    cr = agg.get("containment_rate", 0)
    colour = "green" if cr >= 80 else ("yellow" if cr >= 60 else "red")
    console.print(f"\n  Total sessions:    {agg.get('total_conversations', 0)}")
    console.print(f"  Containment rate:  [{colour}]{cr}%[/{colour}]")
    console.print(f"  Escalations:       {agg.get('escalated_count', 0)}")
    console.print(f"  Avg turns:         {agg.get('avg_turns', 0)}")


if __name__ == "__main__":
    cli()