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

def index_name(prefix: str, kind: str) -> str:
    ts = datetime.now(timezone.utc)
    safe = {
        "network": "network",
        "interaction": "interaction",
    }.get(kind, "other")
    return f"{prefix}-{safe}-{ts.strftime('%Y.%m.%d')}"

def make_actions(kind: str, events: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:

    for e in events:
        ts = datetime.fromisoformat(e.get("@timestamp"))
        out = ts.astimezone(timezone.utc) \
            .isoformat(timespec='milliseconds') \
            .replace('+00:00', 'Z')
        idx = index_name(settings.ES_INDEX_PREFIX,kind)
        yield {
            "_op_type": "index",
            "_index": idx,
            "_source": {**e, "@timestamp": out, "kind": kind},
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
