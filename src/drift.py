# src/drift.py
from src.schemas import RollingDriftResult, RunEvaluationSummary


def detect_rolling_drift(
    recent_runs_newest_first: list[RunEvaluationSummary],
    window_size: int = 7,
    drift_threshold: float = 0.05,
) -> RollingDriftResult:
    """Evaluates slow drift across a full 7-run window relative to the first run in the window.

    Expects `recent_runs_newest_first` in descending order (as returned by `get_recent_runs`),
    reversing it internally so index 0 is the first run in the window and index -1 is latest.
    """
    window = list(reversed(recent_runs_newest_first[:window_size]))
    runs_available = len(window)

    if runs_available < window_size:
        return RollingDriftResult(
            window_size_required=window_size,
            runs_available=runs_available,
            drift_threshold=drift_threshold,
            drift_status="insufficient_data",
            drift_message=(
                f"Rolling drift check requires {window_size} runs in history "
                f"({runs_available}/{window_size} available)."
            ),
        )

    first_run = window[0]
    latest_run = window[-1]
    delta_from_start = round(latest_run.pass_rate - first_run.pass_rate, 4)
    drop_from_start = max(0.0, -delta_from_start)

    if drop_from_start >= drift_threshold:
        drift_status = "slow_drift"
        drift_message = (
            f"SLOW DRIFT WARNING: Pass rate is {latest_run.pass_rate * 100:.1f}% vs. "
            f"{first_run.pass_rate * 100:.1f}% on first run in 7-run window "
            f"({delta_from_start * 100:+.1f} pp, >= {drift_threshold * 100:.1f} pp drop threshold; "
            f"window {first_run.run_id} → {latest_run.run_id})."
        )
    else:
        drift_status = "none"
        drift_message = (
            f"No slow drift detected ({delta_from_start * 100:+.1f} pp vs. first run in 7-run window, "
            f"{first_run.pass_rate * 100:.1f}% → {latest_run.pass_rate * 100:.1f}%)."
        )

    return RollingDriftResult(
        window_size_required=window_size,
        runs_available=runs_available,
        window_start_run_id=first_run.run_id,
        window_end_run_id=latest_run.run_id,
        window_start_pass_rate=first_run.pass_rate,
        latest_pass_rate=latest_run.pass_rate,
        pass_rate_delta_from_start=delta_from_start,
        drift_threshold=drift_threshold,
        drift_status=drift_status,
        drift_message=drift_message,
    )