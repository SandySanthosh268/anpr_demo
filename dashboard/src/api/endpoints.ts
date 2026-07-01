import { apiClient } from './client'
import type {
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

export const getTodayCount = async (cameraName?: string): Promise<EventCount> => {
  const { data } = await apiClient.get('/plates/count', {
    params: { camera_name: cameraName },
  })
  return data
}

// ─── Analytics ────────────────────────────────────────────────────────────────

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

// ─── Pipeline control ─────────────────────────────────────────────────────────

export interface PipelineStatus {
  is_file_source: boolean
  pipeline_active: boolean
  name: string
  url: string
}

export const getPipelineStatus = async (): Promise<PipelineStatus> => {
  const { data } = await apiClient.get('/pipeline/status')
  return data
}

export const playPipeline = async (): Promise<void> => {
  await apiClient.post('/pipeline/play')
}

export const stopPipeline = async (): Promise<void> => {
  await apiClient.post('/pipeline/stop')
}

// ─── Health ───────────────────────────────────────────────────────────────────

export const getHealth = async (): Promise<HealthStatus> => {
  const { data } = await apiClient.get('/health')
  return data
}
