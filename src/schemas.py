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