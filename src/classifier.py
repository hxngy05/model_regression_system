from openai import OpenAI
from src.schemas import ClassifierInput, ClassifierOutput, PromptConfig

client = OpenAI()

def classify_email(email_input: ClassifierInput, config: PromptConfig) -> ClassifierOutput:
    """
    Classifies a customer support email using a configurable prompt and structured outputs.
    """
    # 1. Build message list from system prompt and versioned few-shot examples
    messages = [{"role": "system", "content": config.system_prompt}]

    for ex in config.few_shot_examples:
        messages.append({"role": "user", "content": ex["input"]})
        # Provide the expected output as a strict JSON string matching the schema structure
        messages.append({
            "role": "assistant",
            "content": f'{{"category": "{ex["category"]}", "summary": "{ex["summary"]}"}}'
        })

    # 2. Append the actual target email input
    messages.append({"role": "user", "content": email_input.email_text})

    # 3. Call OpenAI with Structured Outputs for robust, parse-safe responses
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=messages,
        response_format=ClassifierOutput,
        temperature=0.0
    )

    return completion.choices[0].message.parsed