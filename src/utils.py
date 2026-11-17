import json
import yaml
from pathlib import Path
from src.schemas import GoldenDataset, PromptConfig

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

def load_golden_dataset(dataset_filename: str = "golden_dataset_v1.json") -> GoldenDataset:
    """
    Loads and validates the versioned golden dataset from the /data directory.
    """
    root_dir = Path(__file__).resolve().parent.parent
    dataset_path = root_dir / "data" / dataset_filename
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    dataset = GoldenDataset(**raw_data)
    
    # Guardrail: Ensure all test case IDs are unique
    ids = [tc.id for tc in dataset.test_cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate test case IDs detected in {dataset_filename}")
        
    return dataset