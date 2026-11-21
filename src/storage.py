# src/storage.py
import sqlite3
from pathlib import Path
from typing import Optional
from src.schemas import CategoryEnum, RunEvaluationSummary, TestCaseEvaluationResult

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_history.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Creates evaluation run and per-case result tables if they do not exist."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                dataset_version TEXT NOT NULL,
                total_cases INTEGER NOT NULL,
                passed_cases INTEGER NOT NULL,
                pass_rate REAL NOT NULL,
                average_latency REAL NOT NULL,
                average_summary_score REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_case_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                input_text TEXT NOT NULL,
                expected_category TEXT NOT NULL,
                predicted_category TEXT NOT NULL,
                category_match INTEGER NOT NULL,
                expected_summary TEXT NOT NULL,
                predicted_summary TEXT NOT NULL,
                summary_score INTEGER NOT NULL,
                summary_critique TEXT NOT NULL,
                latency_seconds REAL NOT NULL,
                token_usage INTEGER NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES eval_runs(run_id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_eval_case_results_run_id
            ON eval_case_results(run_id);
            """
        )


def save_evaluation_run(summary: RunEvaluationSummary, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Persists a completed evaluation run and all test case results atomically."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO eval_runs (
                run_id, timestamp, prompt_version, dataset_version,
                total_cases, passed_cases, pass_rate,
                average_latency, average_summary_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                summary.run_id,
                summary.timestamp,
                summary.prompt_version,
                summary.dataset_version,
                summary.total_cases,
                summary.passed_cases,
                summary.pass_rate,
                summary.average_latency,
                summary.average_summary_score,
            ),
        )

        case_rows = [
            (
                summary.run_id,
                res.test_id,
                res.input_text,
                res.expected_category.value,
                res.predicted_category.value,
                1 if res.category_match else 0,
                res.expected_summary,
                res.predicted_summary,
                res.summary_score,
                res.summary_critique,
                res.latency_seconds,
                res.token_usage,
                res.status,
            )
            for res in summary.results
        ]

        conn.executemany(
            """
            INSERT INTO eval_case_results (
                run_id, test_id, input_text, expected_category, predicted_category,
                category_match, expected_summary, predicted_summary,
                summary_score, summary_critique, latency_seconds,
                token_usage, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            case_rows,
        )


def load_run_by_id(run_id: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[RunEvaluationSummary]:
    """Loads a full RunEvaluationSummary (including per-case results) by run_id."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        run_row = conn.execute(
            "SELECT * FROM eval_runs WHERE run_id = ?;",
            (run_id,),
        ).fetchone()

        if run_row is None:
            return None

        case_rows = conn.execute(
            "SELECT * FROM eval_case_results WHERE run_id = ? ORDER BY id ASC;",
            (run_id,),
        ).fetchall()

    results = [
        TestCaseEvaluationResult(
            test_id=row["test_id"],
            input_text=row["input_text"],
            expected_category=CategoryEnum(row["expected_category"]),
            predicted_category=CategoryEnum(row["predicted_category"]),
            category_match=bool(row["category_match"]),
            expected_summary=row["expected_summary"],
            predicted_summary=row["predicted_summary"],
            summary_score=row["summary_score"],
            summary_critique=row["summary_critique"],
            latency_seconds=row["latency_seconds"],
            token_usage=row["token_usage"],
            status=row["status"],
        )
        for row in case_rows
    ]

    return RunEvaluationSummary(
        run_id=run_row["run_id"],
        timestamp=run_row["timestamp"],
        prompt_version=run_row["prompt_version"],
        dataset_version=run_row["dataset_version"],
        total_cases=run_row["total_cases"],
        passed_cases=run_row["passed_cases"],
        pass_rate=run_row["pass_rate"],
        average_latency=run_row["average_latency"],
        average_summary_score=run_row["average_summary_score"],
        results=results,
    )


def get_previous_run(
    exclude_run_id: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[RunEvaluationSummary]:
    """Fetches the most recent prior run to use as a baseline comparison."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        if exclude_run_id:
            row = conn.execute(
                """
                SELECT run_id FROM eval_runs
                WHERE run_id != ?
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1;
                """,
                (exclude_run_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT run_id FROM eval_runs
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1;
                """
            ).fetchone()

    if row is None:
        return None
    return load_run_by_id(row["run_id"], db_path=db_path)


def get_recent_runs(limit: int = 7, db_path: Path = DEFAULT_DB_PATH) -> list[RunEvaluationSummary]:
    """Fetches the last N runs (useful for trend charts and rolling drift detection)."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT run_id FROM eval_runs
            ORDER BY timestamp DESC, rowid DESC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()

    runs: list[RunEvaluationSummary] = []
    for row in rows:
        loaded = load_run_by_id(row["run_id"], db_path=db_path)
        if loaded is not None:
            runs.append(loaded)
    return runs