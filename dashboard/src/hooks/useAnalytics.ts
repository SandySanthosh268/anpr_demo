import { useQuery } from '@tanstack/react-query'
import {
  getDailyCounts,
  getFrequentPlates,
  getHourlyCounts,
  getHealth,
} from '@/api/endpoints'

export const useDailyCounts = (days = 7, cameraName?: string) =>
  useQuery({
    queryKey: ['analytics', 'daily', days, cameraName],
    queryFn: () => getDailyCounts(days, cameraName),
    refetchInterval: 60_000,
  })

export const useHourlyCounts = (date?: string, cameraName?: string) =>
  useQuery({
    queryKey: ['analytics', 'hourly', date, cameraName],
    queryFn: () => getHourlyCounts(date, cameraName),
    refetchInterval: 60_000,
  })

export const useFrequentPlates = (limit = 10, days = 7, cameraName?: string) =>
  useQuery({
    queryKey: ['analytics', 'frequent', limit, days, cameraName],
    queryFn: () => getFrequentPlates(limit, days, cameraName),
    refetchInterval: 60_000,
  })

export const useHealth = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10_000,
    retry: false,
  })
