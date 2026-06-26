import { useState } from 'react'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
// import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
// import AccessTimeIcon from '@mui/icons-material/AccessTime'
// import RepeatIcon from '@mui/icons-material/Repeat'
// import CameraAltIcon from '@mui/icons-material/CameraAlt'
// import StatsCard from '@/components/StatsCard'
import LiveFeed from '@/components/LiveFeed'
import PlateTable from '@/components/PlateTable'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useTodayCount, useLatestEvents } from '@/hooks/usePlates'
import { useFrequentPlates, useHourlyCounts } from '@/hooks/useAnalytics'

export default function Dashboard() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const { isConnected, liveEvents } = useWebSocket()
  // const { data: countData, isLoading: countLoading } = useTodayCount()
  const { data: eventsData, isLoading: eventsLoading } = useLatestEvents(page, pageSize)
  const { data: frequent } = useFrequentPlates(1)
  const { data: hourly } = useHourlyCounts()

  const peakHour = hourly?.length
    ? hourly.reduce((max, h) => (h.count > max.count ? h : max), hourly[0])
    : null

  const topPlate = frequent?.[0]?.plate_number

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Live Overview
      </Typography>

      {/* Stats row
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Today's Vehicles"
            value={countData?.total ?? 0}
            subtitle={countData?.date ?? ''}
            Icon={DirectionsCarIcon}
            loading={countLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Peak Hour"
            value={peakHour ? `${peakHour.hour}:00` : '—'}
            subtitle={peakHour ? `${peakHour.count} detections` : 'No data'}
            Icon={AccessTimeIcon}
            color="#d29922"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Top Plate Today"
            value={topPlate ?? '—'}
            subtitle={frequent?.[0] ? `${frequent[0].count} times` : ''}
            Icon={RepeatIcon}
            color="#2ea043"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Live WS Clients"
            value={liveEvents.length}
            subtitle="Recent live events"
            Icon={CameraAltIcon}
            color={isConnected ? '#2ea043' : '#f85149'}
          />
        </Grid>
      </Grid> */}

      {/* Live feed + table */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <LiveFeed events={liveEvents} isConnected={isConnected} />
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
