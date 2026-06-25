import { useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord'
import { format } from 'date-fns'
import PlateChip from './PlateChip'
import type { WSEventPayload } from '@/types'

interface LiveFeedProps {
  events: WSEventPayload[]
  isConnected: boolean
}

export default function LiveFeed({ events, isConnected }: LiveFeedProps) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [events.length])

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <Typography variant="h6">Live Feed</Typography>
        <Chip
          icon={
            <FiberManualRecordIcon
              sx={{ fontSize: '0.7rem !important', color: isConnected ? '#2ea043 !important' : '#f85149 !important' }}
            />
          }
          label={isConnected ? 'Connected' : 'Reconnecting…'}
          size="small"
          sx={{
            bgcolor: isConnected ? 'rgba(46,160,67,0.15)' : 'rgba(248,81,73,0.15)',
            color: isConnected ? '#2ea043' : '#f85149',
            border: `1px solid ${isConnected ? 'rgba(46,160,67,0.4)' : 'rgba(248,81,73,0.4)'}`,
          }}
        />
      </Box>

      <Box
        ref={listRef}
        sx={{ maxHeight: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}
      >
        {events.length === 0 && (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            Waiting for detections…
          </Typography>
        )}
        {events.map((ev, idx) => (
          <Paper
            key={idx}
            variant="outlined"
            sx={{
              p: 1.5,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              bgcolor: idx === 0 ? 'rgba(0,180,216,0.06)' : 'transparent',
              transition: 'background-color 0.3s',
            }}
          >
            <PlateChip plate={ev.plate!} size="small" />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                {ev.timestamp ? format(new Date(ev.timestamp), 'HH:mm:ss') : '—'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {ev.camera} &bull; conf {ev.confidence?.toFixed(1)}%
              </Typography>
            </Box>
          </Paper>
        ))}
      </Box>
    </Box>
  )
}
