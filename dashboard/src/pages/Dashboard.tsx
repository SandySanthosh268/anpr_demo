import { useState } from 'react'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import LiveFeed from '@/components/LiveFeed'
import PlateTable from '@/components/PlateTable'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useLatestEvents } from '@/hooks/usePlates'

export default function Dashboard() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const { isConnected, liveEvents, activeTracks } = useWebSocket()
  const { data: eventsData, isLoading: eventsLoading } = useLatestEvents(page, pageSize)

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Live Overview
      </Typography>

      {/* Live feed + table */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <LiveFeed events={liveEvents} activeTracks={activeTracks} isConnected={isConnected} />
          </Paper>
        </Grid>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 1.5 }}>
              Recent Detections
            </Typography>
            <PlateTable
              events={eventsData?.items ?? []}
              total={eventsData?.total ?? 0}
              page={page}
              pageSize={pageSize}
              loading={eventsLoading}
              onPageChange={setPage}
              onPageSizeChange={(s) => { setPageSize(s); setPage(1) }}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}
