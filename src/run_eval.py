# src/run_eval.py
import argparse
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from src.differ import compare_evaluation_runs
from src.evaluator import run_evaluation_suite
from src.schemas import RunEvaluationSummary, TestCaseEvaluationResult
from src.storage import get_previous_run, init_db, save_evaluation_run
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
        return

    comparison = compare_evaluation_runs(
        current_run=current_summary,
        baseline_run=previous_run,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
    )
    print("\n--- Diff Against Baseline ---")
    print(json.dumps(comparison.model_dump(), indent=2))


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