import { useQuery } from '@tanstack/react-query'
import { getLatestEvents, getTodayCount, searchEvents } from '@/api/endpoints'

export const useTodayCount = (cameraName?: string) =>
  useQuery({
    queryKey: ['count', cameraName],
    queryFn: () => getTodayCount(cameraName),
    refetchInterval: 30_000,
  })

export const useLatestEvents = (page = 1, pageSize = 20, cameraName?: string) =>
  useQuery({
    queryKey: ['events', 'latest', page, pageSize, cameraName],
    queryFn: () => getLatestEvents(page, pageSize, cameraName),
    refetchInterval: 15_000,
    placeholderData: (prev) => prev,
  })

export const useSearchEvents = (params: {
  plate_number?: string
  date_from?: string
  date_to?: string
  camera_name?: string
  page?: number
  page_size?: number
}) =>
  useQuery({
    queryKey: ['events', 'search', params],
    queryFn: () => searchEvents(params),
    enabled: Object.values(params).some(Boolean),
    placeholderData: (prev) => prev,
  })
