import { useState } from 'react'
import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Chip from '@mui/material/Chip'
import CloseIcon from '@mui/icons-material/Close'
import ImageIcon from '@mui/icons-material/Image'
import { format } from 'date-fns'
import PlateChip from '@/components/PlateChip'
import { useLatestEvents } from '@/hooks/usePlates'
import type { ANPREvent } from '@/types'

const SNAPSHOT_BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/\/api$/, '')
  : ''

function SnapshotCard({ event, onClick }: { event: ANPREvent; onClick: () => void }) {
  const imgUrl = event.image_path
    ? `${SNAPSHOT_BASE}/${event.image_path.replace(/^\//, '')}`
    : null

  return (
    <Paper
      sx={{ overflow: 'hidden', cursor: 'pointer', transition: 'transform 0.15s', '&:hover': { transform: 'scale(1.02)' } }}
      onClick={onClick}
    >
      <Box
        sx={{
          width: '100%',
          aspectRatio: '16/7',
          bgcolor: 'rgba(0,0,0,0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {imgUrl ? (
          <img
            src={imgUrl}
            alt={event.plate_number}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              ;(e.target as HTMLImageElement).style.display = 'none'
            }}
          />
        ) : (
          <ImageIcon sx={{ fontSize: 48, color: 'rgba(255,255,255,0.2)' }} />
        )}
      </Box>
      <Box sx={{ p: 1.5 }}>
        <PlateChip plate={event.plate_number} size="small" />
        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
          {format(new Date(event.timestamp), 'dd MMM yyyy HH:mm:ss')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
          <Chip label={event.camera_name} size="small" sx={{ fontSize: '0.65rem' }} />
          <Chip
            label={`conf ${Math.round(event.confidence * 100)}%`}
            size="small"
            sx={{ fontSize: '0.65rem' }}
          />
        </Box>
      </Box>
    </Paper>
  )
}

export default function Snapshots() {
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<ANPREvent | null>(null)

  const { data, isLoading } = useLatestEvents(page, 24)
  const events = data?.items.filter((e) => e.image_path) ?? []

  const imgUrl = selected?.image_path
    ? `${SNAPSHOT_BASE}/${selected.image_path.replace(/^\//, '')}`
    : null

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Snapshots
      </Typography>

      {isLoading && <LinearProgress sx={{ mb: 2 }} />}

      {events.length === 0 && !isLoading && (
        <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
          <ImageIcon sx={{ fontSize: 64, opacity: 0.2 }} />
          <Typography>No snapshots available yet</Typography>
        </Box>
      )}

      <Grid container spacing={2}>
        {events.map((ev) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={ev.id}>
            <SnapshotCard event={ev} onClick={() => setSelected(ev)} />
          </Grid>
        ))}
      </Grid>

      {/* Lightbox */}
      <Dialog
        open={!!selected}
        onClose={() => setSelected(null)}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { bgcolor: 'background.paper' } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', p: 2, pb: 0 }}>
          {selected && <PlateChip plate={selected.plate_number} />}
          <Box sx={{ flex: 1 }} />
          <IconButton onClick={() => setSelected(null)}>
            <CloseIcon />
          </IconButton>
        </Box>
        <DialogContent>
          {imgUrl && (
            <img
              src={imgUrl}
              alt={selected?.plate_number}
              style={{ width: '100%', borderRadius: 8 }}
            />
          )}
          {selected && (
            <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Typography variant="body2" color="text.secondary">
                Time: {format(new Date(selected.timestamp), 'dd MMM yyyy HH:mm:ss')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Camera: {selected.camera_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Detection: {Math.round(selected.confidence * 100)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                OCR: {Math.round(selected.ocr_confidence * 100)}%
              </Typography>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  )
}
