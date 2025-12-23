FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
      fastapi uvicorn[standard] \
      pydantic pydantic-settings \
      sqlalchemy asyncpg alembic psycopg2-binary \
      boto3 opensearch-py python-multipart httpx PyPDF2 \
      sentence-transformers pgvector

COPY app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
