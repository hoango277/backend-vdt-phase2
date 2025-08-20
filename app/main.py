from fastapi import FastAPI, BackgroundTasks, HTTPException
from typing import List, Dict, Any
import logging

from app.config import settings
from app.database import init_models
from app.models.interaction import InteractionEvent
from app.models.network import NetworkEvent
from app.schemas import HealthStatus
from app.elastic_search import get_es
from app.kafka_client import start_kafka, stop_kafka, send_events, is_ready as kafka_ready
from app.kafka_admin import ensure_topics

app = FastAPI(title="Log OCS Backend - Ingest", version="1.1.0")
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("logocs")

@app.on_event("startup")
async def on_startup():
    await init_models()
    # Auto-create topics theo ENV (fallback RF=1 nếu thiếu broker)
    ensure_topics([
        (settings.KAFKA_TOPIC_INTERACTION, settings.KAFKA_TOPIC_PARTITIONS, settings.KAFKA_TOPIC_RF),
        (settings.KAFKA_TOPIC_NETWORK, settings.KAFKA_TOPIC_PARTITIONS, settings.KAFKA_TOPIC_RF),
    ])
    await start_kafka()
    logger.info("Startup complete")

@app.on_event("shutdown")
async def on_shutdown():
    await stop_kafka()

def _to_json_list(events) -> List[Dict[str, Any]]:
    return [e.model_dump(mode="json") for e in events]

@app.post("/v1/logs/interaction")
async def ingest_interaction(events: List[InteractionEvent], background: BackgroundTasks):
    events_dict = _to_json_list(events)
    if not events_dict:
        raise HTTPException(status_code=400, detail="Empty batch")
    background.add_task(send_events, settings.KAFKA_TOPIC_INTERACTION, "interaction", events_dict)
    return {"produced": len(events_dict)}

@app.post("/v1/logs/network")
async def ingest_network(events: List[NetworkEvent], background: BackgroundTasks):
    events_dict = _to_json_list(events)
    if not events_dict:
        raise HTTPException(status_code=400, detail="Empty batch")
    background.add_task(send_events, settings.KAFKA_TOPIC_NETWORK, "network", events_dict)
    return {"produced": len(events_dict)}

@app.get("/health", response_model=HealthStatus)
async def health():
    # DB check: ingest không ghi DB; processor mới ghi
    db_ok = True
    details: Dict[str, Any] = {}

    # ES check (thông tin)
    es_ok = True
    try:
        es = get_es()
        if es:
            es.info()
        else:
            es_ok = False
            details["es"] = "not_configured"
    except Exception as ex:
        es_ok = False
        details["es_error"] = str(ex)

    details["kafka"] = ("ready" if kafka_ready() else ("not_configured" if not settings.KAFKA_ENABLED else "not_ready"))
    return HealthStatus(db_ok=db_ok, es_ok=es_ok, details=details)
