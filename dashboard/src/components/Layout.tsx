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
import Chip from '@mui/material/Chip'
import MenuIcon from '@mui/icons-material/Menu'
import MenuOpenIcon from '@mui/icons-material/MenuOpen'
import DashboardIcon from '@mui/icons-material/Dashboard'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar'
import LiveTvIcon from '@mui/icons-material/LiveTv'
import { useHealth } from '@/hooks/useAnalytics'

const DRAWER_WIDTH = 220
const MINI_WIDTH = 60

const NAV = [
  { label: 'Live View',  path: '/',          Icon: LiveTvIcon    },
  { label: 'Dashboard',  path: '/dashboard', Icon: DashboardIcon },
]

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)   // desktop collapse state
  const navigate = useNavigate()
  const location = useLocation()
  const { data: health } = useHealth()

  const drawerWidth = sidebarOpen ? DRAWER_WIDTH : MINI_WIDTH

  const handleNavClick = (path: string) => {
    navigate(path)
    setMobileOpen(false)
  }

  const drawerContent = (mini = false) => (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Logo row */}
      <Box
        sx={{
          px: mini ? 0 : 2,
          py: 1.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: mini ? 'center' : 'flex-start',
          gap: 1,
          minHeight: 56,
        }}
      >
        <DirectionsCarIcon sx={{ color: 'primary.main', flexShrink: 0 }} />
        {!mini && (
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            ANPR
          </Typography>
        )}
      </Box>

      {/* Nav items */}
      <List dense sx={{ flex: 1 }}>
        {NAV.map(({ label, path, Icon }) => (
          <Tooltip key={path} title={mini ? label : ''} placement="right" arrow>
            <ListItemButton
              selected={location.pathname === path}
              onClick={() => handleNavClick(path)}
              sx={{
                mx: mini ? 0.5 : 1,
                borderRadius: 1,
                mb: 0.5,
                justifyContent: mini ? 'center' : 'flex-start',
                px: mini ? 1 : 2,
                '&.Mui-selected': {
                  bgcolor: 'rgba(0,180,216,0.12)',
                  color: 'primary.main',
                  '& .MuiListItemIcon-root': { color: 'primary.main' },
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: mini ? 'unset' : 36,
                  justifyContent: 'center',
                }}
              >
                <Icon fontSize="small" />
              </ListItemIcon>
              {!mini && (
                <ListItemText
                  primary={label}
                  primaryTypographyProps={{ fontSize: '0.9rem' }}
                />
              )}
            </ListItemButton>
          </Tooltip>
        ))}
      </List>

      {/* Pipeline status */}
      {health && !mini && (
        <Box sx={{ px: 2, pb: 2 }}>
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
      {/* ── AppBar ──────────────────────────────────────────────────── */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { xs: '100%', md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
          bgcolor: 'background.paper',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          transition: 'width 0.2s, margin-left 0.2s',
        }}
      >
        <Toolbar>
          {/* Mobile hamburger */}
          <IconButton
            edge="start"
            sx={{ mr: 1, display: { md: 'none' } }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>

          {/* Desktop collapse toggle */}
          <IconButton
            edge="start"
            sx={{ mr: 2, display: { xs: 'none', md: 'flex' } }}
            onClick={() => setSidebarOpen((v) => !v)}
          >
            {sidebarOpen ? <MenuOpenIcon /> : <MenuIcon />}
          </IconButton>

          <Typography variant="h6" sx={{ flex: 1, fontWeight: 600 }}>
            {NAV.find((n) => n.path === location.pathname)?.label ?? 'ANPR System'}
          </Typography>

          {health && (
            <Tooltip title={`${health.ws_clients} WebSocket client(s) connected`}>
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

      {/* ── Mobile drawer (temporary) ───────────────────────────────── */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH },
        }}
      >
        {drawerContent(false)}
      </Drawer>

      {/* ── Desktop drawer (permanent, collapsible) ─────────────────── */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          width: { md: drawerWidth },   // root div width = flex spacer
          flexShrink: 0,                // don't let flex compress the drawer
          transition: 'width 0.2s',
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            bgcolor: 'background.paper',
            borderRight: '1px solid rgba(255,255,255,0.08)',
            overflowX: 'hidden',
            transition: 'width 0.2s',
          },
        }}
        open
      >
        {drawerContent(!sidebarOpen)}
      </Drawer>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,          // prevents content from bleeding under the drawer
          p: 3,
          mt: '64px',
          bgcolor: 'background.default',
          minHeight: 'calc(100vh - 64px)',
          overflowX: 'hidden',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  )
}
