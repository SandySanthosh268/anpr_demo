import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import CircularProgress from '@mui/material/CircularProgress'
import Tooltip from '@mui/material/Tooltip'
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
import PlayCircleIcon from '@mui/icons-material/PlayCircle'
import StopCircleIcon from '@mui/icons-material/StopCircle'
import VideoFileIcon from '@mui/icons-material/VideoFile'
import { format } from 'date-fns'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useHealth } from '@/hooks/useAnalytics'
import { getPipelineStatus, playPipeline, stopPipeline } from '@/api/endpoints'
import type { WSEventPayload } from '@/types'

const STREAM_URL =
  (import.meta.env.VITE_API_URL ?? '/api').replace(/\/api$/, '') + '/api/stream/video'

export default function LiveView() {
  const queryClient = useQueryClient()
  const { isConnected, liveEvents } = useWebSocket()
  const { data: health } = useHealth()

  const { data: pipelineStatus } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: getPipelineStatus,
    refetchInterval: 3_000,
  })

  const playMutation = useMutation({
    mutationFn: playPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-status'] }),
  })
  const stopMutation = useMutation({
    mutationFn: stopPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-status'] }),
  })

  const isFile = pipelineStatus?.is_file_source ?? false
  const isPlaying = pipelineStatus?.pipeline_active ?? false
  const isBusy = playMutation.isPending || stopMutation.isPending

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        height: 'calc(100vh - 88px)',
        overflow: 'hidden',
      }}
    >
      {/* ── Video feed ─────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {/* LIVE / OFFLINE chip — for RTSP. For files, show file chip */}
          {isFile ? (
            <Chip
              icon={<VideoFileIcon sx={{ fontSize: '0.85rem !important' }} />}
              label="VIDEO FILE"
              size="small"
              sx={{
                bgcolor: isPlaying ? 'rgba(46,160,67,0.15)' : 'rgba(139,148,158,0.1)',
                color: isPlaying ? '#2ea043' : '#8b949e',
                fontWeight: 700,
                letterSpacing: '0.06em',
              }}
            />
          ) : (
            <Chip
              icon={
                <FiberManualRecordIcon
                  sx={{
                    fontSize: '0.7rem !important',
                    color: `${health?.camera_connected ? '#f85149' : '#8b949e'} !important`,
                  }}
                />
              }
              label={health?.camera_connected ? 'LIVE' : 'OFFLINE'}
              size="small"
              sx={{
                bgcolor: health?.camera_connected ? 'rgba(248,81,73,0.15)' : 'rgba(139,148,158,0.1)',
                color: health?.camera_connected ? '#f85149' : '#8b949e',
                fontWeight: 700,
                letterSpacing: '0.08em',
              }}
            />
          )}

          <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
            {isFile
              ? isPlaying
                ? `Playing: ${pipelineStatus?.name}`
                : `Stopped — press Play to start detection`
              : health?.camera_connected
                ? 'Detection active — boxes drawn on plates'
                : 'Camera not connected — check RTSP_URL in .env'}
          </Typography>

          {/* Play / Stop controls — only visible for file sources */}
          {isFile && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {isBusy ? (
                <CircularProgress size={24} sx={{ mx: 1 }} />
              ) : isPlaying ? (
                <Tooltip title="Stop video">
                  <IconButton
                    size="small"
                    onClick={() => stopMutation.mutate()}
                    sx={{ color: '#f85149', '&:hover': { bgcolor: 'rgba(248,81,73,0.1)' } }}
                  >
                    <StopCircleIcon sx={{ fontSize: 32 }} />
                  </IconButton>
                </Tooltip>
              ) : (
                <Tooltip title="Play video & start detection">
                  <IconButton
                    size="small"
                    onClick={() => playMutation.mutate()}
                    sx={{ color: '#2ea043', '&:hover': { bgcolor: 'rgba(46,160,67,0.1)' } }}
                  >
                    <PlayCircleIcon sx={{ fontSize: 32 }} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
          )}
        </Box>

        <Paper
          sx={{
            flex: 1,
            overflow: 'hidden',
            bgcolor: '#000',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <img
            src={STREAM_URL}
            alt="Live ANPR feed"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              display: 'block',
            }}
            onError={(e) => {
              // Retry after 3s if stream fails
              setTimeout(() => {
                const img = e.target as HTMLImageElement
                img.src = STREAM_URL + '?t=' + Date.now()
              }, 3000)
            }}
          />
        </Paper>
      </Box>

      {/* ── Detected plates panel ──────────────────────────────────── */}
      <Paper
        sx={{
          width: 280,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          p: 2,
          overflow: 'hidden',
        }}
      >
        {/* Panel header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <DirectionsCarIcon sx={{ color: 'primary.main', fontSize: 20 }} />
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700 }}>
            Detected Plates
          </Typography>
          <Chip
            icon={
              <FiberManualRecordIcon
                sx={{
                  fontSize: '0.65rem !important',
                  color: `${isConnected ? '#2ea043' : '#f85149'} !important`,
                }}
              />
            }
            label={isConnected ? 'Live' : 'Reconnecting'}
            size="small"
            sx={{
              ml: 'auto',
              fontSize: '0.7rem',
              bgcolor: isConnected ? 'rgba(46,160,67,0.1)' : 'rgba(248,81,73,0.1)',
              color: isConnected ? '#2ea043' : '#f85149',
            }}
          />
        </Box>

        <Divider sx={{ mb: 1.5 }} />

        {/* Plate list */}
        <Box sx={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {liveEvents.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
              <DirectionsCarIcon sx={{ fontSize: 40, opacity: 0.15, display: 'block', mx: 'auto', mb: 1 }} />
              <Typography variant="caption">Waiting for detections…</Typography>
            </Box>
          )}

          {liveEvents.map((ev: WSEventPayload, idx) => (
            <PlateCard key={idx} event={ev} isNew={idx === 0} />
          ))}
        </Box>

        {/* Footer count */}
        <Divider sx={{ mt: 1.5, mb: 1 }} />
        <Typography variant="caption" color="text.secondary" align="center">
          {liveEvents.length} detection{liveEvents.length !== 1 ? 's' : ''} this session
        </Typography>
      </Paper>
    </Box>
  )
}

function PlateCard({ event, isNew }: { event: WSEventPayload; isNew: boolean }) {
  return (
    <Box
      sx={{
        p: 1.25,
        borderRadius: 1.5,
        border: '1px solid',
        borderColor: isNew ? 'rgba(0,180,216,0.4)' : 'rgba(255,255,255,0.07)',
        bgcolor: isNew ? 'rgba(0,180,216,0.06)' : 'transparent',
        transition: 'all 0.3s',
      }}
    >
      {/* Plate number */}
      <Typography
        sx={{
          fontFamily: 'monospace',
          fontWeight: 700,
          fontSize: '1.1rem',
          letterSpacing: '0.06em',
          color: 'primary.main',
          lineHeight: 1.2,
        }}
      >
        {event.plate}
      </Typography>

      {/* Meta row */}
      <Box sx={{ display: 'flex', gap: 1, mt: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography variant="caption" color="text.secondary">
          {event.timestamp ? format(new Date(event.timestamp), 'HH:mm:ss') : '—'}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Chip
          label={`${event.confidence?.toFixed(1)}%`}
          size="small"
          sx={{
            height: 18,
            fontSize: '0.65rem',
            fontWeight: 600,
            bgcolor: 'rgba(255,255,255,0.06)',
            color: 'text.secondary',
          }}
        />
      </Box>

      {/* Camera name */}
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>
        {event.camera}
      </Typography>
    </Box>
  )
}
