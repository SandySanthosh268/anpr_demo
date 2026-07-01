import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TablePagination from '@mui/material/TablePagination'
import Tooltip from '@mui/material/Tooltip'
import LinearProgress from '@mui/material/LinearProgress'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus'
import TwoWheelerIcon from '@mui/icons-material/TwoWheeler'
import { format } from 'date-fns'
import PlateChip from './PlateChip'
import type { ANPREvent } from '@/types'

const VEHICLE_STYLE: Record<string, { color: string; bg: string; border: string; Icon: React.ElementType }> = {
  car:        { color: '#2ea043', bg: 'rgba(46,160,67,0.12)',   border: 'rgba(46,160,67,0.4)',   Icon: DirectionsCarIcon },
  truck:      { color: '#1976d2', bg: 'rgba(25,118,210,0.12)',  border: 'rgba(25,118,210,0.4)',  Icon: LocalShippingIcon },
  bus:        { color: '#ed6c02', bg: 'rgba(237,108,2,0.12)',   border: 'rgba(237,108,2,0.4)',   Icon: DirectionsBusIcon },
  motorcycle: { color: '#9c27b0', bg: 'rgba(156,39,176,0.12)', border: 'rgba(156,39,176,0.4)', Icon: TwoWheelerIcon },
}
const UNKNOWN_STYLE = { color: '#888', bg: 'rgba(136,136,136,0.10)', border: 'rgba(136,136,136,0.3)', Icon: DirectionsCarIcon }

function VehicleChip({ type }: { type?: string | null }) {
  if (!type) return <Box sx={{ color: 'text.disabled', fontSize: '0.75rem' }}>—</Box>
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

function BestPlateThumbnail({ path }: { path?: string | null }) {
  if (!path) return <Box sx={{ color: 'text.disabled', fontSize: '0.75rem' }}>—</Box>
  const url = `/${path}`
  return (
    <Tooltip
      title={<Box component="img" src={url} sx={{ maxWidth: 300, borderRadius: 1 }} />}
      placement="left"
    >
      <Box
        component="img"
        src={url}
        sx={{ height: 28, borderRadius: 0.5, border: '1px solid rgba(255,255,255,0.1)', cursor: 'zoom-in' }}
      />
    </Tooltip>
  )
}

interface PlateTableProps {
  events: ANPREvent[]
  total: number
  page: number
  pageSize: number
  loading?: boolean
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 85 ? '#2ea043' : pct >= 65 ? '#d29922' : '#f85149'
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ width: 60 }}>
        <LinearProgress
          variant="determinate"
          value={pct}
          sx={{
            height: 6,
            borderRadius: 3,
            bgcolor: 'rgba(255,255,255,0.08)',
            '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 3 },
          }}
        />
      </Box>
      <Box sx={{ fontSize: '0.75rem', color }}>{pct}%</Box>
    </Box>
  )
}

export default function PlateTable({
  events,
  total,
  page,
  pageSize,
  loading = false,
  onPageChange,
  onPageSizeChange,
}: PlateTableProps) {
  return (
    <Box>
      {loading && <LinearProgress sx={{ mb: 1 }} />}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Plate</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>Camera</TableCell>
              <TableCell>Vehicle</TableCell>
              <TableCell>Detection Conf.</TableCell>
              <TableCell>OCR Conf.</TableCell>
              <TableCell>Best Plate</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.map((ev) => (
              <TableRow key={ev.id} hover>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <PlateChip plate={ev.plate_number} size="small" />
                    {ev.track_id != null && (
                      <Box component="span" sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                        #{ev.track_id}
                      </Box>
                    )}
                  </Box>
                </TableCell>
                <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  {format(new Date(ev.timestamp), 'dd MMM yyyy HH:mm:ss')}
                </TableCell>
                <TableCell sx={{ fontSize: '0.8rem' }}>{ev.camera_name}</TableCell>
                <TableCell>
                  <VehicleChip type={ev.vehicle_type} />
                </TableCell>
                <TableCell>
                  <ConfidenceBar value={ev.confidence} />
                </TableCell>
                <TableCell>
                  <ConfidenceBar value={ev.ocr_confidence} />
                </TableCell>
                <TableCell>
                  <BestPlateThumbnail path={ev.best_plate_path} />
                </TableCell>
              </TableRow>
            ))}
            {events.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                  No records found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={total}
        page={page - 1}
        rowsPerPage={pageSize}
        rowsPerPageOptions={[10, 20, 50, 100]}
        onPageChange={(_, p) => onPageChange(p + 1)}
        onRowsPerPageChange={(e) => onPageSizeChange(Number(e.target.value))}
      />
    </Box>
  )
}
