"""
reporter.py — Self-contained HTML report generation

Produces a single HTML file from eval results. The report is fully
self-contained (no external dependencies) so it can be emailed to a
customer's team or attached to a pull request without any server.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def generate(
    agent_id: str,
    mode: str,
    stt_scored: list[dict] | None,
    stt_agg: dict | None,
    history_agg: dict | None,
    recommendations: list[str],
    output_path: Path,
) -> Path:
    """
    Render the evaluation report to an HTML file.

    Args:
        agent_id:        ElevenLabs agent ID (displayed in report header).
        mode:            Eval mode: "stt", "history", or "full".
        stt_scored:      Per-utterance scored results from wer.score_batch.
        stt_agg:         Aggregated STT metrics from wer.aggregate.
        history_agg:     Aggregated history metrics from analyser.analyse.
        recommendations: List of recommendation strings.
        output_path:     Path to write the HTML file.

    Returns:
        The output path.
    """
    run_time = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = _render(agent_id, mode, run_time, stt_scored, stt_agg, history_agg, recommendations)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ── HTML rendering ────────────────────────────────────────────────────────────

def _render(agent_id, mode, run_time, stt_scored, stt_agg, history_agg, recommendations) -> str:
    stt_section     = _stt_section(stt_scored, stt_agg) if stt_agg else ""
    history_section = _history_section(history_agg) if history_agg else ""
    rec_section     = _recommendations_section(recommendations)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Agent Eval Report — {run_time}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');

  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
  :root{{
    --bg:#F7F8FA;
    --white:#FFFFFF;
    --border:#E4E6EE;
    --text:#111318;
    --text-2:#5A6070;
    --text-3:#9BA3B8;
    --accent:#FF5733;
    --ok:#00A868;
    --ok-bg:#F0FBF7;
    --warn:#B87300;
    --warn-bg:#FFFBF0;
    --danger:#CC2244;
    --danger-bg:#FFF5F7;
    --ui:'Syne',sans-serif;
    --mono:'IBM Plex Mono',monospace;
    --radius:10px;
  }}
  body{{font-family:var(--ui);background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;padding:40px 24px;}}
  .container{{max-width:960px;margin:0 auto;display:flex;flex-direction:column;gap:32px;}}

  /* Header */
  .report-header{{background:var(--text);color:#fff;border-radius:var(--radius);padding:32px 36px;}}
  .report-title{{font-size:26px;font-weight:800;letter-spacing:-0.5px;margin-bottom:6px;}}
  .report-meta{{display:flex;gap:24px;flex-wrap:wrap;margin-top:16px;}}
  .meta-item{{font-family:var(--mono);font-size:12px;color:rgba(255,255,255,0.55);}}
  .meta-item span{{color:rgba(255,255,255,0.9);margin-left:4px;}}
  .mode-badge{{display:inline-block;background:var(--accent);color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:0.5px;text-transform:uppercase;margin-top:12px;}}

  /* Cards */
  .card{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);padding:28px 32px;}}
  .card-title{{font-size:16px;font-weight:700;letter-spacing:-0.2px;margin-bottom:4px;}}
  .card-sub{{font-size:12px;color:var(--text-2);margin-bottom:20px;}}

  /* KPI row */
  .kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin-bottom:24px;}}
  .kpi{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:16px;}}
  .kpi-val{{font-family:var(--mono);font-size:28px;font-weight:500;line-height:1;margin-bottom:6px;}}
  .kpi-lbl{{font-size:11px;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:0.5px;}}
  .ok{{color:var(--ok);}} .danger{{color:var(--danger);}} .warn{{color:var(--warn);}} .accent{{color:var(--accent);}}

  /* Accuracy bar */
  .acc-bar-wrap{{height:8px;background:var(--bg);border-radius:4px;overflow:hidden;margin-bottom:24px;}}
  .acc-bar{{height:100%;border-radius:4px;background:var(--ok);transition:width 0.6s ease;}}

  /* Table */
  table{{width:100%;border-collapse:collapse;font-size:13px;}}
  th{{text-align:left;font-size:10px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;color:var(--text-3);padding:0 12px 10px;border-bottom:1px solid var(--border);}}
  td{{padding:11px 12px;border-bottom:1px solid var(--border);vertical-align:top;}}
  tr:last-child td{{border-bottom:none;}}
  tr:hover td{{background:var(--bg);}}
  .mono{{font-family:var(--mono);font-size:12px;}}

  /* Tags */
  .tag{{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;font-family:var(--mono);}}
  .tag-ok{{background:var(--ok-bg);color:var(--ok);border:1px solid rgba(0,168,104,0.2);}}
  .tag-warn{{background:var(--warn-bg);color:var(--warn);border:1px solid rgba(184,115,0,0.2);}}
  .tag-fail{{background:var(--danger-bg);color:var(--danger);border:1px solid rgba(204,34,68,0.2);}}
  .tag-err{{background:#f5f5f5;color:#888;border:1px solid #ddd;}}

  /* Distribution bar */
  .dist-row{{display:flex;align-items:center;gap:12px;margin-bottom:10px;font-size:13px;}}
  .dist-label{{width:90px;color:var(--text-2);flex-shrink:0;}}
  .dist-bar-wrap{{flex:1;height:8px;background:var(--bg);border-radius:4px;overflow:hidden;}}
  .dist-bar{{height:100%;background:var(--accent);border-radius:4px;opacity:0.7;}}
  .dist-count{{width:30px;text-align:right;font-family:var(--mono);font-size:12px;color:var(--text-2);}}

  /* Intents list */
  .intent-item{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;}}
  .intent-item:last-child{{border-bottom:none;}}
  .intent-count{{font-family:var(--mono);font-size:12px;color:var(--text-2);flex-shrink:0;margin-left:16px;}}

  /* Recommendations */
  .rec-item{{display:flex;gap:12px;padding:14px 0;border-bottom:1px solid var(--border);}}
  .rec-item:last-child{{border-bottom:none;}}
  .rec-icon{{font-size:16px;flex-shrink:0;margin-top:1px;}}
  .rec-text{{font-size:13px;line-height:1.6;color:var(--text);}}

  /* Footer */
  .report-footer{{text-align:center;font-size:11px;color:var(--text-3);font-family:var(--mono);padding-bottom:16px;}}
</style>
</head>
<body>
<div class="container">

  <div class="report-header">
    <div class="report-title">Agent Evaluation Report</div>
    <div class="mode-badge">{mode.upper()} PIPELINE</div>
    <div class="report-meta">
      <div class="meta-item">Agent ID<span>{agent_id}</span></div>
      <div class="meta-item">Generated<span>{run_time}</span></div>
      <div class="meta-item">Tool<span>elevenlabs-agent-eval-toolkit</span></div>
    </div>
  </div>

  {stt_section}
  {history_section}
  {rec_section}

  <div class="report-footer">
    elevenlabs-agent-eval-toolkit · github.com/harjasgill · {run_time}
  </div>

</div>
</body>
</html>"""


def _stt_section(scored, agg) -> str:
    acc   = agg.get("overall_accuracy", 0) or 0
    color = "ok" if acc >= 90 else ("warn" if acc >= 70 else "danger")

    rows = ""
    for item in (scored or []):
        orig  = item.get("text", "")
        trans = item.get("transcription") or "—"
        wer_v = item.get("wer")
        cls   = item.get("classification", "ERROR")
        wer_s = f"{wer_v:.1%}" if wer_v is not None else "—"
        tag_cls = {"PASS": "tag-ok", "WARN": "tag-warn", "FAIL": "tag-fail"}.get(cls, "tag-err")
        tag_icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(cls, "?")
        cat = item.get("category", "—")
        rows += f"""
        <tr>
          <td style="color:#888;font-family:var(--mono);font-size:11px">{cat}</td>
          <td>{orig}</td>
          <td style="color:var(--text-2)">{trans}</td>
          <td class="mono">{wer_s}</td>
          <td><span class="tag {tag_cls}">{tag_icon} {cls}</span></td>
        </tr>"""

    return f"""
  <div class="card">
    <div class="card-title">STT Accuracy Test</div>
    <div class="card-sub">Utterances synthesized via TTS then transcribed via STT — measures pre-launch voice recognition accuracy</div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-val {color}">{acc}%</div><div class="kpi-lbl">Overall Accuracy</div></div>
      <div class="kpi"><div class="kpi-val">{agg.get('total',0)}</div><div class="kpi-lbl">Utterances Tested</div></div>
      <div class="kpi"><div class="kpi-val ok">{agg.get('pass_count',0)}</div><div class="kpi-lbl">Pass</div></div>
      <div class="kpi"><div class="kpi-val warn">{agg.get('warn_count',0)}</div><div class="kpi-lbl">Warning</div></div>
      <div class="kpi"><div class="kpi-val danger">{agg.get('fail_count',0)}</div><div class="kpi-lbl">Fail</div></div>
    </div>

    <div class="acc-bar-wrap">
      <div class="acc-bar" style="width:{min(acc,100)}%"></div>
    </div>

    <table>
      <thead><tr><th>Category</th><th>Original Utterance</th><th>STT Transcription</th><th>WER</th><th>Result</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""


def _history_section(agg) -> str:
    cr     = agg.get("containment_rate", 0)
    cr_cls = "ok" if cr >= 80 else ("warn" if cr >= 60 else "danger")

    avg_dur = agg.get("avg_duration_secs", 0)
    dur_str = f"{int(avg_dur // 60)}m {int(avg_dur % 60)}s" if avg_dur else "—"

    # Turn distribution
    dist_html  = ""
    dist_data  = agg.get("turn_distribution", {})
    max_count  = max(dist_data.values(), default=1) or 1
    for label, count in dist_data.items():
        width = round(count / max_count * 100)
        dist_html += f"""
        <div class="dist-row">
          <div class="dist-label">{label}</div>
          <div class="dist-bar-wrap"><div class="dist-bar" style="width:{width}%"></div></div>
          <div class="dist-count">{count}</div>
        </div>"""

    # Top intents
    intents_html = ""
    for text, count in agg.get("top_opening_intents", []):
        intents_html += f"""
        <div class="intent-item">
          <span>{text}</span>
          <span class="intent-count">{count}×</span>
        </div>"""
    if not intents_html:
        intents_html = '<div style="color:var(--text-3);padding:12px 0;font-size:13px">No transcript data available</div>'

    # Recent sessions table
    session_rows = ""
    for s in agg.get("recent_sessions", []):
        dur    = s.get("duration_secs", 0)
        ds     = f"{int(dur // 60)}m {int(dur % 60)}s" if dur else "—"
        esc    = s.get("escalated", False)
        tag    = '<span class="tag tag-fail">⚠ Escalated</span>' if esc else '<span class="tag tag-ok">✓ Contained</span>'
        cid    = s.get("conversation_id", "—")
        cid_s  = cid[:20] + "…" if len(cid) > 20 else cid
        session_rows += f"""
        <tr>
          <td class="mono" style="color:var(--text-2)">{cid_s}</td>
          <td>{s.get('start_time','—')}</td>
          <td class="mono">{ds}</td>
          <td class="mono">{s.get('turn_count',0)}</td>
          <td>{tag}</td>
        </tr>"""

    if not session_rows:
        session_rows = '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:20px">No sessions available</td></tr>'

    return f"""
  <div class="card">
    <div class="card-title">Conversation History Analysis</div>
    <div class="card-sub">Pattern analysis across {agg.get('total_conversations',0)} completed agent sessions</div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-val accent">{agg.get('total_conversations',0)}</div><div class="kpi-lbl">Total Sessions</div></div>
      <div class="kpi"><div class="kpi-val {cr_cls}">{cr}%</div><div class="kpi-lbl">Containment Rate</div></div>
      <div class="kpi"><div class="kpi-val">{agg.get('avg_turns',0)}</div><div class="kpi-lbl">Avg Turns</div></div>
      <div class="kpi"><div class="kpi-val">{dur_str}</div><div class="kpi-lbl">Avg Duration</div></div>
      <div class="kpi"><div class="kpi-val danger">{agg.get('escalated_count',0)}</div><div class="kpi-lbl">Escalations</div></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:28px">
      <div>
        <div style="font-size:12px;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px">Turn Depth Distribution</div>
        {dist_html}
      </div>
      <div>
        <div style="font-size:12px;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px">Top Opening Intents</div>
        {intents_html}
      </div>
    </div>

    <div style="font-size:12px;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px">Recent Sessions</div>
    <table>
      <thead><tr><th>Conversation ID</th><th>Start Time</th><th>Duration</th><th>Turns</th><th>Status</th></tr></thead>
      <tbody>{session_rows}</tbody>
    </table>
  </div>"""


def _recommendations_section(recommendations) -> str:
    items = ""
    for rec in recommendations:
        icon = "✓" if "excellent" in rec.lower() or "no critical" in rec.lower() else "→"
        color = "var(--ok)" if icon == "✓" else "var(--accent)"
        items += f"""
        <div class="rec-item">
          <div class="rec-icon" style="color:{color}">{icon}</div>
          <div class="rec-text">{rec}</div>
        </div>"""

    return f"""
  <div class="card">
    <div class="card-title">Recommendations</div>
    <div class="card-sub">Auto-generated from eval results</div>
    {items}
  </div>"""
