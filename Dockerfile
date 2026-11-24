FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY prompts/ ./prompts/
COPY data/ ./data/
COPY templates/ ./templates/
COPY src/ ./src/

RUN mkdir -p /app/data /app/reports

ENTRYPOINT ["python", "-m", "src.run_eval"]
CMD ["--prompt", "v1_0_0.yaml", "--dataset", "golden_dataset_v1.json"]