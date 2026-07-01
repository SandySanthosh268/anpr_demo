export interface ANPREvent {
  id: number
  plate_number: string
  timestamp: string
  camera_name: string
  confidence: number
  ocr_confidence: number
  image_path: string | null
  raw_plate_text: string | null
  track_id: number | null
  vehicle_type: string | null
  best_plate_path: string | null
  created_at: string
}

export interface PaginatedEvents {
  items: ANPREvent[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface EventCount {
  total: number
  camera_name: string | null
  date: string | null
}

export interface DailyCount {
  date: string
  count: number
}

export interface HourlyCount {
  hour: number
  count: number
}

export interface FrequentPlate {
  plate_number: string
  count: number
  first_seen: string | null
  last_seen: string | null
}

export interface EntryExit {
  plate_number: string
  first_seen: string | null
  last_seen: string | null
  total_visits: number
  duration_seconds: number | null
}

export interface Camera {
  id: number
  name: string
  rtsp_url: string
  location: string | null
  is_active: boolean
  created_at: string
}

export interface HealthStatus {
  status: string
  version: string
  pipeline_running: boolean
  camera_connected: boolean
  ws_clients: number
}

export interface WSEventPayload {
  type?: 'heartbeat' | 'tracks_update'
  plate?: string
  timestamp?: string
  confidence?: number
  ocr_confidence?: number
  camera?: string
  image_path?: string | null
  bbox?: number[] | null
  track_id?: number | null
  vehicle_type?: string | null
  best_plate_path?: string | null
  // present when type === 'tracks_update'
  tracks?: ActiveTrack[]
}

export interface ActiveTrack {
  track_id: number
  plate: string
  camera: string
  timestamp: number
}
