import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Tooltip from '@mui/material/Tooltip'
import LinearProgress from '@mui/material/LinearProgress'
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline'
import VideocamIcon from '@mui/icons-material/Videocam'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import CloudUploadIcon from '@mui/icons-material/CloudUpload'
import { format } from 'date-fns'
import {
  getActiveSource,
  listCameras,
  registerCamera,
  setActiveCameraByName,
  switchSource,
  uploadVideo,
} from '@/api/endpoints'
import type { Camera } from '@/types'

const EMPTY_RTSP = { name: '', rtsp_url: '', location: '' }

// ── Status chip ────────────────────────────────────────────────────────────────
function CameraStatusChip({ name, activeSource }: { name: string; activeSource: string }) {
  const isActive = activeSource === name
  return (
    <Chip
      icon={
        isActive ? (
          <CheckCircleIcon sx={{ fontSize: '0.85rem !important' }} />
        ) : (
          <ErrorIcon sx={{ fontSize: '0.85rem !important' }} />
        )
      }
      label={isActive ? 'Active' : 'Idle'}
      size="small"
      sx={{
        bgcolor: isActive ? 'rgba(46,160,67,0.15)' : 'rgba(139,148,158,0.15)',
        color: isActive ? '#2ea043' : '#8b949e',
        border: `1px solid ${isActive ? 'rgba(46,160,67,0.3)' : 'rgba(139,148,158,0.2)'}`,
        fontWeight: 600,
      }}
    />
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function Cameras() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState(0)

  // RTSP form
  const [rtspForm, setRtspForm] = useState(EMPTY_RTSP)
  const [rtspError, setRtspError] = useState('')
  const [rtspSuccess, setRtspSuccess] = useState('')

  // Video upload form
  const [videoName, setVideoName] = useState('')
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoError, setVideoError] = useState('')
  const [videoSuccess, setVideoSuccess] = useState('')
  const [uploadProgress, setUploadProgress] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Active source (polling)
  const { data: activeSource } = useQuery({
    queryKey: ['active-source'],
    queryFn: getActiveSource,
    refetchInterval: 5_000,
  })

  // Camera list
  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: listCameras,
    refetchInterval: 15_000,
  })

  // Register RTSP camera
  const registerMutation = useMutation({
    mutationFn: registerCamera,
    onSuccess: (cam) => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      setRtspSuccess(`Camera "${cam.name}" registered.`)
      setRtspForm(EMPTY_RTSP)
      setRtspError('')
      setTimeout(() => setRtspSuccess(''), 4000)
    },
    onError: (err: any) => {
      setRtspError(err?.response?.data?.detail ?? 'Registration failed.')
    },
  })

  // Set active by registered name
  const setActiveMutation = useMutation({
    mutationFn: setActiveCameraByName,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['active-source'] })
    },
  })

  const handleRtspSubmit = () => {
    setRtspError('')
    if (!rtspForm.name.trim()) { setRtspError('Camera name is required.'); return }
    if (!rtspForm.rtsp_url.trim()) { setRtspError('RTSP URL is required.'); return }
    const url = rtspForm.rtsp_url.trim()
    if (!url.startsWith('rtsp://') && !url.startsWith('rtmp://') && !url.startsWith('http')) {
      setRtspError('URL must start with rtsp://, rtmp://, or http.')
      return
    }
    registerMutation.mutate({
      name: rtspForm.name.trim(),
      rtsp_url: url,
      location: rtspForm.location.trim() || undefined,
    })
  }

  const handleVideoUpload = async () => {
    setVideoError('')
    if (!videoName.trim()) { setVideoError('Source name is required.'); return }
    if (!videoFile) { setVideoError('Select a video file first.'); return }

    setUploadProgress(true)
    try {
      const result = await uploadVideo(videoFile)
      await switchSource(result.path, videoName.trim())
      queryClient.invalidateQueries({ queryKey: ['active-source'] })
      setVideoSuccess(`"${videoFile.name}" uploaded and set as active source.`)
      setVideoName('')
      setVideoFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setTimeout(() => setVideoSuccess(''), 5000)
    } catch (err: any) {
      setVideoError(err?.response?.data?.detail ?? 'Upload failed.')
    } finally {
      setUploadProgress(false)
    }
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 700 }}>
        Video Sources
      </Typography>

      {/* Active source banner */}
      {activeSource && (
        <Alert
          severity="info"
          icon={<PlayArrowIcon />}
          sx={{ mb: 3, fontFamily: 'monospace' }}
        >
          <strong>Active:</strong> {activeSource.name} — {activeSource.url}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* ── Left: add source ──────────────────────────────────── */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <AddCircleOutlineIcon sx={{ color: 'primary.main' }} />
              <Typography variant="h6">Add New Source</Typography>
            </Box>

            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
              <Tab label="RTSP Stream" />
              <Tab label="Upload Video" />
            </Tabs>

            {tab === 0 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  label="Camera Name"
                  value={rtspForm.name}
                  onChange={(e) => setRtspForm((f) => ({ ...f, name: e.target.value }))}
                  fullWidth
                  size="small"
                  placeholder="e.g. Gate1, Parking-A"
                  helperText="Unique label stored with every detection"
                />
                <TextField
                  label="RTSP URL"
                  value={rtspForm.rtsp_url}
                  onChange={(e) => setRtspForm((f) => ({ ...f, rtsp_url: e.target.value }))}
                  fullWidth
                  size="small"
                  placeholder="rtsp://admin:pass@192.168.1.100:554/stream1"
                  inputProps={{ style: { fontFamily: 'monospace', fontSize: '0.85rem' } }}
                />
                <TextField
                  label="Location (optional)"
                  value={rtspForm.location}
                  onChange={(e) => setRtspForm((f) => ({ ...f, location: e.target.value }))}
                  fullWidth
                  size="small"
                  placeholder="e.g. Main Entrance, North Gate"
                />
                {rtspError   && <Alert severity="error"   sx={{ py: 0 }}>{rtspError}</Alert>}
                {rtspSuccess && <Alert severity="success" sx={{ py: 0 }}>{rtspSuccess}</Alert>}
                <Button
                  variant="contained"
                  onClick={handleRtspSubmit}
                  disabled={registerMutation.isPending}
                  startIcon={
                    registerMutation.isPending
                      ? <CircularProgress size={16} />
                      : <AddCircleOutlineIcon />
                  }
                  fullWidth
                >
                  {registerMutation.isPending ? 'Registering…' : 'Register Camera'}
                </Button>
              </Box>
            )}

            {tab === 1 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  label="Source Name"
                  value={videoName}
                  onChange={(e) => setVideoName(e.target.value)}
                  fullWidth
                  size="small"
                  placeholder="e.g. TestVideo, ParkingLot"
                  helperText="Label for this video file"
                />

                <Box
                  sx={{
                    border: '2px dashed',
                    borderColor: videoFile ? 'primary.main' : 'divider',
                    borderRadius: 2,
                    p: 3,
                    textAlign: 'center',
                    cursor: 'pointer',
                    bgcolor: videoFile ? 'rgba(0,180,216,0.05)' : 'transparent',
                    transition: 'all 0.2s',
                    '&:hover': { borderColor: 'primary.main', bgcolor: 'rgba(0,180,216,0.05)' },
                  }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".mp4,.avi,.mov,.mkv,.ts,.flv,.webm"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null
                      setVideoFile(f)
                      if (!videoName && f) {
                        setVideoName(f.name.replace(/\.[^.]+$/, ''))
                      }
                    }}
                  />
                  <CloudUploadIcon
                    sx={{ fontSize: 40, color: videoFile ? 'primary.main' : 'action.disabled', mb: 1 }}
                  />
                  {videoFile ? (
                    <>
                      <Typography variant="body2" fontWeight={600}>{videoFile.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {(videoFile.size / 1_048_576).toFixed(1)} MB
                      </Typography>
                    </>
                  ) : (
                    <>
                      <Typography variant="body2" color="text.secondary">
                        Click to select video file
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        mp4, avi, mov, mkv, ts, flv, webm
                      </Typography>
                    </>
                  )}
                </Box>

                {uploadProgress && <LinearProgress />}
                {videoError   && <Alert severity="error"   sx={{ py: 0 }}>{videoError}</Alert>}
                {videoSuccess && <Alert severity="success" sx={{ py: 0 }}>{videoSuccess}</Alert>}

                <Button
                  variant="contained"
                  onClick={handleVideoUpload}
                  disabled={uploadProgress || !videoFile}
                  startIcon={
                    uploadProgress
                      ? <CircularProgress size={16} />
                      : <PlayArrowIcon />
                  }
                  fullWidth
                >
                  {uploadProgress ? 'Uploading…' : 'Upload & Set Active'}
                </Button>

                <Divider />
                <Typography variant="caption" color="text.secondary">
                  The video will loop continuously. Uploads are stored on the server under <code>videos/</code>.
                </Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* ── Right: camera list ────────────────────────────────── */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2.5 }}>
              <VideocamIcon sx={{ color: 'primary.main' }} />
              <Typography variant="h6">Registered Cameras</Typography>
              <Chip
                label={cameras?.length ?? 0}
                size="small"
                sx={{ ml: 'auto', bgcolor: 'rgba(0,180,216,0.15)', color: 'primary.main' }}
              />
            </Box>

            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={32} />
              </Box>
            ) : cameras?.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 5, color: 'text.secondary' }}>
                <VideocamIcon sx={{ fontSize: 56, opacity: 0.15, display: 'block', mx: 'auto', mb: 1 }} />
                <Typography>No cameras registered yet</Typography>
                <Typography variant="caption">Add a source using the form on the left</Typography>
              </Box>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>URL / Path</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Added</TableCell>
                      <TableCell align="right">Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {cameras?.map((cam: Camera) => (
                      <TableRow key={cam.id} hover>
                        <TableCell sx={{ fontWeight: 600 }}>{cam.name}</TableCell>
                        <TableCell>
                          <Tooltip title={cam.rtsp_url} placement="top">
                            <Typography
                              variant="caption"
                              sx={{
                                fontFamily: 'monospace',
                                color: 'text.secondary',
                                display: 'block',
                                maxWidth: 200,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {cam.rtsp_url}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <CameraStatusChip
                            name={cam.name}
                            activeSource={activeSource?.name ?? ''}
                          />
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                          {format(new Date(cam.created_at), 'dd MMM yyyy')}
                        </TableCell>
                        <TableCell align="right">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<PlayArrowIcon />}
                            disabled={
                              setActiveMutation.isPending ||
                              activeSource?.name === cam.name
                            }
                            onClick={() => setActiveMutation.mutate(cam.name)}
                          >
                            Set Active
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
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
