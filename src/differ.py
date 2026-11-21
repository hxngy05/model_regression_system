from src.schemas import RunEvaluationSummary, RunComparisonResult, FlippedTestCase

def compare_evaluation_runs(
    current_run: RunEvaluationSummary,
    baseline_run: RunEvaluationSummary,
    warning_threshold: float = 0.03, # 3% drop triggers warning
    critical_threshold: float = 0.08 # 8% drop triggers critical failure
) -> RunComparisonResult:
    """
    Comapres the current evaluation run against a baseline run,
    identifying regressions, improvements, and applying severity thresholds.
    """
    # 1. Map baseline results by test_id for O(1) lookup
    baseline_map = {res.test_id.strip(): res for res in baseline_run.results}

    pass_rate_delta = round(current_run.pass_rate - baseline_run.pass_rate, 4)

    regressions: list[FlippedTestCase] = []
    improvements: list[FlippedTestCase] = []

    for current_res in current_run.results:
        test_id = current_res.test_id
        if test_id not in baseline_map:
            continue # Skip new test cases not present in baseline

        baseline_res = baseline_map[test_id]
        old_status = (baseline_res.status.value if hasattr(baseline_res.status, "value") else str(baseline_res.status)).strip().lower()
        new_status = (current_res.status.value if hasattr(current_res.status, "value") else str(current_res.status)).strip().lower()

        # Check for Regression: Pass -> Fail
        if old_status == "pass" and new_status == "fail":
            regressions.append(
                FlippedTestCase(
                    test_id=test_id,
                    input_text=current_res.input_text,
                    expected_category=current_res.expected_category,
                    old_predicted_category=baseline_res.predicted_category,
                    new_predicted_category=current_res.predicted_category,
                    old_status=old_status,
                    new_status=new_status,
                    old_summary=baseline_res.predicted_summary,
                    new_summary=current_res.predicted_summary,
                    summary_score_delta=current_res.summary_score - baseline_res.summary_score
                )
            )

        # Check for Improvement: Fail -> Pass
        elif old_status == "fail" and new_status == "pass":
            improvements.append(
                FlippedTestCase(
                    test_id=test_id,
                    input_text=current_res.input_text,
                    expected_category=current_res.expected_category,
                    old_predicted_category=baseline_res.predicted_category,
                    new_predicted_category=current_res.predicted_category,
                    old_status=old_status,
                    new_status=new_status,
                    old_summary=baseline_res.predicted_summary,
                    new_summary=current_res.predicted_summary,
                    summary_score_delta=current_res.summary_score - baseline_res.summary_score
                )
            )

    # 2. Determine severity status based on pass rate delta thresholds
    severity_status = "pass"
    alert_message = f"Evaluation passed successfully with {len(improvements)} improvements and 0 critical regressions."

    # Note: A negative delta means pass rate dropped
    drop_amount = max(0.0, -pass_rate_delta)

    if drop_amount >= critical_threshold:
        severity_status = "fail"
        alert_message = (
            f"CRITICAL REGRESSION: Pass rate dropped by {drop_amount * 100:.1f} pp "
            f"(from {baseline_run.pass_rate * 100:.1f}% to {current_run.pass_rate * 100:.1f}%, "
            f"exceeding {critical_threshold * 100:.1f} pp threshold). "
            f"{len(regressions)} regression(s), {len(improvements)} improvement(s)."
        )
    elif drop_amount >= warning_threshold:
        severity_status = "warn"
        alert_message = (
            f"WARNING: Pass rate dropped by {drop_amount * 100:.1f} pp "
            f"(from {baseline_run.pass_rate * 100:.1f}% to {current_run.pass_rate * 100:.1f}%, "
            f"exceeding {warning_threshold * 100:.1f} pp threshold). "
            f"{len(regressions)} regression(s), {len(improvements)} improvement(s)."
        )
    else:
        severity_status = "pass"
        direction = "increased" if pass_rate_delta > 0 else ("unchanged" if pass_rate_delta == 0 else "changed")
        alert_message = (
            f"PASS: Pass rate {direction} ({pass_rate_delta * 100:+.1f} pp, "
            f"{baseline_run.pass_rate * 100:.1f}% → {current_run.pass_rate * 100:.1f}%). "
            f"{len(regressions)} regression(s), {len(improvements)} improvement(s)."
        )

    return RunComparisonResult(
        current_run_id=current_run.run_id,
        baseline_run_id=baseline_run.run_id,
        pass_rate_delta=pass_rate_delta,
        regressions_count=len(regressions),
        improvements_count=len(improvements),
        regressions=regressions,
        improvements=improvements,
        severity_status=severity_status,
        alert_message=alert_message
    )
