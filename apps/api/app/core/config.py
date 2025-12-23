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

    # Local embeddings / LLM
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 64

    local_llm_base_url: str = "http://localhost:11434"
    # Default to a small widely-available Ollama model
    local_llm_model: str = "phi3:mini"

    # Cross-encoder reranker
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"

    # Chunking (character-based defaults)
    parent_chunk_chars: int = 4000
    parent_overlap_chars: int = 200
    child_chunk_chars: int = 1000
    child_overlap_chars: int = 100

    # Retrieval tuning
    retrieve_k_keyword: int = 50
    retrieve_k_vector: int = 50
    retrieve_k_merge: int = 80
    rerank_top_n: int = 15
    max_parent_chunks_for_llm: int = 10
    max_parent_chunk_chars_for_llm: int = 1500

    # Query expansion (HyDE)
    hyde_enabled: bool = False

    # Debugging
    debug_prompts: bool = False
    debug_max_chars: int = 12000

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
