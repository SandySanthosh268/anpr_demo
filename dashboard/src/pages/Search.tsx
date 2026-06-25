import { useState } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import Button from '@mui/material/Button'
import Grid from '@mui/material/Grid'
import SearchIcon from '@mui/icons-material/Search'
import PlateTable from '@/components/PlateTable'
import { useSearchEvents } from '@/hooks/usePlates'

interface SearchParams {
  plate_number: string
  date_from: string
  date_to: string
  camera_name: string
}

const EMPTY: SearchParams = { plate_number: '', date_from: '', date_to: '', camera_name: '' }

export default function Search() {
  const [form, setForm] = useState<SearchParams>(EMPTY)
  const [submitted, setSubmitted] = useState<SearchParams | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const { data, isLoading } = useSearchEvents(
    submitted
      ? {
          plate_number: submitted.plate_number || undefined,
          date_from: submitted.date_from || undefined,
          date_to: submitted.date_to || undefined,
          camera_name: submitted.camera_name || undefined,
          page,
          page_size: pageSize,
        }
      : {}
  )

  const handleSearch = () => {
    setPage(1)
    setSubmitted({ ...form })
  }

  const handleReset = () => {
    setForm(EMPTY)
    setSubmitted(null)
    setPage(1)
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Search
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems="flex-end">
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              label="Plate Number"
              value={form.plate_number}
              onChange={(e) => setForm((f) => ({ ...f, plate_number: e.target.value.toUpperCase() }))}
              fullWidth
              size="small"
              placeholder="e.g. TN01AB"
              inputProps={{ style: { fontFamily: 'monospace', letterSpacing: '0.05em' } }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              label="From"
              type="datetime-local"
              value={form.date_from}
              onChange={(e) => setForm((f) => ({ ...f, date_from: e.target.value }))}
              fullWidth
              size="small"
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              label="To"
              type="datetime-local"
              value={form.date_to}
              onChange={(e) => setForm((f) => ({ ...f, date_to: e.target.value }))}
              fullWidth
              size="small"
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              label="Camera"
              value={form.camera_name}
              onChange={(e) => setForm((f) => ({ ...f, camera_name: e.target.value }))}
              fullWidth
              size="small"
              placeholder="e.g. Gate1"
            />
          </Grid>
          <Grid item xs={6} md={0.5}>
            <Button
              variant="contained"
              startIcon={<SearchIcon />}
              onClick={handleSearch}
              fullWidth
            >
              Search
            </Button>
          </Grid>
          <Grid item xs={6} md={0.5}>
            <Button variant="outlined" onClick={handleReset} fullWidth>
              Reset
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {submitted && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {data?.total ?? 0} result(s) found
          </Typography>
          <PlateTable
            events={data?.items ?? []}
            total={data?.total ?? 0}
            page={page}
            pageSize={pageSize}
            loading={isLoading}
            onPageChange={setPage}
            onPageSizeChange={(s) => { setPageSize(s); setPage(1) }}
          />
        </Paper>
      )}

      {!submitted && (
        <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
          <SearchIcon sx={{ fontSize: 64, opacity: 0.2 }} />
          <Typography>Enter search criteria above and click Search</Typography>
        </Box>
      )}
    </Box>
  )
}
