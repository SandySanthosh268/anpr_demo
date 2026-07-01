import { useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Tooltip from '@mui/material/Tooltip'
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus'
import TwoWheelerIcon from '@mui/icons-material/TwoWheeler'
import { format } from 'date-fns'
import PlateChip from './PlateChip'
import type { ActiveTrack, WSEventPayload } from '@/types'

const VEHICLE_STYLE: Record<string, { color: string; bg: string; border: string; Icon: React.ElementType }> = {
  car:        { color: '#2ea043', bg: 'rgba(46,160,67,0.12)',   border: 'rgba(46,160,67,0.4)',   Icon: DirectionsCarIcon },
  truck:      { color: '#1976d2', bg: 'rgba(25,118,210,0.12)',  border: 'rgba(25,118,210,0.4)',  Icon: LocalShippingIcon },
  bus:        { color: '#ed6c02', bg: 'rgba(237,108,2,0.12)',   border: 'rgba(237,108,2,0.4)',   Icon: DirectionsBusIcon },
  motorcycle: { color: '#9c27b0', bg: 'rgba(156,39,176,0.12)', border: 'rgba(156,39,176,0.4)', Icon: TwoWheelerIcon },
}
const UNKNOWN_STYLE = { color: '#888', bg: 'rgba(136,136,136,0.10)', border: 'rgba(136,136,136,0.3)', Icon: DirectionsCarIcon }

function VehicleChip({ type }: { type?: string | null }) {
  if (!type) return null
  const s = VEHICLE_STYLE[type] ?? UNKNOWN_STYLE
  const { Icon } = s
  return (
    <Chip
      icon={<Icon sx={{ fontSize: '0.75rem !important', color: `${s.color} !important` }} />}
      label={type}
      size="small"
      sx={{ bgcolor: s.bg, color: s.color, border: `1px solid ${s.border}`, fontSize: '0.7rem', height: 20 }}
    />
  )
}

interface LiveFeedProps {
  events: WSEventPayload[]
  activeTracks: ActiveTrack[]
  isConnected: boolean
}

export default function LiveFeed({ events, activeTracks, isConnected }: LiveFeedProps) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [events.length])

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <Typography variant="h6">Detected Plates</Typography>
        <Chip
          icon={
            <FiberManualRecordIcon
              sx={{ fontSize: '0.7rem !important', color: isConnected ? '#2ea043 !important' : '#f85149 !important' }}
            />
          }
          label={isConnected ? 'Live' : 'Reconnecting…'}
          size="small"
          sx={{
            bgcolor: isConnected ? 'rgba(46,160,67,0.15)' : 'rgba(248,81,73,0.15)',
            color: isConnected ? '#2ea043' : '#f85149',
            border: `1px solid ${isConnected ? 'rgba(46,160,67,0.4)' : 'rgba(248,81,73,0.4)'}`,
          }}
        />
      </Box>

      {/* ── On-screen right now ───────────────────────────────────── */}
      {activeTracks.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 1, fontSize: '0.65rem' }}>
            On camera now
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.5 }}>
            {activeTracks.map((t) => (
              <Chip
                key={t.track_id}
                label={t.plate}
                size="small"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  letterSpacing: '0.06em',
                  bgcolor: 'rgba(0,230,118,0.15)',
                  color: '#00e676',
                  border: '1px solid rgba(0,230,118,0.4)',
                }}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* ── Detection event history ───────────────────────────────── */}
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 1, fontSize: '0.65rem' }}>
        Recent events
      </Typography>

      <Box
        ref={listRef}
        sx={{ maxHeight: 340, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1, mt: 0.5 }}
      >
        {events.length === 0 && (
          <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
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
              gap: 1.5,
              bgcolor: idx === 0 ? 'rgba(0,180,216,0.06)' : 'transparent',
              transition: 'background-color 0.3s',
            }}
          >
            {/* Best plate thumbnail */}
            {ev.best_plate_path && (
              <Tooltip
                title={<Box component="img" src={`/${ev.best_plate_path}`} sx={{ maxWidth: 240, borderRadius: 1 }} />}
                placement="right"
              >
                <Box
                  component="img"
                  src={`/${ev.best_plate_path}`}
                  sx={{ height: 32, borderRadius: 0.5, border: '1px solid rgba(255,255,255,0.1)', cursor: 'zoom-in', flexShrink: 0 }}
                />
              </Tooltip>
            )}

            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 0.25 }}>
                <PlateChip plate={ev.plate!} size="small" />
                <VehicleChip type={ev.vehicle_type} />
                {ev.track_id != null && (
                  <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.65rem' }}>
                    #{ev.track_id}
                  </Typography>
                )}
              </Box>
              <Typography variant="caption" color="text.secondary">
                {ev.timestamp ? format(new Date(ev.timestamp), 'HH:mm:ss') : '—'}
                {' '}&bull;{' '}{ev.camera}
                {' '}&bull;{' '}conf {ev.confidence?.toFixed(1)}%
              </Typography>
            </Box>
          </Paper>
        ))}
      </Box>
    </Box>
  )
}
