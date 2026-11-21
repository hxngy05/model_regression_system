# src/evaluator.py
import asyncio
import time
from openai import OpenAI
from pydantic import BaseModel, Field

from src.classifier import classify_email
from src.schemas import ClassifierInput, CategoryEnum, TestCaseEvaluationResult, PromptConfig, GoldenTestCase

client = OpenAI()

class JudgeOutput(BaseModel):
    score: int = Field(..., ge=1, le=5, description="Score from 1 to 5 based on semantic accuracy and conciseness.")
    critique: str = Field(..., description="One sentence explanation for the score.")

def evaluate_summary_llm(expected: str, predicted: str) -> tuple[int, str]:
    system_prompt = (
        "You are an objective evaluation judge. Compare the generated summary against the expected ground truth summary. "
        "Rate the generated summary from 1 to 5 based on whether it captures the core meaning accurately and concisely. "
        "1 = completely incorrect or missing gist, 5 = perfectly captures the gist."
    )
    user_prompt = f"Expected Summary: {expected}\nGenerated Summary: {predicted}"
    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=JudgeOutput,
        temperature=0.0
    )
    result = completion.choices[0].message.parsed
    return result.score, result.critique

async def run_single_test(test_case: GoldenTestCase, config: PromptConfig) -> TestCaseEvaluationResult:
    start_time = time.time()
    
    # Run classifier
    input_payload = ClassifierInput(email_text=test_case.input_text)
    # Note: classify_email is synchronous, so we run it in an executor if needed, 
    # or call it directly since OpenAI client handles network IO.
    try:
        prediction = classify_email(input_payload, config)
        latency = time.time() - start_time
        
        pred_cat = prediction.category
        pred_sum = prediction.summary
        
        # Check category match
        cat_match = (pred_cat == test_case.expected_category)
        
        # LLM-as-a-judge for summary
        score, critique = evaluate_summary_llm(test_case.expected_summary_gist, pred_sum)
        
        # Determine pass/fail condition (e.g., category must match and summary score >= 4)
        status = "pass" if (cat_match and score >= 4) else "fail"
        
        # Approximate token usage (can be extracted from completion if desired)
        token_usage = 150 # placeholder or actual usage if returned from client
        
        return TestCaseEvaluationResult(
            test_id=test_case.id,
            input_text=test_case.input_text,
            expected_category=test_case.expected_category,
            predicted_category=pred_cat,
            category_match=cat_match,
            expected_summary=test_case.expected_summary_gist,
            predicted_summary=pred_sum,
            summary_score=score,
            summary_critique=critique,
            latency_seconds=round(latency, 3),
            token_usage=token_usage,
            status=status
        )
    except Exception as e:
        latency = time.time() - start_time
        return TestCaseEvaluationResult(
            test_id=test_case.id,
            input_text=test_case.input_text,
            expected_category=test_case.expected_category,
            predicted_category=CategoryEnum.GENERAL,
            category_match=False,
            expected_summary=test_case.expected_summary_gist,
            predicted_summary=f"ERROR: {str(e)}",
            summary_score=1,
            summary_critique=str(e),
            latency_seconds=round(latency, 3),
            token_usage=0,
            status="fail"
        )

async def run_evaluation_suite(golden_dataset, config: PromptConfig, max_concurrent: int = 5) -> list[TestCaseEvaluationResult]:
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def sem_task(tc):
        async with semaphore:
            return await run_single_test(tc, config)
            
    tasks = [sem_task(tc) for tc in golden_dataset.test_cases]
    results = await asyncio.gather(*tasks)
    return results