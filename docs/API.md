# API Documentation

Interactive Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

## Authentication
Currently open (add API key middleware for production as needed).

## Pagination
All list endpoints support `page` (1-based) and `page_size` query parameters.
Response includes `total`, `pages`, `page`, `page_size`.

## Endpoints

### GET /plates/latest
Returns the most recent ANPR events.

**Query params:**
- `page` (int, default 1)
- `page_size` (int, default 20, max 200)
- `camera_name` (string, optional)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "plate_number": "TN01AB1234",
      "timestamp": "2026-01-01T10:00:00+00:00",
      "camera_name": "Gate1",
      "confidence": 0.95,
      "ocr_confidence": 0.92,
      "image_path": "snapshots/TN01AB1234_20260101_100000.jpg",
      "raw_plate_text": "TN01AB1234",
      "created_at": "2026-01-01T10:00:00+00:00"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "pages": 5
}
```

### GET /plates/search
Search events with filters.

**Query params:**
- `plate_number` (string, partial match)
- `date_from` (ISO datetime)
- `date_to` (ISO datetime)
- `camera_name` (string)
- `page`, `page_size`

### GET /plates/count
Returns today's vehicle count.

**Query params:**
- `camera_name` (string, optional)

**Response:**
```json
{ "total": 42, "camera_name": null, "date": "2026-01-01" }
```

### GET /analytics/daily
Per-day vehicle counts.

**Query params:**
- `days` (int, default 7, max 90)
- `camera_name` (optional)

**Response:** `[{"date": "2026-01-01", "count": 42}, ...]`

### GET /analytics/hourly
Per-hour counts for a specific day.

**Query params:**
- `date` (ISO datetime, defaults to today)
- `camera_name` (optional)

**Response:** `[{"hour": 8, "count": 12}, ...]`

### GET /analytics/frequent
Most frequently seen plates.

**Query params:**
- `limit` (int, default 10)
- `days` (int, default 7)
- `camera_name` (optional)

**Response:**
```json
[
  {
    "plate_number": "TN01AB1234",
    "count": 15,
    "first_seen": "2026-01-01T08:00:00+00:00",
    "last_seen": "2026-01-07T18:00:00+00:00"
  }
]
```

### GET /analytics/entry-exit/{plate_number}
First/last seen and total visits for a specific plate.

**Response:**
```json
{
  "plate_number": "TN01AB1234",
  "first_seen": "2026-01-01T08:00:00+00:00",
  "last_seen": "2026-01-07T18:00:00+00:00",
  "total_visits": 15,
  "duration_seconds": 561600
}
```

### POST /camera/register
Register a new camera.

**Body:**
```json
{
  "name": "Gate1",
  "rtsp_url": "rtsp://admin:pass@192.168.1.100:554/stream1",
  "location": "Main Entrance"
}
```

### GET /camera/list
List all registered cameras.

### GET /health
System health check.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "pipeline_running": true,
  "camera_connected": true,
  "ws_clients": 3
}
```

### WebSocket /ws/anpr
Connect for real-time ANPR event streaming.

**JavaScript example:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/anpr')
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'heartbeat') return
  console.log('Detected plate:', data.plate)
}
```
