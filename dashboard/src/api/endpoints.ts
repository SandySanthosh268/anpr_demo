import { apiClient } from './client'
import type {
  ANPREvent,
  Camera,
  DailyCount,
  EntryExit,
  EventCount,
  FrequentPlate,
  HealthStatus,
  HourlyCount,
  PaginatedEvents,
} from '@/types'

// ─── Plates ───────────────────────────────────────────────────────────────────

export const getLatestEvents = async (
  page = 1,
  pageSize = 20,
  cameraName?: string
): Promise<PaginatedEvents> => {
  const { data } = await apiClient.get('/plates/latest', {
    params: { page, page_size: pageSize, camera_name: cameraName },
  })
  return data
}

export const searchEvents = async (params: {
  plate_number?: string
  date_from?: string
  date_to?: string
  camera_name?: string
  page?: number
  page_size?: number
}): Promise<PaginatedEvents> => {
  const { data } = await apiClient.get('/plates/search', { params })
  return data
}

export const getTodayCount = async (cameraName?: string): Promise<EventCount> => {
  const { data } = await apiClient.get('/plates/count', {
    params: { camera_name: cameraName },
  })
  return data
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export const getDailyCounts = async (
  days = 7,
  cameraName?: string
): Promise<DailyCount[]> => {
  const { data } = await apiClient.get('/analytics/daily', {
    params: { days, camera_name: cameraName },
  })
  return data
}

export const getHourlyCounts = async (
  date?: string,
  cameraName?: string
): Promise<HourlyCount[]> => {
  const { data } = await apiClient.get('/analytics/hourly', {
    params: { date, camera_name: cameraName },
  })
  return data
}

export const getFrequentPlates = async (
  limit = 10,
  days = 7,
  cameraName?: string
): Promise<FrequentPlate[]> => {
  const { data } = await apiClient.get('/analytics/frequent', {
    params: { limit, days, camera_name: cameraName },
  })
  return data
}

export const getEntryExit = async (plateNumber: string): Promise<EntryExit> => {
  const { data } = await apiClient.get(`/analytics/entry-exit/${plateNumber}`)
  return data
}

// ─── Cameras ──────────────────────────────────────────────────────────────────

export const registerCamera = async (body: {
  name: string
  rtsp_url: string
  location?: string
}): Promise<Camera> => {
  const { data } = await apiClient.post('/camera/register', body)
  return data
}

export const listCameras = async (): Promise<Camera[]> => {
  const { data } = await apiClient.get('/camera/list')
  return data
}

// ─── Health ───────────────────────────────────────────────────────────────────

export const getHealth = async (): Promise<HealthStatus> => {
  const { data } = await apiClient.get('/health')
  return data
}
