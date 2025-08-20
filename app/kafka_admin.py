from typing import List, Tuple, Dict, Any
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, InvalidReplicationFactorError
from app.config import settings

def _admin_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client_id": "logocs-admin",
    }
    # optional security
    if settings.KAFKA_SECURITY_PROTOCOL:
        kw["security_protocol"] = settings.KAFKA_SECURITY_PROTOCOL
    if settings.KAFKA_SASL_MECHANISM:
        kw["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
    if settings.KAFKA_SASL_USERNAME and settings.KAFKA_SASL_PASSWORD:
        kw["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
        kw["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD
    if settings.KAFKA_SSL_CAFILE:
        kw["ssl_cafile"] = settings.KAFKA_SSL_CAFILE
    return kw

def ensure_topics(topics: List[Tuple[str, int, int]]) -> None:
    """
    Ensure Kafka topics exist.
    topics: list of (name, partitions, replication_factor)
    Fallback RF=1 nếu cụm chỉ có 1 broker.
    """
    if not settings.KAFKA_ENABLED or not settings.KAFKA_BOOTSTRAP_SERVERS:
        return
    admin = KafkaAdminClient(**_admin_kwargs())
    try:
        existing = set(admin.list_topics())
        to_create = []
        for name, partitions, rf in topics:
            if name and name not in existing:
                to_create.append(NewTopic(name=name, num_partitions=partitions, replication_factor=rf))
        if to_create:
            try:
                admin.create_topics(new_topics=to_create, validate_only=False)
            except TopicAlreadyExistsError:
                pass
            except InvalidReplicationFactorError:
                # single-broker fallback
                to_create_rf1 = [
                    NewTopic(name=t.topic, num_partitions=t.num_partitions, replication_factor=1)
                    for t in to_create
                ]
                admin.create_topics(new_topics=to_create_rf1, validate_only=False)
    finally:
        admin.close()
