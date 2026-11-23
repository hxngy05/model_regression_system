# src/alerter.py
import os
from pathlib import Path
from typing import Optional
import requests

from src.schemas import RollingDriftResult, RunComparisonResult, RunEvaluationSummary

WEBHOOK_ENV_VAR = "SLACK_WEBHOOK_URL"


def build_slack_payload(
    current_run: RunEvaluationSummary,
    comparison: RunComparisonResult,
    baseline_run: Optional[RunEvaluationSummary] = None,
    report_path: Optional[Path] = None,
    report_url: Optional[str] = None,
    drift_result: Optional[RollingDriftResult] = None
) -> dict:
    """Builds a structured Slack Block Kit payload for an evaluation run."""
    status = comparison.severity_status.lower()
    status_badge = {
        "pass": ":white_check_mark: *PASS*",
        "warn": ":warning: *WARN*",
        "fail": ":rotating_light: *FAIL*",
    }.get(status, f"*{status.upper()}*")

    current_pct = f"{current_run.pass_rate * 100:.1f}%"
    if baseline_run is not None:
        baseline_pct = f"{baseline_run.pass_rate * 100:.1f}%"
        delta_pp = f"{comparison.pass_rate_delta * 100:+.1f} pp"
        pass_rate_line = f"{current_pct} (vs. {baseline_pct}, {delta_pp})"
    else:
        pass_rate_line = f"{current_pct} (initial baseline)"

    report_link_text = ""
    if report_url:
        report_link_text = f"\n*Diff Report:* <{report_url}|View HTML Diff Report>"
    elif report_path is not None:
        report_link_text = f"\n*Diff Report:* `{report_path}`"

    headline_summary = (
        f"{status_badge} — *{comparison.regressions_count}* regression(s), "
        f"*{comparison.improvements_count}* improvement(s); pass rate *{pass_rate_line}*"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"LLM Eval Alert: {current_run.prompt_version}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{headline_summary}\n{comparison.alert_message}{report_link_text}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*Run:* `{current_run.run_id}` | "
                        f"*Dataset:* `{current_run.dataset_version}` | "
                        f"*Avg Summary:* `{current_run.average_summary_score}/5` | "
                        f"*Avg Latency:* `{current_run.average_latency}s`"
                    ),
                }
            ],
        },
    ]

    if comparison.regressions:
        sample_ids = ", ".join(r.test_id for r in comparison.regressions[:8])
        extra = "" if len(comparison.regressions) <= 8 else f" (+{len(comparison.regressions) - 8} more)"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Regressed Case IDs:* `{sample_ids}`{extra}",
                },
            }
        )

    if drift_result is not None and drift_result.drift_status == "slow_drift":
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":snail: *Slow Drift Alert:* {drift_result.drift_message}",
                },
            }
        )

    return {
        "text": f"[{status.upper()}] {current_run.prompt_version}: {comparison.alert_message}",
        "blocks": blocks,
    }


def send_slack_alert(
    current_run: RunEvaluationSummary,
    comparison: RunComparisonResult,
    baseline_run: Optional[RunEvaluationSummary] = None,
    report_path: Optional[Path] = None,
    report_url: Optional[str] = None,
    webhook_url: Optional[str] = None,
    timeout_seconds: float = 10.0,
    drift_result: Optional[RollingDriftResult] = None
) -> bool:
    """Sends the Slack webhook notification if a webhook URL is configured.

    Returns True when posted successfully, False when skipped due to missing URL.
    """
    target_url = (webhook_url or os.getenv(WEBHOOK_ENV_VAR, "")).strip()
    if not target_url:
        return False

    payload = build_slack_payload(
        current_run=current_run,
        comparison=comparison,
        baseline_run=baseline_run,
        report_path=report_path,
        report_url=report_url,
        drift_result=drift_result
    )

    response = requests.post(target_url, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    return True