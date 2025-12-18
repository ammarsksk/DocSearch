from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_user: str = "docsearch"
    postgres_password: str = "docsearch"
    postgres_db: str = "docsearch"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key_id: str = "minio"
    s3_secret_access_key: str = "minio123"
    s3_bucket: str = "docsearch-documents"
    s3_region: str = "us-east-1"

    opensearch_host: str = "opensearch"
    opensearch_port: int = 9200
    opensearch_index: str = "chunks_v1"

    embedding_model_name: str = "text-embedding-3-small"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

