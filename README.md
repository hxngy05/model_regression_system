# Model Regression System

An automated LLM regression testing and evaluation pipeline built with Python (`asyncio`), Pydantic, SQLite, Jinja2, and GitHub Actions. It evaluates prompt and dataset revisions against human-verified golden datasets, tracks run history locally in SQLite, detects regressions and 7-run rolling drift, generates HTML diff reports, and sends Slack webhook alerts.

## Project Structure

```text
model_regression_system/
├── .github/
│   └── workflows/
│       └── eval.yml              # Automated CI/CD evaluation workflow
├── data/
│   ├── golden_dataset_v1.json    # Human-verified golden dataset
│   └── eval_history.db           # Local SQLite run history (git-ignored)
├── prompts/
│   └── v1_0_0.yaml               # Versioned prompt configurations
├── reports/                      # Generated HTML diff reports (git-ignored)
├── src/
│   ├── __init__.py
│   ├── schemas.py                # Pydantic models for runs, diffs, and drift
│   ├── classifier.py             # Category classification logic
│   ├── utils.py                  # Prompt and golden dataset loaders
│   ├── evaluator.py              # Async runner + LLM-as-a-judge summary scoring
│   ├── differ.py                 # Run-to-run baseline diffing & severity logic
│   ├── storage.py                # SQLite persistence & history queries
│   ├── drift.py                  # 7-run rolling drift detection
│   ├── reporter.py               # Jinja2 HTML diff report & trend chart builder
│   ├── alerter.py                # Slack Block Kit webhook notifications
│   └── run_eval.py               # End-to-end CLI orchestration entry point
├── templates/
│   └── diff_report.html.j2       # HTML report template
├── .dockerignore
├── Dockerfile
├── requirements.txt
└── README.md
```

## Setup & Local Execution

### 1. Create a Virtual Environment and Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key"
export SLACK_WEBHOOK_URL="[https://hooks.slack.com/services/](https://hooks.slack.com/services/)..."  # Optional
```

### 3. Run the Evaluation Suite

```bash
python -m src.run_eval --prompt v1_0_0.yaml --dataset golden_dataset_v1.json
```

Useful CLI options:
* `--max-concurrent`: Maximum concurrent test case workers (default: `5`).
* `--warning-threshold`: Pass-rate drop threshold for `warn` status (default: `0.03` = `3.0%`).
* `--critical-threshold`: Pass-rate drop threshold for `fail` status (default: `0.08` = `8.0%`).
* `--drift-threshold`: Pass-rate drop threshold from the first run in a 7-run window for `slow_drift` (default: `0.05` = `5.0%`).
* `--fail-on-critical`: Exit with status code `1` when run-to-run `severity_status` is `"fail"`.

## Evaluation, Diffing & Drift Strategy

* **Golden Dataset & LLM-as-a-Judge:** Validates classification accuracy alongside rubric-scored summaries and per-case latency/token metrics.
* **Run-to-Run Diffing:** Compares the current run against the immediately preceding baseline run in SQLite to surface individual regressions (`pass` → `fail`), improvements (`fail` → `pass`), and `pass` / `warn` / `fail` status.
* **7-Run Rolling Drift Detection:** Waits until 7 runs exist in SQLite, then compares the latest run's pass rate against the first run in the 7-run window. If pass rate drops by at least `drift-threshold` (`>= 5.0%` by default), it surfaces a `slow_drift` warning across the CLI, HTML report, and Slack alert without altering the run-to-run `severity_status`.

## Reports & Slack Alerts

* **HTML Diff Report:** Saved to `reports/<run_id>_diff.html` with run metadata, baseline comparison scorecard, side-by-side regressed test cases, slow drift banner (when triggered), and a pass-rate trend chart.
* **Slack Webhook Alerts:** Posts structured Block Kit summaries with status, pass-rate shift, regression/improvement counts, regressed test IDs, report location, and slow drift warnings when `SLACK_WEBHOOK_URL` is set.

## Docker Usage

Build the container image:

```bash
docker build -t model-regression-system:latest .
```

Run with mounted `data/` and `reports/` directories so SQLite history and HTML reports persist on your host:

```bash
docker run --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/reports:/app/reports" \
  model-regression-system:latest \
  --prompt v1_0_0.yaml \
  --dataset golden_dataset_v1.json
```

## GitHub Actions CI/CD

The workflow in `.github/workflows/eval.yml` runs on pull requests and pushes to `main` touching `prompts/**`, `data/**`, `src/**`, or `templates/**` (and supports manual `workflow_dispatch` runs). It restores `data/eval_history.db` via cache, runs `python -m src.run_eval --fail-on-critical`, and uploads generated HTML reports as workflow artifacts.

Configure `OPENAI_API_KEY` (required) and `SLACK_WEBHOOK_URL` (optional) under **Settings → Secrets and variables → Actions** in your GitHub repository.