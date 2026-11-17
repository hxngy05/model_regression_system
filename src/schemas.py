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