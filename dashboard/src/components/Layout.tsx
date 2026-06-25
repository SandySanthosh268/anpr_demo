import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import MenuIcon from '@mui/icons-material/Menu'
import DashboardIcon from '@mui/icons-material/Dashboard'
import SearchIcon from '@mui/icons-material/Search'
import BarChartIcon from '@mui/icons-material/BarChart'
import PhotoLibraryIcon from '@mui/icons-material/PhotoLibrary'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
import { useHealth } from '@/hooks/useAnalytics'
import Chip from '@mui/material/Chip'

const DRAWER_WIDTH = 220

const NAV = [
  { label: 'Dashboard', path: '/', Icon: DashboardIcon },
  { label: 'Search', path: '/search', Icon: SearchIcon },
  { label: 'Analytics', path: '/analytics', Icon: BarChartIcon },
  { label: 'Snapshots', path: '/snapshots', Icon: PhotoLibraryIcon },
]

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { data: health } = useHealth()

  const drawer = (
    <Box sx={{ mt: 1 }}>
      <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
        <DirectionsCarIcon sx={{ color: 'primary.main' }} />
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          ANPR
        </Typography>
      </Box>
      <List dense>
        {NAV.map(({ label, path, Icon }) => (
          <ListItemButton
            key={path}
            selected={location.pathname === path}
            onClick={() => { navigate(path); setMobileOpen(false) }}
            sx={{
              mx: 1,
              borderRadius: 1,
              mb: 0.5,
              '&.Mui-selected': {
                bgcolor: 'rgba(0,180,216,0.12)',
                color: 'primary.main',
                '& .MuiListItemIcon-root': { color: 'primary.main' },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>
              <Icon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary={label} primaryTypographyProps={{ fontSize: '0.9rem' }} />
          </ListItemButton>
        ))}
      </List>
      {health && (
        <Box sx={{ px: 2, mt: 'auto', pt: 2 }}>
          <Chip
            size="small"
            label={health.pipeline_running ? 'Pipeline Running' : 'Pipeline Stopped'}
            sx={{
              bgcolor: health.pipeline_running ? 'rgba(46,160,67,0.15)' : 'rgba(248,81,73,0.15)',
              color: health.pipeline_running ? '#2ea043' : '#f85149',
              fontSize: '0.7rem',
              width: '100%',
            }}
          />
        </Box>
      )}
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          bgcolor: 'background.paper',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <Toolbar>
          <IconButton
            edge="start"
            sx={{ mr: 2, display: { md: 'none' } }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flex: 1, fontWeight: 600 }}>
            {NAV.find((n) => n.path === location.pathname)?.label ?? 'ANPR System'}
          </Typography>
          {health && (
            <Tooltip title={`${health.ws_clients} WebSocket client(s)`}>
              <Chip
                size="small"
                label={health.camera_connected ? 'Camera Online' : 'Camera Offline'}
                sx={{
                  bgcolor: health.camera_connected ? 'rgba(46,160,67,0.15)' : 'rgba(248,81,73,0.15)',
                  color: health.camera_connected ? '#2ea043' : '#f85149',
                  border: `1px solid ${health.camera_connected ? 'rgba(46,160,67,0.3)' : 'rgba(248,81,73,0.3)'}`,
                }}
              />
            </Tooltip>
          )}
        </Toolbar>
      </AppBar>

      {/* Mobile drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width: DRAWER_WIDTH } }}
      >
        {drawer}
      </Drawer>

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            bgcolor: 'background.paper',
            borderRight: '1px solid rgba(255,255,255,0.08)',
          },
        }}
        open
      >
        {drawer}
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px',
          bgcolor: 'background.default',
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  )
}
