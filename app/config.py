import os
from typing import List, Optional

def _split_env_list(v: Optional[str]) -> List[str]:
    if not v:
        return []
    return [s.strip() for s in v.split(",") if s.strip()]

class Settings:
    # --- Database ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        # mặc định dùng service name trong docker-compose
        "postgresql+asyncpg://postgres:postgres@localhost:5432/logocs"
    )

    # --- Elasticsearch ---
    ELASTICSEARCH_URLS: List[str] = _split_env_list(os.getenv("ELASTICSEARCH_URLS", "http://localhost:9200"))
    ELASTIC_USERNAME: Optional[str] = os.getenv("ELASTIC_USERNAME")
    ELASTIC_PASSWORD: Optional[str] = os.getenv("ELASTIC_PASSWORD")
    ELASTIC_CA_CERT: Optional[str] = os.getenv("ELASTIC_CA_CERT")
    ES_INDEX_PREFIX: str = os.getenv("ES_INDEX_PREFIX", "logocs")

    # --- App ---
    RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "90"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    UVICORN_HOST: str = os.getenv("UVICORN_HOST", "0.0.0.0")
    UVICORN_PORT: int = int(os.getenv("UVICORN_PORT", "8000"))

    # --- Kafka (Producer & Consumer) ---
    KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "false").lower() in ("1","true","yes","on")
    # mặc định hợp với docker-compose (service 'kafka')
    KAFKA_BOOTSTRAP_SERVERS: List[str] = _split_env_list(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    KAFKA_TOPIC_INTERACTION: str = os.getenv("KAFKA_TOPIC_INTERACTION", "logocs-interaction")
    KAFKA_TOPIC_NETWORK: str = os.getenv("KAFKA_TOPIC_NETWORK", "logocs-network")
    KAFKA_SECURITY_PROTOCOL: str = os.getenv("KAFKA_SECURITY_PROTOCOL", "")  # PLAINTEXT | SSL | SASL_PLAINTEXT | SASL_SSL
    KAFKA_SASL_MECHANISM: str = os.getenv("KAFKA_SASL_MECHANISM", "")        # PLAIN | SCRAM-SHA-256 | SCRAM-SHA-512
    KAFKA_SASL_USERNAME: str = os.getenv("KAFKA_SASL_USERNAME", "")
    KAFKA_SASL_PASSWORD: str = os.getenv("KAFKA_SASL_PASSWORD", "")
    KAFKA_SSL_CAFILE: str = os.getenv("KAFKA_SSL_CAFILE", "")

    # --- Kafka topics layout (ENV-driven) ---
    KAFKA_TOPIC_PARTITIONS: int = int(os.getenv("KAFKA_TOPIC_PARTITIONS", "3"))
    # single-broker dev => RF=1
    KAFKA_TOPIC_RF: int = int(os.getenv("KAFKA_TOPIC_RF", "1"))

    # --- Processor ---
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "logocs-processor")
    PROCESSOR_MAX_BATCH: int = int(os.getenv("PROCESSOR_MAX_BATCH", "500"))
    PROCESSOR_FLUSH_MS: int = int(os.getenv("PROCESSOR_FLUSH_MS", "2000"))

settings = Settings()
