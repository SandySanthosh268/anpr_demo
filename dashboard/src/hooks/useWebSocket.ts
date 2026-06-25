import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL } from '@/api/client'
import type { WSEventPayload } from '@/types'

interface UseWebSocketOptions {
  onEvent?: (event: WSEventPayload) => void
  maxHistory?: number
}

export function useWebSocket({ onEvent, maxHistory = 50 }: UseWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [liveEvents, setLiveEvents] = useState<WSEventPayload[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number | null>(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        if (!mountedRef.current) return
        setIsConnected(true)
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = null
        }
      }

      ws.onmessage = (msg) => {
        if (!mountedRef.current) return
        try {
          const payload: WSEventPayload = JSON.parse(msg.data)
          if (payload.type === 'heartbeat') return
          setLiveEvents((prev) => [payload, ...prev].slice(0, maxHistory))
          onEvent?.(payload)
        } catch {
          // ignore malformed frames
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setIsConnected(false)
        wsRef.current = null
        // Reconnect after 3 seconds
        reconnectTimer.current = window.setTimeout(connect, 3_000)
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    } catch {
      reconnectTimer.current = window.setTimeout(connect, 5_000)
    }
  }, [onEvent, maxHistory])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { isConnected, liveEvents }
}
