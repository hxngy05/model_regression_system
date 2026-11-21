# src/run_eval.py
import argparse
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from src.alerter import send_slack_alert
from src.differ import compare_evaluation_runs
from src.evaluator import run_evaluation_suite
from src.reporter import generate_html_diff_report
from src.schemas import RunComparisonResult, RunEvaluationSummary, TestCaseEvaluationResult
from src.storage import get_previous_run, get_recent_runs, init_db, save_evaluation_run
from src.utils import load_golden_dataset, load_prompt_version


def build_run_summary(
    prompt_version: str,
    dataset_version: str,
    results: list[TestCaseEvaluationResult],
) -> RunEvaluationSummary:
    """Aggregates per-test-case results into a run-level evaluation summary."""
    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.status == "pass")
    pass_rate = round(passed_cases / total_cases, 4) if total_cases > 0 else 0.0
    average_latency = (
        round(sum(r.latency_seconds for r in results) / total_cases, 3)
        if total_cases > 0
        else 0.0
    )
    average_summary_score = (
        round(sum(r.summary_score for r in results) / total_cases, 2)
        if total_cases > 0
        else 0.0
    )

    now_utc = datetime.now(timezone.utc)
    run_id = f"run_{now_utc.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:6]}"

    return RunEvaluationSummary(
        run_id=run_id,
        timestamp=now_utc.isoformat(),
        prompt_version=prompt_version,
        dataset_version=dataset_version,
        total_cases=total_cases,
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        average_latency=average_latency,
        average_summary_score=average_summary_score,
        results=results,
    )

def build_initial_baseline_comparison(current_run: RunEvaluationSummary) -> RunComparisonResult:
    """Creates a pass-status comparison object when no prior baseline run exists."""
    return RunComparisonResult(
        current_run_id=current_run.run_id,
        baseline_run_id="NONE",
        pass_rate_delta=0.0,
        regressions_count=0,
        improvements_count=0,
        regressions=[],
        improvements=[],
        severity_status="pass",
        alert_message="Initial baseline run recorded; no previous run available for diffing.",
    )

async def execute_pipeline(
    prompt_file: str,
    dataset_file: str,
    max_concurrent: int,
    warning_threshold: float,
    critical_threshold: float,
) -> None:
    # 1. Initialize storage and load Phase 1 + Phase 2 inputs
    init_db()
    prompt_config = load_prompt_version(prompt_file)
    golden_dataset = load_golden_dataset(dataset_file)

    # 2. Run Phase 3 async evaluation suite
    results = await run_evaluation_suite(
        golden_dataset=golden_dataset,
        config=prompt_config,
        max_concurrent=max_concurrent,
    )

    # 3. Build summary and persist to SQLite
    current_summary = build_run_summary(
        prompt_version=prompt_config.version_id,
        dataset_version=golden_dataset.dataset_version,
        results=results,
    )
    save_evaluation_run(current_summary)

    print(f"Saved run: {current_summary.run_id}")
    print(
        f"Pass rate: {current_summary.pass_rate * 100:.1f}% "
        f"({current_summary.passed_cases}/{current_summary.total_cases}) | "
        f"Avg summary score: {current_summary.average_summary_score}/5 | "
        f"Avg latency: {current_summary.average_latency}s"
    )

    # 4. Compare against previous run if one exists
    previous_run = get_previous_run(exclude_run_id=current_summary.run_id)
    if previous_run is None:
        print("No prior run found in SQLite. Recorded this run as the initial baseline.")
        comparison = build_initial_baseline_comparison(current_summary)
    else:
        comparison = compare_evaluation_runs(
            current_run=current_summary,
            baseline_run=previous_run,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
        )
        print("\n--- Diff Against Baseline ---")
        print(json.dumps(comparison.model_dump(), indent=2))

    # 5. Generate HTML diff report with recent run history (last N runs)
    recent_runs = get_recent_runs(limit=7)
    report_path = generate_html_diff_report(
        current_run=current_summary,
        comparison=comparison,
        recent_runs=recent_runs,
        baseline_run=previous_run,
        model_name=prompt_config.model_config.model if hasattr(prompt_config, "model_config") and prompt_config.model_config else "gpt-4o-mini",
    )
    print(f"Generated HTML diff report: {report_path}")

    sent = send_slack_alert(
        current_run=current_summary,
        comparison=comparison,
        baseline_run=previous_run,
        report_path=report_path,
    )
    if sent:
        print("Sent Slack alert.")
    else:
        print("SLACK_WEBHOOK_URL not set; skipped Slack alert.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LLM regression evaluation suite.")
    parser.add_argument("--prompt", default="v1_0_0.yaml", help="Prompt filename in prompts/")
    parser.add_argument(
        "--dataset",
        default="golden_dataset_v1.json",
        help="Dataset filename in data/",
    )
    parser.add_argument("--max-concurrent", type=int, default=5, help="Max concurrent workers")
    parser.add_argument(
        "--warning-threshold",
        type=float,
        default=0.03,
        help="Pass-rate drop threshold for warning (e.g., 0.03 = 3%%)",
    )
    parser.add_argument(
        "--critical-threshold",
        type=float,
        default=0.08,
        help="Pass-rate drop threshold for critical failure (e.g., 0.08 = 8%%)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        execute_pipeline(
            prompt_file=args.prompt,
            dataset_file=args.dataset,
            max_concurrent=args.max_concurrent,
            warning_threshold=args.warning_threshold,
            critical_threshold=args.critical_threshold,
        )
    )