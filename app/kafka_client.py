import json
import ssl
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from app.config import settings

_producer: Optional[AIOKafkaProducer] = None
_started: bool = False

def _ssl_context() -> Optional[ssl.SSLContext]:
    if not settings.KAFKA_SSL_CAFILE:
        return None
    ctx = ssl.create_default_context(cafile=settings.KAFKA_SSL_CAFILE)
    return ctx

async def start_kafka():
    global _producer, _started
    if _started or not settings.KAFKA_ENABLED:
        return
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        return
    kwargs = dict(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    if settings.KAFKA_SECURITY_PROTOCOL:
        kwargs["security_protocol"] = settings.KAFKA_SECURITY_PROTOCOL
    if settings.KAFKA_SASL_MECHANISM:
        kwargs["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
    if settings.KAFKA_SASL_USERNAME and settings.KAFKA_SASL_PASSWORD:
        kwargs["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
        kwargs["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD
    ctx = _ssl_context()
    if ctx:
        kwargs["ssl_context"] = ctx

    _producer = AIOKafkaProducer(**kwargs)
    await _producer.start()
    _started = True

async def stop_kafka():
    global _producer, _started
    if _producer is not None:
        await _producer.stop()
    _producer = None
    _started = False

def is_ready() -> bool:
    return _started and _producer is not None


def normalize_ts(ts: int | float | str | datetime) -> str:
    """Convert timestamp (ms, s, iso string, datetime) về ISO8601 UTC string"""
    from datetime import datetime, timezone

    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).isoformat()
    if isinstance(ts, (int, float)):
        # nếu số lớn hơn 10^12 thì là milliseconds
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return None
    return None

async def send_events(topic: str, kind: str, events: List[Dict[str, Any]]):
    if not settings.KAFKA_ENABLED or not is_ready() or not events:
        return False
    # produce one message per event
    for e in events:
        base_ts = e.get("timestamp")
        ts = normalize_ts(base_ts)
        payload = {**e, "kind": kind, "@timestamp": ts}
        try:
            await _producer.send_and_wait(topic, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except Exception:
            # continue other events; the endpoint already persists to DB
            continue
    return True
