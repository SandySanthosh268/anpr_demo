import Chip from '@mui/material/Chip'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'

interface PlateChipProps {
  plate: string
  size?: 'small' | 'medium'
}

export default function PlateChip({ plate, size = 'medium' }: PlateChipProps) {
  return (
    <Chip
      icon={<DirectionsCarIcon />}
      label={plate}
      size={size}
      sx={{
        fontFamily: 'monospace',
        fontWeight: 700,
        fontSize: size === 'medium' ? '0.95rem' : '0.8rem',
        letterSpacing: '0.08em',
        bgcolor: 'rgba(0, 180, 216, 0.15)',
        color: '#00b4d8',
        border: '1px solid rgba(0, 180, 216, 0.4)',
      }}
    />
  )
}
