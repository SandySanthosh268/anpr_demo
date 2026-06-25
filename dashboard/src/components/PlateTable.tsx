import { useState } from 'react'
import Box from '@mui/material/Box'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TablePagination from '@mui/material/TablePagination'
import Tooltip from '@mui/material/Tooltip'
import LinearProgress from '@mui/material/LinearProgress'
import { format } from 'date-fns'
import PlateChip from './PlateChip'
import type { ANPREvent } from '@/types'

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
              <TableCell>Detection Conf.</TableCell>
              <TableCell>OCR Conf.</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.map((ev) => (
              <TableRow key={ev.id} hover>
                <TableCell>
                  <PlateChip plate={ev.plate_number} size="small" />
                </TableCell>
                <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  {format(new Date(ev.timestamp), 'dd MMM yyyy HH:mm:ss')}
                </TableCell>
                <TableCell sx={{ fontSize: '0.8rem' }}>{ev.camera_name}</TableCell>
                <TableCell>
                  <ConfidenceBar value={ev.confidence} />
                </TableCell>
                <TableCell>
                  <ConfidenceBar value={ev.ocr_confidence} />
                </TableCell>
              </TableRow>
            ))}
            {events.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
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
