# Log OCS Backend (FastAPI)

**Pipeline mới**: Extension ⇒ **Ingest API** ⇒ **Kafka** ⇒ **Processor** ⇒ **PostgreSQL + Elasticsearch**

- Ingest API: chỉ nhận HTTP và **produce** vào Kafka (không ghi DB/ES).
- Processor: **consumer** Kafka, sau đó lưu Postgres (lưu giữ lâu dài) và đẩy Elasticsearch (search/visualize).
- Nếu ES lỗi, processor sẽ ghi **NDJSON** vào `failed_es/` để retry thủ công.

## Chạy bằng Docker Compose
1. `cp .env.example .env` và cấu hình Kafka/Postgres/Elasticsearch.
2. `docker compose up --build`
3. Ingest API tại `http://localhost:8000/docs`

### Endpoints Ingest
- `POST /v1/logs/interaction` – nhận batch, **produce** vào topic.
- `POST /v1/logs/network` – nhận batch, **produce** vào topic.
- `GET /health` – báo trạng thái Kafka/ES/DB (ES/DB chỉ để tham khảo vì không ghi trực tiếp).

**Client mẫu (background/content):**
```js
async function sendBatch(kind, events) {
  await fetch("http://localhost:8000/v1/logs/" + kind, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(events), keepalive: true
  });
}
```
# Log OCS Backend (FastAPI)

Nhận log từ Chrome Extension, lưu trữ lâu dài (PostgreSQL) và đẩy sang Elasticsearch.

## Tính năng
- REST Ingest API (batch) cho 2 loại log: `interaction` (từ content script) và `network` (từ background).
- Lưu **bản gốc** của mỗi event vào PostgreSQL (JSONB) + cột metadata (ts/kind/username/session_id/domain/page_url).
- Đẩy sang Elasticsearch (bulk). Nếu đẩy thất bại sẽ ghi tạm NDJSON để retry thủ công.
- `/health` kiểm tra kết nối DB/ES.
- Cấu hình qua biến môi trường.

## Chạy nhanh (Docker Compose)
1. Tạo file `.env` từ mẫu:
   ```bash
   cp .env.local .env
   ```
2. Sửa `.env` cho đúng thông tin PostgreSQL và Elasticsearch.
3. Chạy:
   ```bash
   docker compose up --build
   ```
4. API sẽ nghe ở `http://localhost:8000`. Truy cập `http://localhost:8000/docs` để thử.

> Ghi chú: Compose này chỉ chạy **app + Postgres**. Trỏ Elasticsearch tới cụm sẵn có của bạn qua biến môi trường `ELASTICSEARCH_URLS`.
> Nếu chưa có cụm ES để test, có thể tự thêm service ES/Kibana vào compose sau.

## Biến môi trường chính
- `DATABASE_URL` (vd: `postgresql+asyncpg://postgres:postgres@db:5432/logocs`)
- `ELASTICSEARCH_URLS` (vd: `http://es1:9200,http://es2:9200`)
- `ELASTIC_USERNAME`, `ELASTIC_PASSWORD`, `ELASTIC_CA_CERT` (optional)
- `ES_INDEX_PREFIX` (mặc định: `logocs`)
- `RETENTION_DAYS` (chỉ để tham khảo, chưa tự xoá dữ liệu)
- `LOG_LEVEL` (mặc định: `INFO`)

## CURL mẫu
```bash
# Gửi interaction events (batch)
curl -X POST http://localhost:8000/v1/logs/interaction   -H "Content-Type: application/json"   -d '[{
    "ts": "2025-08-15T12:00:00Z",
    "user": {"username":"alice","sessionId":"s1","domain":"example.local","pageUrl":"/home"},
    "eventType": "click",
    "domInfo": {"tag":"button","id":"save"}
  }]'

# Gửi network events (batch)
curl -X POST http://localhost:8000/v1/logs/network   -H "Content-Type: application/json"   -d '[{
    "ts": "2025-08-15T12:00:05Z",
    "user": {"username":"alice","sessionId":"s1","domain":"example.local","pageUrl":"/home"},
    "request": {"url":"http://10.0.0.1/api","method":"GET"},
    "response": {"statusCode":200},
    "timing": {"durationMs": 123}
  }]'
```

## Gợi ý client (thay phần TODO trong extension)
JavaScript (background/content):
```js
async function sendBatch(kind, events) {
  try {
    const res = await fetch("http://localhost:8000/v1/logs/" + kind, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(events),
      keepalive: true
    });
    if (!res.ok) {
      console.warn("Ingest failed", res.status);
    }
  } catch (e) {
    console.error("Ingest error", e);
  }
}
```

## Kafka (tuỳ chọn)
Bật Kafka để đẩy log ra topic song song với Elasticsearch.
- Bật bằng cách đặt `KAFKA_ENABLED=true` và cấu hình `KAFKA_BOOTSTRAP_SERVERS`.
- Mặc định mỗi event sẽ được gửi thành **1 message** với key là `sessionId`/`username` (nếu có).
- Topic mặc định:
  - `KAFKA_TOPIC_INTERACTION=logocs-interaction`
  - `KAFKA_TOPIC_NETWORK=logocs-network`

### Biến môi trường Kafka
```
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=broker1:9092,broker2:9092
KAFKA_TOPIC_INTERACTION=logocs-interaction
KAFKA_TOPIC_NETWORK=logocs-network
# Bảo mật (tuỳ cụm)
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-username
KAFKA_SASL_PASSWORD=your-password
KAFKA_SSL_CAFILE=/path/to/ca.pem
```

### Auto-create topics
Ingest API và Processor sẽ tự tạo 2 topic nếu chưa có (mặc định 3 partitions, RF=2).
Tuỳ cụm của bạn, đổi số partition/RF trong mã `ensure_topics([...])` hoặc cấp quyền `Create` cho tài khoản ứng dụng.
