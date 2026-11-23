# src/reporter.py
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader

from src.schemas import RollingDriftResult, RunComparisonResult, RunEvaluationSummary

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES_DIR = ROOT_DIR / "templates"
DEFAULT_REPORTS_DIR = ROOT_DIR / "reports"


def _build_chart_points(recent_runs_oldest_first: list[RunEvaluationSummary]) -> tuple[list[dict], str]:
    """Maps pass rates (0.0 to 1.0) onto an SVG coordinate space (x: 50..670, y: 20..180)."""
    count = len(recent_runs_oldest_first)
    if count == 0:
        return [], ""

    x_start, x_end = 70.0, 650.0
    y_top, y_bottom = 25.0, 175.0
    step_x = (x_end - x_start) / (count - 1) if count > 1 else 0.0

    points: list[dict] = []
    coords: list[str] = []

    for idx, run in enumerate(recent_runs_oldest_first):
        x = round(x_start + idx * step_x, 1)
        clamped_rate = max(0.0, min(1.0, run.pass_rate))
        y = round(y_bottom - clamped_rate * (y_bottom - y_top), 1)
        pct = round(clamped_rate * 100, 1)
        short_label = run.run_id.replace("run_", "")[:13]

        points.append({"x": x, "y": y, "pct": pct, "label": short_label})
        coords.append(f"{x},{y}")

    return points, " ".join(coords)


def generate_html_diff_report(
    current_run: RunEvaluationSummary,
    comparison: RunComparisonResult,
    recent_runs: list[RunEvaluationSummary],
    baseline_run: Optional[RunEvaluationSummary] = None,
    model_name: str = "gpt-4o-mini",
    output_path: Optional[Path] = None,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    drift_result: Optional[RollingDriftResult] = None
) -> Path:
    """Renders the HTML diff report to disk and returns the output file path."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    template = env.get_template("diff_report.html.j2")

    # storage.get_recent_runs returns newest-first; reverse for left-to-right time series
    chronological_runs = list(reversed(recent_runs))
    chart_points, polyline_points = _build_chart_points(chronological_runs)

    html_content = template.render(
        current_run=current_run,
        baseline_run=baseline_run,
        comparison=comparison,
        recent_runs=chronological_runs,
        chart_points=chart_points,
        polyline_points=polyline_points,
        model_name=model_name,
        drift_result=drift_result
    )

    if output_path is None:
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DEFAULT_REPORTS_DIR / f"{current_run.run_id}_diff.html"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(html_content, encoding="utf-8")
    return output_path