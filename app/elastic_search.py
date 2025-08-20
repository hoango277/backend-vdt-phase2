from typing import Iterable, Dict, Any, List, Optional
from datetime import datetime, timezone
from elasticsearch import Elasticsearch, helpers
from app.config import settings
import pathlib

_es_client: Optional[Elasticsearch] = None

def get_es() -> Optional[Elasticsearch]:
    global _es_client
    if _es_client is not None:
        return _es_client

    if not settings.ELASTICSEARCH_URLS:
        return None  # ES not configured

    ca = settings.ELASTIC_CA_CERT
    ca_kw = {}
    if ca:
        p = pathlib.Path(ca)
        if p.exists():
            ca_kw["ca_certs"] = str(p)
    _es_client = Elasticsearch(
        settings.ELASTICSEARCH_URLS,
        basic_auth=(settings.ELASTIC_USERNAME, settings.ELASTIC_PASSWORD) if settings.ELASTIC_USERNAME else None,
        verify_certs=True if ca else False,
        **ca_kw
    )
    return _es_client

def index_name(prefix: str, ts: Optional[datetime]) -> str:
    if not ts:
        ts = datetime.now(timezone.utc)
    return f"{prefix}-{ts.strftime('%Y.%m.%d')}"

def make_actions(kind: str, events: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for e in events:
        ts = e.get("ts")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts = None
        idx = index_name(settings.ES_INDEX_PREFIX, ts)
        yield {
            "_op_type": "index",
            "_index": idx,
            "_source": {**e, "@timestamp": (ts.isoformat() if ts else None), "kind": kind},
        }

def bulk_index(kind: str, events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    es = get_es()
    if not es:
        return None
    actions = list(make_actions(kind, events))
    if not actions:
        return None
    success, fail = helpers.bulk(es, actions, raise_on_error=False)
    return {"success": success, "failed": len(fail), "errors": fail}
