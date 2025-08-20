import asyncio, json, pathlib, logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.database import SessionLocal, LogRecord, init_models
from app.elastic_search import bulk_index
from app.kafka_admin import ensure_topics

print("DATABASE_URL =", settings.DATABASE_URL)
print("KAFKA_BOOTSTRAP_SERVERS =", settings.KAFKA_BOOTSTRAP_SERVERS)
print("ELASTICSEARCH_URLS =", settings.ELASTICSEARCH_URLS)

logger = logging.getLogger("processor")
logging.basicConfig(level=logging.INFO)


def _write_failed_ndjson(kind: str, events: List[Dict[str, Any]], why: str):
    out_dir = pathlib.Path("./failed_es")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{kind}-{ts}.ndjson"
    with path.open("a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    logger.error("ES indexing failed: %s. Saved %d events to %s", why, len(events), path)

async def store_db(kind: str, events: List[Dict[str, Any]]):
    async with SessionLocal() as session:
        records = []
        for e in events:
            records.append(LogRecord(
                ts=datetime.fromisoformat(e.get("@timestamp")),
                kind=kind,
                body=e
            ))
        session.add_all(records)
        await session.commit()

async def process_batch(kind: str, batch: List[Dict[str, Any]]):
    if not batch:
        return
    await store_db(kind, batch)
    try:
        res = bulk_index(kind, batch)
        if res and res.get("failed", 0) > 0:
            _write_failed_ndjson(kind, batch, why=f"{res.get('failed')} failed")
    except Exception as ex:
        _write_failed_ndjson(kind, batch, why=str(ex))

async def run_consumer():
    await init_models()

    # Ensure topics exist (ENV-driven; fallback RF=1 nếu cần)
    ensure_topics([
        (settings.KAFKA_TOPIC_INTERACTION, settings.KAFKA_TOPIC_PARTITIONS, settings.KAFKA_TOPIC_RF),
        (settings.KAFKA_TOPIC_NETWORK, settings.KAFKA_TOPIC_PARTITIONS, settings.KAFKA_TOPIC_RF),
    ])

    topics = [settings.KAFKA_TOPIC_INTERACTION, settings.KAFKA_TOPIC_NETWORK]

    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="latest"
    )

    await consumer.start()
    logger.info("Kafka consumer started for topics: %s", topics)
    try:
        buffer: Dict[str, List[Dict[str, Any]]] = {"interaction": [], "network": []}
        loop = asyncio.get_event_loop()
        last_flush = loop.time()
        max_batch = settings.PROCESSOR_MAX_BATCH
        flush_ms = settings.PROCESSOR_FLUSH_MS

        while True:
            msg = await consumer.getone()
            try:
                e = json.loads(msg.value.decode("utf-8"))
            except Exception:
                # bad message → skip, commit and continue
                await consumer.commit()
                continue

            kind = e.get("kind") or ("interaction" if msg.topic == settings.KAFKA_TOPIC_INTERACTION else "network")
            buffer.setdefault(kind, []).append(e)

            now = loop.time()
            need_flush = (now - last_flush) * 1000 >= flush_ms or any(len(v) >= max_batch for v in buffer.values())
            if need_flush:
                for k, events in list(buffer.items()):
                    if not events:
                        continue
                    await process_batch(k, events)
                    buffer[k] = []
                await consumer.commit()
                last_flush = now
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(run_consumer())
