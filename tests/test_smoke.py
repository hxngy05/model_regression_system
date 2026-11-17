# tests/test_smoke.py
from src.schemas import ClassifierInput
from src.classifier import classify_email
from src.utils import load_prompt_version

def test_classifier_smoke():
    # Load version 1.0.0 of your prompt
    config = load_prompt_version("v1_0_0.yaml")
    
    # Create a sample input
    test_input = ClassifierInput(
        email_text="Hi team, I was charged twice for my subscription this month. Can you issue a refund?"
    )
    
    # Run classifier
    result = classify_email(test_input, config)
    
    print("Classification Result:")
    print(f"Category: {result.category}")
    print(f"Summary: {result.summary}")
    
    assert result.category in ["billing", "technical", "account", "general"]

if __name__ == "__main__":
    test_classifier_smoke()