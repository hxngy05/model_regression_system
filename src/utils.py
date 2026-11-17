import yaml
from pathlib import Path
from src.schemas import PromptConfig

def load_prompt_version(version_filename: str) -> PromptConfig:
    """
    Loads a versioned YAML prompt file from the /prompts directory and validates it against the PromptConfig Pydantic schema.
    """
    # Ensure it looks in the root-level 'prompts' folder regardless of where the script is executed
    root_dir = Path(__file__).resolve().parent.parent
    prompt_path = root_dir/ "prompts" / version_filename

    with open(prompt_path, "r") as f:
        data = yaml.safe_load(f)

    return PromptConfig(**data)