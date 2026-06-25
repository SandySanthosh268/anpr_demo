import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import LinearProgress from '@mui/material/LinearProgress'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts'
import PlateChip from '@/components/PlateChip'
import { useDailyCounts, useHourlyCounts, useFrequentPlates } from '@/hooks/useAnalytics'
import { format } from 'date-fns'

export default function Analytics() {
  const { data: daily, isLoading: dailyLoading } = useDailyCounts(14)
  const { data: hourly, isLoading: hourlyLoading } = useHourlyCounts()
  const { data: frequent, isLoading: freqLoading } = useFrequentPlates(15, 30)

  const formattedDaily = daily?.map((d) => ({
    ...d,
    date: format(new Date(d.date), 'dd MMM'),
  }))

  const formattedHourly = Array.from({ length: 24 }, (_, h) => ({
    hour: `${h}:00`,
    count: hourly?.find((r) => r.hour === h)?.count ?? 0,
  }))

  const maxFreq = frequent?.[0]?.count ?? 1

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Analytics
      </Typography>

      <Grid container spacing={3}>
        {/* Daily counts */}
        <Grid item xs={12} lg={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Daily Vehicle Count (14 days)
            </Typography>
            {dailyLoading ? (
              <LinearProgress />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={formattedDaily} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8b949e' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#8b949e' }} />
                  <Tooltip
                    contentStyle={{ background: '#161b22', border: '1px solid rgba(255,255,255,0.08)' }}
                  />
                  <Bar dataKey="count" fill="#00b4d8" radius={[4, 4, 0, 0]} name="Vehicles" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Hourly distribution */}
        <Grid item xs={12} lg={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Today's Hourly Distribution
            </Typography>
            {hourlyLoading ? (
              <LinearProgress />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={formattedHourly} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#8b949e' }} interval={3} />
                  <YAxis tick={{ fontSize: 11, fill: '#8b949e' }} />
                  <Tooltip
                    contentStyle={{ background: '#161b22', border: '1px solid rgba(255,255,255,0.08)' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#00b4d8"
                    strokeWidth={2}
                    dot={false}
                    name="Vehicles"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Frequent plates */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Most Frequent Vehicles (Last 30 Days)
            </Typography>
            {freqLoading ? (
              <LinearProgress />
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>#</TableCell>
                      <TableCell>Plate</TableCell>
                      <TableCell>Count</TableCell>
                      <TableCell>Frequency</TableCell>
                      <TableCell>First Seen</TableCell>
                      <TableCell>Last Seen</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {frequent?.map((fp, idx) => (
                      <TableRow key={fp.plate_number} hover>
                        <TableCell sx={{ color: 'text.secondary' }}>{idx + 1}</TableCell>
                        <TableCell>
                          <PlateChip plate={fp.plate_number} size="small" />
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>{fp.count}</TableCell>
                        <TableCell sx={{ width: 200 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={(fp.count / maxFreq) * 100}
                              sx={{
                                flex: 1,
                                height: 6,
                                borderRadius: 3,
                                bgcolor: 'rgba(255,255,255,0.08)',
                                '& .MuiLinearProgress-bar': { bgcolor: '#00b4d8', borderRadius: 3 },
                              }}
                            />
                          </Box>
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                          {fp.first_seen
                            ? format(new Date(fp.first_seen), 'dd MMM HH:mm')
                            : '—'}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                          {fp.last_seen
                            ? format(new Date(fp.last_seen), 'dd MMM HH:mm')
                            : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                    {!frequent?.length && (
                      <TableRow>
                        <TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                          No data available
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}
