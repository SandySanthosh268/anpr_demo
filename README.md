# ANPR System — Real-Time Indian Number Plate Recognition

A production-ready, end-to-end **Automatic Number Plate Recognition (ANPR)** system designed specifically for Indian vehicle registration plates.

```
IP Camera (RTSP)
    ↓
camera_service  — RTSP ingestion + frame skip + auto-reconnect
    ↓
detection_service  — YOLOv8 plate bounding-box detection
    ↓
ocr_service  — PaddleOCR text extraction
    ↓
validation_service  — Indian plate regex + OCR correction + dedup
    ↓
database  — PostgreSQL via SQLAlchemy async + Alembic
    ↓
api_service  — FastAPI REST + WebSocket broadcast
    ↓
dashboard  — React + MUI real-time dashboard
```

---

## Quick Start (Docker)

### 1. Prerequisites
- Docker ≥ 24 and Docker Compose v2
- A YOLOv8 model trained on Indian license plates (see [Model Setup](#model-setup))

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set RTSP_URL, SECRET_KEY, POSTGRES_PASSWORD
```

### 3. Place YOLO model

```bash
mkdir -p models
cp /path/to/yolov8_license_plate.pt models/
```

### 4. Run

```bash
docker compose up -d
```

| Service        | URL                          |
|----------------|------------------------------|
| Dashboard      | http://localhost             |
| REST API       | http://localhost:8000        |
| API Docs       | http://localhost:8000/docs   |
| PostgreSQL     | localhost:5432               |

---

## Local Development

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # configure DATABASE_URL and RTSP_URL

# Run Alembic migrations
alembic upgrade head

# Start API + pipeline
python main.py
# or
uvicorn api_service.main:app --reload --port 8000
```

### Frontend

```bash
cd dashboard
npm install
npm run dev        # http://localhost:3000
```

### Tests

```bash
pip install aiosqlite pytest-asyncio
pytest
```

---

## Folder Structure

```
anpr-system/
├── camera_service/          # RTSP capture, auto-reconnect
│   └── rtsp_capture.py
├── detection_service/       # YOLOv8 plate detection
│   └── plate_detector.py
├── ocr_service/             # PaddleOCR text extraction
│   └── paddle_ocr.py
├── validation_service/      # Indian plate validation + OCR correction
│   └── plate_validator.py
├── pipeline/                # End-to-end ANPR orchestrator
│   └── anpr_pipeline.py
├── api_service/             # FastAPI app
│   ├── main.py
│   ├── schemas.py
│   ├── ws_manager.py
│   └── routers/
│       ├── plates.py
│       ├── analytics.py
│       ├── camera.py
│       └── websocket.py
├── database/                # SQLAlchemy models + CRUD
│   ├── models.py
│   ├── session.py
│   └── crud.py
├── dashboard/               # React + MUI frontend
│   └── src/
│       ├── pages/           # Dashboard, Search, Analytics, Snapshots
│       ├── components/
│       ├── hooks/
│       └── api/
├── alembic/                 # Database migrations
├── docker/                  # Dockerfiles + nginx config
├── snapshots/               # Saved plate images
├── tests/                   # pytest test suite
├── docker-compose.yml
├── config.py                # Centralised pydantic-settings config
└── requirements.txt
```

---

## Model Setup

### Option A — Custom Model (Recommended for production)

Train a YOLOv8 model on Indian license plates:

```bash
# Install ultralytics
pip install ultralytics

# Train (requires labelled dataset in YOLO format)
yolo detect train data=plates.yaml model=yolov8n.pt epochs=100 imgsz=640

# Copy best weights
cp runs/detect/train/weights/best.pt models/yolov8_license_plate.pt
```

### Option B — Fallback (Development only)

If no custom model is found, the system automatically downloads `yolov8n.pt` (general COCO model). Plate detection accuracy will be poor — use only for integration testing.

---

## API Reference

Full Swagger UI available at `/docs`.

### Plates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/plates/latest` | Latest ANPR events (paginated) |
| GET | `/plates/search` | Search by plate, date range, camera |
| GET | `/plates/count` | Today's vehicle count |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/daily?days=7` | Per-day counts |
| GET | `/analytics/hourly` | Per-hour counts for today |
| GET | `/analytics/frequent?limit=10&days=7` | Most frequent plates |
| GET | `/analytics/entry-exit/{plate}` | First/last seen + duration |

### Camera

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/camera/register` | Register an IP camera |
| GET | `/camera/list` | List all cameras |

### WebSocket

```
ws://host/ws/anpr
```

Event payload:
```json
{
  "plate": "TN01AB1234",
  "timestamp": "2026-01-01T10:01:22+00:00",
  "confidence": 98.4,
  "ocr_confidence": 95.1,
  "camera": "Gate1",
  "image_path": "snapshots/TN01AB1234_20260101_100122.jpg",
  "bbox": [120, 340, 560, 420]
}
```

### Health

```
GET /health
```

---

## Indian Plate Validation Rules

The validator supports:

| Format | Example | Pattern |
|--------|---------|---------|
| Standard | `TN01AB1234` | `SS DD LL NNNN` |
| BH Series | `22BH1234AB` | `YY BH NNNN LL` |
| Temporary | `TEMP-01-22-1234` | `TEMP-NN-NN-NNNN` |

**OCR correction rules applied:**

| OCR Error | Correction | Position |
|-----------|-----------|----------|
| `O` → `0` | Digit position | Positions 2,3 and last 4 |
| `I` → `1` | Digit position | Same as above |
| `Z` → `2`, `S` → `5`, `B` → `8`, `G` → `6`, `T` → `7` | Digit positions |
| `0` → `O`, `1` → `I` | Letter positions | Positions 0,1 |

---

## Configuration Reference

All settings are in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `RTSP_URL` | — | Full RTSP stream URL |
| `CAMERA_NAME` | `Gate1` | Label stored with each event |
| `FRAME_SKIP` | `5` | Process every Nth frame |
| `YOLO_CONFIDENCE` | `0.5` | Detection confidence threshold |
| `OCR_CONFIDENCE_THRESHOLD` | `0.7` | Minimum OCR confidence |
| `PLATE_CONFIDENCE_MIN` | `0.6` | Minimum overall confidence to accept |
| `DUPLICATE_WINDOW_SECONDS` | `30` | Suppress same plate for N seconds |
| `SNAPSHOT_DIR` | `snapshots` | Where to save plate images |
| `DETECTION_DEVICE` | `cpu` | `cpu` or `0` / `cuda:0` for GPU |

---

## Production Deployment Notes

1. **TLS** — Put a reverse proxy (nginx/Traefik) with Let's Encrypt in front
2. **GPU** — Set `DETECTION_DEVICE=0` and use `paddlepaddle-gpu` in requirements
3. **Snapshot retention** — Mount `snapshots/` to object storage and run a cleanup cron
4. **Multi-camera** — Deploy one API+pipeline container per camera, sharing the same PostgreSQL
5. **Horizontal scaling** — Run multiple API workers behind a load balancer; the pipeline is a separate process

---

## License

MIT
