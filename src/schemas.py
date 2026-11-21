# src/schemas.py
from enum import Enum
from pydantic import BaseModel, Field

class CategoryEnum(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"

class ClassifierInput(BaseModel):
    email_text: str = Field(..., description="The raw customer support email text.")

class ClassifierOutput(BaseModel):
    category: CategoryEnum = Field(..., description="The classified category of the email.")
    summary: str = Field(..., description="A one-sentence summary of the email content.")

class PromptConfig(BaseModel):
    version_id: str
    timestamp: str
    description: str | None = None
    author: str | None = None
    system_prompt: str
    few_shot_examples: list[dict] = []

class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class GoldenTestCase(BaseModel):
    id: str = Field(..., description="Stable unique identifier, e.g., TC-001")
    input_text: str = Field(..., description="Raw customer support email")
    expected_category: CategoryEnum
    expected_summary_gist: str = Field(..., description="Human-verified ideal one-sentence summary")
    expected_difficulty: DifficultyEnum
    notes: str = Field(..., description="Context explaining why this test case matters")

class GoldenDataset(BaseModel):
    dataset_version: str
    created_at: str
    description: str | None = None
    test_cases: list[GoldenTestCase]

class TestCaseEvaluationResult(BaseModel):
    test_id: str
    input_text: str
    expected_category: CategoryEnum
    predicted_category: CategoryEnum
    category_match: bool
    expected_summary: str
    predicted_summary: str
    summary_score: int = Field(..., ge=1, le=5, description="LLM-as-a-judge score from 1-5")
    summary_critique: str
    latency_seconds: float
    token_usage: int
    status: str = Field(..., description="'pass' or 'fail'")

class RunEvaluationSummary(BaseModel):
    run_id: str
    timestamp: str
    prompt_version: str
    dataset_version: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    average_latency: float
    average_summary_score: float
    results: list[TestCaseEvaluationResult]

class FlippedTestCase(BaseModel):
    test_id: str
    input_text: str
    expected_category: CategoryEnum
    old_predicted_category: CategoryEnum
    new_predicted_category: CategoryEnum
    old_status: str
    new_status: str
    old_summary: str
    new_summary: str
    summary_score_delta: int

class RunComparisonResult(BaseModel):
    current_run_id: str
    baseline_run_id: str
    pass_rate_delta: float = Field(..., description="Current pass rate minus baseline pass rate (e.g., +0.05 or -0.03)")
    regressions_count: int
    improvements_count: int
    regressions: list[FlippedTestCase]
    improvements: list[FlippedTestCase]
    severity_status: str = Field(..., description="'pass', 'warn', 'fail'")
    alert_message: str