from typing import Iterable, Dict, Any, List, Optional
from datetime import datetime, timezone
from elasticsearch import Elasticsearch, helpers
from app.config import settings
import pathlib
import urllib.parse

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
# ===== Noise filters =====
STATIC_EXTS = {
    ".css", ".js", ".mjs", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".svg",
    ".ttf", ".otf", ".woff", ".woff2",
    ".mp4", ".mp3", ".wav", ".webm"
}
STATIC_TYPES = {"image", "stylesheet", "font", "media"}
STATIC_PATH_HINTS = ("/static/", "/assets/", "/images/", "/img/", "/fonts/")

def _url_path(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        u = urllib.parse.urlparse(url)
        return u.path.lower()
    except Exception:
        return url.lower()

def _has_static_ext(path: str) -> bool:
    # pathlib để lấy suffix (".css", ".js", ...)
    try:
        return pathlib.PurePosixPath(path).suffix.lower() in STATIC_EXTS
    except Exception:
        return False

def should_keep_network(ev: Dict[str, Any]) -> bool:
    method = (_get(ev, "request.method") or "GET").upper()
    url = _get(ev, "request.url") or ""
    rtype = (_get(ev, "request.type") or "").lower()
    code = _get(ev, "response.statusCode")
    from_cache = _get(ev, "response.fromCache")
    path = _url_path(url)

    # Giữ luôn các call "có ý nghĩa" (thao tác) theo method
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True

    # Nếu là lỗi hoặc mã khác 2xx/3xx thì giữ để phân tích
    try:
        code_int = int(code) if code is not None else None
    except Exception:
        code_int = None
    if code_int is not None and (code_int >= 400 or code_int == 0):
        return True  # ví dụ ERR_CACHE_MISS, 4xx/5xx

    # Các asset tĩnh: loại bỏ
    is_static = (
        rtype in STATIC_TYPES
        or _has_static_ext(path)
        or any(h in path for h in STATIC_PATH_HINTS)
    )
    if is_static:
        # Nếu là asset tĩnh & response từ cache → bỏ
        if from_cache is True:
            return False
        # Asset tĩnh 2xx/3xx cũng bỏ (giảm nhiễu)
        if code_int is None or (200 <= code_int < 400):
            return False

    # GET API “có ý nghĩa”
    if path.startswith("/server/") or path.startswith("/api/"):
        return True

    # Điều hướng khung chính tới các page quan trọng thì giữ
    if path in ("/login", "/portal") or path.startswith("/account") or path.startswith("/dashboard"):
        return True

    # Mặc định: giữ nếu không rõ là asset
    return not is_static

def should_keep_interaction(ev: Dict[str, Any]) -> bool:
    # Chỉ giữ click / input (như bạn đã chuẩn hoá)
    source = (ev.get("source") or "").lower()
    if source and source not in {"click", "input"}:
        return False

    # Nếu không có source: giữ nếu có tín hiệu thao tác
    has_dom = bool(_get(ev, "domInfo.tagName"))
    has_value = _get(ev, "domInfo.value") is not None or _get(ev, "inputValue") is not None
    has_coords = _get(ev, "eventData.coordinates.x") is not None and _get(ev, "eventData.coordinates.y") is not None
    return source in {"click", "input"} or has_dom or has_value or has_coords

def should_keep(kind: str, ev: Dict[str, Any]) -> bool:
    k = (kind or ev.get("kind") or "").lower()
    if k == "network":
        return should_keep_network(ev)
    if k == "interaction":
        return should_keep_interaction(ev)
    # Mặc định: giữ
    return True


# ===== Helpers (không rút gọn) =====
def _get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for k in path.split('.'):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _path_or_url(ev: Dict[str, Any]) -> Optional[str]:
    """Prefer full pageContext.url; fallback to (domain + path) if needed."""
    url = _get(ev, "pageContext.url")
    if url:
        return url
    domain = _get(ev, "pageContext.domain")
    path = _get(ev, "pageContext.path")
    if domain and path:
        return f"http://{domain}{path}"
    return domain or path

def _fmt_kv(name: str, value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return f"{name}='{value}'"
    return f"{name}={value}"

def _fmt_bool(name: str, value: Optional[bool]) -> Optional[str]:
    if value is None:
        return None
    return f"{name}={value}"

def _fmt_xy_raw(x: Optional[float], y: Optional[float]) -> Optional[str]:
    if x is None or y is None:
        return None
    return f"(x={x}, y={y})"

def _fmt_position(pos: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(pos, dict):
        return None
    xs = []
    for k in ["x", "y", "width", "height"]:
        if k in pos and pos[k] is not None:
            xs.append(f"{k}={pos[k]}")
    return f"position({', '.join(xs)})" if xs else None

def _join(parts: List[Optional[str]], sep: str = ", ") -> str:
    return sep.join([p for p in parts if p])

# ===== Summarizers (English, natural, full fields) =====
def summarize_interaction(ev: Dict[str, Any]) -> str:
    user = _get(ev, "user.username") or ev.get("user") or "unknown"
    action = (ev.get("source") or "").lower() or "interaction"

    # DOM element & attributes (full, not truncated)
    tag      = _get(ev, "domInfo.tagName")
    el_id    = _get(ev, "domInfo.id")
    cls      = _get(ev, "domInfo.className")
    dtype    = _get(ev, "domInfo.type")
    name     = _get(ev, "domInfo.name")
    value    = _get(ev, "domInfo.value")
    text     = _get(ev, "domInfo.textContent")
    placeholder = _get(ev, "domInfo.placeholder")
    href     = _get(ev, "domInfo.href")
    pos_str  = _fmt_position(_get(ev, "domInfo.position"))
    disabled = _get(ev, "domInfo.disabled")
    readonly = _get(ev, "domInfo.readonly")
    checked  = _get(ev, "domInfo.checked")
    required = _get(ev, "domInfo.required")
    visible  = _get(ev, "domInfo.visible")

    parent_tag  = _get(ev, "domInfo.parent.tagName")
    parent_id   = _get(ev, "domInfo.parent.id")
    parent_cls  = _get(ev, "domInfo.parent.className")

    form_action = _get(ev, "domInfo.form.action")
    form_id     = _get(ev, "domInfo.form.id")
    form_method = _get(ev, "domInfo.form.method")

    node_id = _get(ev, "eventData.nodeId")
    cx = _get(ev, "eventData.coordinates.x")
    cy = _get(ev, "eventData.coordinates.y")
    coords = _fmt_xy_raw(cx, cy)

    page_url  = _path_or_url(ev)
    page_path = _get(ev, "pageContext.path")
    page_title= _get(ev, "pageContext.title")
    page_dom  = _get(ev, "pageContext.domain")

    session_id   = ev.get("sessionId")
    session_ms   = ev.get("sessionDuration")

    interaction_type = ev.get("interactionType")
    input_type       = ev.get("inputType")
    input_value      = ev.get("inputValue")

    # Natural language sentence (no truncation)
    parts = []
    parts.append(f"User '{user}' performed a {action} action")

    # element core
    el_desc_bits = []
    if tag: el_desc_bits.append(f"tag='{tag}'")
    if el_id: el_desc_bits.append(f"id='{el_id}'")
    if cls: el_desc_bits.append(f"class='{cls}'")
    if dtype: el_desc_bits.append(f"type='{dtype}'")
    if name: el_desc_bits.append(f"name='{name}'")
    if value is not None: el_desc_bits.append(f"value='{value}'")
    if text is not None: el_desc_bits.append(f"text='{text}'")
    if placeholder is not None: el_desc_bits.append(f"placeholder='{placeholder}'")
    if href: el_desc_bits.append(f"href='{href}'")
    if pos_str: el_desc_bits.append(pos_str)
    if disabled is not None: el_desc_bits.append(_fmt_bool("disabled", disabled))
    if readonly is not None: el_desc_bits.append(_fmt_bool("readonly", readonly))
    if checked is not None: el_desc_bits.append(_fmt_bool("checked", checked))
    if required is not None: el_desc_bits.append(_fmt_bool("required", required))
    if visible is not None: el_desc_bits.append(_fmt_bool("visible", visible))
    if el_desc_bits:
        parts.append("on element {" + _join(el_desc_bits) + "}")

    # parent + form
    parent_bits = []
    if parent_tag: parent_bits.append(f"tag='{parent_tag}'")
    if parent_id:  parent_bits.append(f"id='{parent_id}'")
    if parent_cls: parent_bits.append(f"class='{parent_cls}'")
    if parent_bits:
        parts.append("with parent {" + _join(parent_bits) + "}")

    form_bits = []
    if form_action: form_bits.append(f"action='{form_action}'")
    if form_id:     form_bits.append(f"id='{form_id}'")
    if form_method: form_bits.append(f"method='{form_method}'")
    if form_bits:
        parts.append("in form {" + _join(form_bits) + "}")

    # event data
    ed_bits = []
    if node_id is not None: ed_bits.append(f"nodeId={node_id}")
    if coords: ed_bits.append(f"coordinates={coords}")
    if interaction_type is not None: ed_bits.append(f"interactionType={interaction_type}")
    if input_type is not None: ed_bits.append(f"inputType='{input_type}'")
    if input_value is not None: ed_bits.append(f"inputValue='{input_value}'")
    if ed_bits:
        parts.append("eventData {" + _join(ed_bits) + "}")

    # page context
    pc_bits = []
    if page_url:   pc_bits.append(f"url='{page_url}'")
    if page_path:  pc_bits.append(f"path='{page_path}'")
    if page_title: pc_bits.append(f"title='{page_title}'")
    if page_dom:   pc_bits.append(f"domain='{page_dom}'")
    if pc_bits:
        parts.append("on page {" + _join(pc_bits) + "}")

    # session
    sess_bits = []
    if session_id: sess_bits.append(f"sessionId='{session_id}'")
    if session_ms is not None: sess_bits.append(f"sessionDuration={session_ms}ms")
    if sess_bits:
        parts.append("session {" + _join(sess_bits) + "}")

    return ". ".join(parts) + "."

def summarize_network(ev: Dict[str, Any]) -> str:
    # user context (full)
    uname = _get(ev, "user.username") or ev.get("user") or "unknown"
    sess  = _get(ev, "user.sessionId")
    domain= _get(ev, "user.domain")
    page  = _get(ev, "user.pageUrl")

    # request (full)
    method = _get(ev, "request.method") or "GET"
    url    = _get(ev, "request.url")
    rtype  = _get(ev, "request.type")
    initi  = _get(ev, "request.initiator")
    frame  = _get(ev, "request.frameId")
    tab    = _get(ev, "request.tabId")

    # response (full)
    code   = _get(ev, "response.statusCode")
    line   = _get(ev, "response.statusLine")
    rip    = _get(ev, "response.ip")
    from_cache = _get(ev, "response.fromCache")

    # timing (full)
    dur    = _get(ev, "timing.duration")
    req_t  = _get(ev, "timing.requestTime")
    res_t  = _get(ev, "timing.responseTime")

    req_id = ev.get("requestId")
    event_type = ev.get("eventType")
    sequence = ev.get("sequence")

    parts = []
    parts.append(f"User '{uname}' initiated an HTTP {method} request to url='{url}'")

    req_bits = []
    if rtype is not None: req_bits.append(f"type='{rtype}'")
    if initi is not None: req_bits.append(f"initiator='{initi}'")
    if frame is not None: req_bits.append(f"frameId={frame}")
    if tab   is not None: req_bits.append(f"tabId={tab}")
    if req_id: req_bits.append(f"requestId='{req_id}'")
    if event_type: req_bits.append(f"eventType='{event_type}'")
    if sequence is not None: req_bits.append(f"sequence={sequence}")
    if req_bits:
        parts.append("request {" + _join(req_bits) + "}")

    resp_bits = []
    if code is not None: resp_bits.append(f"statusCode={code}")
    if line is not None: resp_bits.append(f"statusLine='{line}'")
    if rip  is not None: resp_bits.append(f"ip='{rip}'")
    if from_cache is not None: resp_bits.append(f"fromCache={from_cache}")
    if resp_bits:
        parts.append("response {" + _join(resp_bits) + "}")

    time_bits = []
    if dur  is not None: time_bits.append(f"duration={dur}ms")
    if req_t is not None: time_bits.append(f"requestTime={req_t}")
    if res_t is not None: time_bits.append(f"responseTime={res_t}")
    if time_bits:
        parts.append("timing {" + _join(time_bits) + "}")

    uc_bits = []
    if sess:   uc_bits.append(f"sessionId='{sess}'")
    if domain: uc_bits.append(f"domain='{domain}'")
    if page:   uc_bits.append(f"pageUrl='{page}'")
    if uc_bits:
        parts.append("userContext {" + _join(uc_bits) + "}")

    return ". ".join(parts) + "."

def render_event_text(kind: str, ev: Dict[str, Any]) -> str:
    k = (kind or ev.get("kind") or "").lower()
    if k == "interaction":
        return summarize_interaction(ev)
    if k == "network":
        return summarize_network(ev)
    user = _get(ev, "user.username") or ev.get("user") or "unknown"
    return f"User '{user}' generated an event of kind='{k or 'other'}' with full payload included in the original fields."

def make_actions(kind: str, events: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for e in events:
        # BỘ LỌC: bỏ qua record noise trước khi build event_text
        if not should_keep(kind, e):
            continue

        ts = datetime.fromisoformat(e.get("@timestamp"))
        out = ts.astimezone(timezone.utc) \
            .isoformat(timespec='milliseconds') \
            .replace('+00:00', 'Z')
        idx = index_name(settings.ES_INDEX_PREFIX, kind)

        body = render_event_text(kind, e)
        event_text = f"[{out}] {body}"

        yield {
            "_op_type": "index",
            "_index": idx,
            "_source": {**e, "@timestamp": out, "kind": kind, "event_text": event_text},
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
