import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import type { SvgIconComponent } from '@mui/icons-material'

interface StatsCardProps {
  title: string
  value: string | number
  subtitle?: string
  Icon: SvgIconComponent
  color?: string
  loading?: boolean
}

export default function StatsCard({
  title,
  value,
  subtitle,
  Icon,
  color = '#00b4d8',
  loading = false,
}: StatsCardProps) {
  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700, color }}>
            {loading ? '—' : value}
          </Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            bgcolor: `${color}22`,
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Icon sx={{ color, fontSize: 32 }} />
        </Box>
      </Box>
    </Paper>
  )
}
