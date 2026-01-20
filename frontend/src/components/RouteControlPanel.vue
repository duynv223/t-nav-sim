<script setup lang="ts">
import { ref, watch, nextTick, computed, onBeforeUnmount } from 'vue'
import { Route as MapRoute } from '@/types/route'
import { MapPinPlus, Trash2, Play, Square, ChevronDown, Download, Upload, LocateFixed, Loader2, Info } from 'lucide-vue-next'

const props = defineProps<{
  route: MapRoute
  mode: 'view' | 'add'
  telemetry: any
  simState: 'idle' | 'running' | 'paused' | 'stopped'
  simStatus: { stage: string; detail?: string } | null
  onModeChange: (mode: 'view' | 'add') => void
  onReset: () => void
  onRun: () => void
  onRunFromSegment: () => void
  onStop: () => void
  onSelectWaypoint: (idx: number) => void
  onSelectSegment: (idx: number) => void
  onFocusStart: () => void
  onSplitSegment: () => void
}>()

const showClearConfirm = ref(false)
const isPointsCollapsed = ref(true)
const isSegmentsCollapsed = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const activeTab = ref<'route' | 'simulation'>('route')
// Check if a segment is selected
const hasSelectedSegment = computed(() => {
  return props.route.segments.some(s => s.isSelected)
})

type BuildStatus = 'none' | 'building' | 'outdated' | 'completed'
type RunStatus = 'idle' | 'building' | 'waiting' | 'running'

const buildStartTime = ref('2026-01-20 02:00:00')
const buildStartEnabled = ref(false)
const runStartTime = ref('2026-01-20 02:05:00')
const realtime = ref(false)
const gpsOnly = ref(false)
const buildStatus = ref<BuildStatus>('none')
const runStatus = ref<RunStatus>('idle')
const buildProgress = ref({ current: 1, total: 20 })
const runningTime = ref(32.4)
const sessionId = ref<string | null>(null)
const buildAbort = ref<AbortController | null>(null)
const buildJobId = ref<string | null>(null)
const buildPollTimer = ref<number | null>(null)

const apiBaseUrl = import.meta.env.VITE_SIM_API_URL || 'http://localhost:8000'

const buildRunning = computed(() => buildStatus.value === 'building')
const runDisabled = computed(() => buildRunning.value)

const buildStatusLabel = computed(() => {
  switch (buildStatus.value) {
    case 'none':
      return 'None'
    case 'building':
      return `Building (${buildProgress.value.current}/${buildProgress.value.total})`
    case 'completed':
      return 'Build completed'
    case 'outdated':
      return 'Outdated'
    default:
      return 'None'
  }
})

const runStatusLabel = computed(() => {
  switch (runStatus.value) {
    case 'idle':
      return 'Idle'
    case 'building':
      return 'Building'
    case 'waiting':
      return 'Waiting for start time'
    case 'running':
      return `Running (t = ${runningTime.value.toFixed(1)}s)`
    default:
      return 'Idle'
  }
})

let scenarioInitialized = false
watch(() => props.route, () => {
  if (!scenarioInitialized) {
    scenarioInitialized = true
    return
  }
  if (!buildRunning.value) {
    buildStatus.value = 'outdated'
    sessionId.value = null
    buildJobId.value = null
    stopBuildPolling()
  }
}, { deep: true })

function formatDateTime(value: Date) {
  const pad = (num: number) => num.toString().padStart(2, '0')
  const year = value.getFullYear()
  const month = pad(value.getMonth() + 1)
  const day = pad(value.getDate())
  const hours = pad(value.getHours())
  const minutes = pad(value.getMinutes())
  const seconds = pad(value.getSeconds())
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

watch(buildStartEnabled, (enabled) => {
  if (enabled) {
    buildStartTime.value = formatDateTime(new Date())
  }
})

onBeforeUnmount(() => {
  if (buildAbort.value) {
    buildAbort.value.abort()
    buildAbort.value = null
  }
  stopBuildPolling()
})

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  const response = await fetch(`${apiBaseUrl}/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: props.route.routeId || undefined })
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || 'Failed to create session')
  }
  const data = await response.json()
  sessionId.value = data.session_id
  return sessionId.value
}

async function sendGenRequest(id: string, controller: AbortController) {
  const response = await fetch(`${apiBaseUrl}/sessions/${id}/gen`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(buildPayload()),
    signal: controller.signal
  })
  return response
}

function startBuildPolling() {
  stopBuildPolling()
  buildPollTimer.value = window.setInterval(async () => {
    if (!sessionId.value || !buildJobId.value) return
    try {
      const response = await fetch(`${apiBaseUrl}/sessions/${sessionId.value}/gen/${buildJobId.value}`)
      if (!response.ok) return
      const job = await response.json()
      handleBuildJob(job)
    } catch (err) {
      console.error('Failed to poll build status:', err)
    }
  }, 1000)
}

function stopBuildPolling() {
  if (buildPollTimer.value !== null) {
    window.clearInterval(buildPollTimer.value)
    buildPollTimer.value = null
  }
}

function handleBuildJob(job: any) {
  buildJobId.value = job.job_id || buildJobId.value
  switch (job.status) {
    case 'running':
    case 'pending':
      buildStatus.value = 'building'
      break
    case 'completed':
      buildStatus.value = 'completed'
      stopBuildPolling()
      break
    case 'failed':
      buildStatus.value = 'none'
      stopBuildPolling()
      alert(`Build failed: ${job.error || 'Unknown error'}`)
      break
    case 'canceled':
      buildStatus.value = 'none'
      stopBuildPolling()
      break
    default:
      break
  }
}

function buildPayload() {
  const scenario = {
    meta: {
      name: props.route.routeId || undefined
    },
    route: {
      points: props.route.points.map(p => ({ lat: p.lat, lon: p.lon }))
    },
    motion_profile: {
      type: props.route.motionProfile.type,
      params: props.route.motionProfile.params
    }
  }
  return {
    schema_version: 1,
    scenario,
    dt_s: 0.1,
    start_time: buildStartEnabled.value ? buildStartTime.value : undefined,
    outputs: {
      motion_csv: 'motion.csv',
      iq: 'route.iq'
    }
  }
}

async function startBuild() {
  if (buildRunning.value) return
  if (props.route.points.length < 2) {
    alert('Add at least two points')
    return
  }
  buildStatus.value = 'building'
  buildProgress.value = { current: 1, total: 1 }

  const controller = new AbortController()
  buildAbort.value = controller

  try {
    let id = await ensureSession()
    let response = await sendGenRequest(id, controller)
    if (response.status === 404) {
      sessionId.value = null
      id = await ensureSession()
      response = await sendGenRequest(id, controller)
    }
    if (!response.ok) {
      const error = await response.text()
      throw new Error(error || 'Build failed')
    }
    const job = await response.json()
    handleBuildJob(job)
    if (job.status === 'running' || job.status === 'pending') {
      startBuildPolling()
    }
  } catch (err: any) {
    if (controller.signal.aborted) {
      buildStatus.value = 'none'
      return
    }
    console.error('Build failed:', err)
    alert(`Build failed: ${err?.message || err}`)
    buildStatus.value = 'none'
  } finally {
    buildAbort.value = null
  }
}

async function cancelBuild() {
  if (buildAbort.value) {
    buildAbort.value.abort()
  }
  stopBuildPolling()
  if (sessionId.value && buildJobId.value) {
    try {
      await fetch(`${apiBaseUrl}/sessions/${sessionId.value}/gen/${buildJobId.value}/cancel`, {
        method: 'POST'
      })
    } catch (err) {
      console.error('Failed to cancel build:', err)
    }
  }
  buildJobId.value = null
  buildStatus.value = 'none'
}

function handleClear() {
  showClearConfirm.value = true
}

function confirmClear() {
  props.onReset()
  showClearConfirm.value = false
}

function cancelClear() {
  showClearConfirm.value = false
}

// Save/Load route to/from file
async function saveRoute() {
  if (props.route.points.length < 2) {
    alert('Route must have at least 2 points')
    return
  }
  
  const defaultName = props.route.routeId || `Route-${Date.now()}`
  
  // Use File System Access API (native Windows file dialog)
  if ('showSaveFilePicker' in window) {
    try {
      const handle = await (window as any).showSaveFilePicker({
        suggestedName: `${defaultName}.json`,
        types: [{
          description: 'Route JSON Files',
          accept: { 'application/json': ['.json'] }
        }],
        excludeAcceptAllOption: false
      })
      
      // Update route name from saved file
      const fileName = handle.name.replace('.json', '')
      props.route.routeId = fileName
      
      // Build and save route data
      const routeData = buildRouteData()
      const json = JSON.stringify(routeData, null, 2)
      const writable = await handle.createWritable()
      await writable.write(json)
      await writable.close()
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Failed to save file:', err)
        alert('Failed to save file. Please try again.')
      }
    }
    return
  }
  
  // Fallback: traditional download for unsupported browsers
  alert('Your browser does not support file picker. File will be downloaded to default folder.')
  const routeData = buildRouteData()
  const json = JSON.stringify(routeData, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${defaultName}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const ROUTE_SCHEMA_VERSION = 1
const ROUTE_APP_VERSION = '0.1'

function buildRouteData() {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `route-${Date.now()}`

  const scenarioName = props.route.routeId || `Scenario-${Date.now()}`

  return {
    schema_version: ROUTE_SCHEMA_VERSION,
    scenario: {
      meta: {
        id,
        created_at: new Date().toISOString(),
        app_version: ROUTE_APP_VERSION,
        name: scenarioName
      },
      route: {
        points: props.route.points.map(p => ({ lat: p.lat, lon: p.lon }))
      },
      motion_profile: props.route.motionProfile
    }
  }
}

function triggerLoadFile() {
  fileInputRef.value?.click()
}

async function loadRouteFromFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    
    // Use file name as scenario name if missing
    const fileName = file.name.replace('.json', '')
    if (data?.scenario?.meta && !data.scenario.meta.name) {
      data.scenario.meta.name = fileName
    }
    
    // Emit loaded route data to parent
    const loadEvent = new CustomEvent('load-route', { detail: data })
    window.dispatchEvent(loadEvent)
  } catch (err) {
    console.error('Failed to load route file:', err)
    alert('Failed to load route file. Please check the file format.')
  } finally {
    // Reset input to allow loading same file again
    input.value = ''
  }
}

// Auto-scroll to selected waypoint
watch(() => props.route.points.findIndex(p => p.isSelected), (selectedIdx) => {
  if (selectedIdx >= 0 && !isPointsCollapsed.value) {
    nextTick(() => {
      const row = document.querySelector(`[data-point-idx="${selectedIdx}"]`)
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    })
  }
})

// Auto-scroll to selected segment
watch(() => props.route.segments.findIndex(s => s.isSelected), (selectedIdx) => {
  if (selectedIdx >= 0 && !isSegmentsCollapsed.value) {
    nextTick(() => {
      const row = document.querySelector(`[data-segment-idx="${selectedIdx}"]`)
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    })
  }
})

// Auto-scroll to bottom when new point is added
watch(() => props.route.points.length, (newLen, oldLen) => {
  if (newLen > oldLen && newLen > 0 && !isPointsCollapsed.value) {
    nextTick(() => {
      const lastRow = document.querySelector(`[data-point-idx="${newLen - 1}"]`)
      if (lastRow) {
        lastRow.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }
    })
  }
})

// Auto-scroll to bottom when new segment is added
watch(() => props.route.segments.length, (newLen, oldLen) => {
  if (newLen > oldLen && newLen > 0 && !isSegmentsCollapsed.value) {
    nextTick(() => {
      const lastRow = document.querySelector(`[data-segment-idx="${newLen - 1}"]`)
      if (lastRow) {
        lastRow.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }
    })
  }
})

const METERS_PER_DEGREE = 111000

function formatSegmentDistance(seg: { from: number; to: number }) {
  const fromPoint = props.route.points[seg.from]
  const toPoint = props.route.points[seg.to]
  if (!fromPoint || !toPoint) return '-'
  const meters = Math.hypot(toPoint.lat - fromPoint.lat, toPoint.lon - fromPoint.lon) * METERS_PER_DEGREE
  return Math.round(meters).toString()
}
</script>

<template>
  <div class="flex flex-col h-full w-80 border-r border-gray-200 bg-white">
    <div class="border-b border-gray-200 bg-gray-50 p-2">
      <div class="flex gap-2">
        <button
          @click="activeTab = 'route'"
          :class="[
            'flex-1 px-3 py-2 text-xs font-semibold rounded-md transition-colors',
            activeTab === 'route'
              ? 'bg-white text-gray-900 border border-gray-200 shadow-sm'
              : 'bg-transparent text-gray-500 hover:text-gray-700'
          ]"
        >
          Scenario
        </button>
        <button
          @click="activeTab = 'simulation'"
          :class="[
            'flex-1 px-3 py-2 text-xs font-semibold rounded-md transition-colors',
            activeTab === 'simulation'
              ? 'bg-white text-gray-900 border border-gray-200 shadow-sm'
              : 'bg-transparent text-gray-500 hover:text-gray-700'
          ]"
        >
          Simulation
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div v-show="activeTab === 'route'">
      <!-- Route File Management Section -->
      <div class="p-4 border-b border-gray-200 bg-gray-50">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-sm font-semibold text-gray-900">Scenario</h4>
          <div class="flex gap-2">
            <button
              @click="saveRoute"
              :disabled="props.route.points.length < 2"
              class="h-8 px-3 flex items-center justify-center gap-1.5 rounded-md text-xs font-medium transition-colors"
              :class="props.route.points.length >= 2 ? 'bg-green-500 text-white hover:bg-green-600' : 'bg-gray-300 text-gray-500 cursor-not-allowed'"
              title="Save route to file">
              <Download :size="14" />
              Save
            </button>
            <button
              @click="triggerLoadFile"
              class="h-8 px-3 flex items-center justify-center gap-1.5 rounded-md bg-blue-500 text-white hover:bg-blue-600 transition-colors text-xs font-medium"
              title="Load route from file">
              <Upload :size="14" />
              Load
            </button>
          </div>
        </div>
        
        <input 
          ref="fileInputRef"
          type="file" 
          accept=".json"
          @change="loadRouteFromFile"
          class="hidden"
        />
        
        <div class="text-xs text-gray-500 mt-2">
          Current: <span class="font-medium text-gray-700">{{ props.route.routeId || 'Untitled' }}</span>
          <span class="text-gray-400 ml-1">({{ props.route.points.length }} points)</span>
        </div>
      </div>

      <!-- Route Editor Section -->
      <div class="p-4 border-b border-gray-200">
        <h4 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span class="w-1 h-4 bg-blue-600 rounded"></span>
          Route Editor
        </h4>
        
        <!-- Add Point Mode Toggle -->
        <div class="flex gap-2 mb-2">
          <button 
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors',
              mode === 'add' 
                ? 'bg-blue-500 text-white hover:bg-blue-600' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
            @click="onModeChange(mode === 'add' ? 'view' : 'add')"
            :title="mode === 'add' ? 'Exit add mode (ESC)' : 'Enable add point mode - click map to add waypoints'">
            <MapPinPlus :size="20" :class="mode === 'add' ? 'rotate-12' : ''" class="transition-transform" />
          </button>
          
          <button 
            @click="props.onSplitSegment"
            :disabled="!hasSelectedSegment"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors',
              !hasSelectedSegment
                ? 'bg-gray-50 text-gray-300 cursor-not-allowed'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
            :title="hasSelectedSegment ? 'Split selected segment' : 'Select a segment to split'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-5 w-5">
              <circle cx="6" cy="12" r="2"></circle>
              <circle cx="12" cy="12" r="2"></circle>
              <circle cx="18" cy="12" r="2"></circle>
              <line x1="8" y1="12" x2="10" y2="12"></line>
              <line x1="14" y1="12" x2="16" y2="12"></line>
            </svg>
          </button>

          <button 
            @click="handleClear"
            :disabled="route.points.length === 0 || props.simState === 'running'"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors',
              route.points.length === 0 || props.simState === 'running'
                ? 'bg-gray-50 text-gray-300 cursor-not-allowed'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
            :title="props.simState === 'running' ? 'Stop simulation to clear route' : (route.points.length === 0 ? 'No points to clear' : 'Clear all waypoints and segments')">
            <Trash2 :size="18" />
          </button>

          <button 
            @click="props.onFocusStart"
            :disabled="route.points.length === 0"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors',
              route.points.length === 0
                ? 'bg-gray-50 text-gray-300 cursor-not-allowed'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
            :title="route.points.length === 0 ? 'No start point available' : 'Focus map on start point'">
            <LocateFixed :size="18" />
          </button>
        </div>
      </div>

      <!-- Points Section -->
      <div class="p-4 border-b border-gray-200">
        <h4 
          class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2 cursor-pointer hover:text-gray-700 select-none"
          @click="isPointsCollapsed = !isPointsCollapsed">
          <span class="w-1 h-4 bg-purple-600 rounded"></span>
          Points ({{ route.points.length }})
          <ChevronDown :size="16" :class="['ml-auto transition-transform', isPointsCollapsed ? '-rotate-90' : '']" />
        </h4>
        <div v-if="!isPointsCollapsed">
          <div v-if="route.points.length === 0" class="text-sm text-gray-500">
            Click the map to add points.
          </div>
          <div v-else class="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table class="w-full text-xs border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">#</th>
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">Latitude</th>
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">Longitude</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(point, idx) in route.points" 
                :key="idx"
                :data-point-idx="idx"
                :class="['cursor-pointer transition-colors hover:bg-gray-50', point.isSelected ? 'bg-blue-100' : '']"
                @click="onSelectWaypoint(idx)">
                <td class="border border-gray-200 px-2 py-1">{{ idx }}</td>
                <td class="border border-gray-200 px-2 py-1">{{ point.lat.toFixed(6) }}</td>
                <td class="border border-gray-200 px-2 py-1">{{ point.lon.toFixed(6) }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>
      </div>

      <!-- Segments Section -->
      <div class="p-4 border-b border-gray-200">
        <h4 
          class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2 cursor-pointer hover:text-gray-700 select-none"
          @click="isSegmentsCollapsed = !isSegmentsCollapsed">
          <span class="w-1 h-4 bg-orange-600 rounded"></span>
          Segments ({{ route.segments.length }})
          <ChevronDown :size="16" :class="['ml-auto transition-transform', isSegmentsCollapsed ? '-rotate-90' : '']" />
        </h4>
        <div v-if="!isSegmentsCollapsed">
          <div v-if="route.segments.length === 0" class="text-sm text-gray-500">
            Add at least two waypoints by clicking the map.
          </div>
          <div v-else class="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table class="w-full text-xs border-collapse">
            <thead>
              <tr class="bg-gray-50">
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">#</th>
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">Route</th>
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">distance (m)</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(seg, idx) in route.segments" 
                :key="idx"
                :data-segment-idx="idx"
                :class="['cursor-pointer transition-colors hover:bg-gray-50', seg.isSelected ? 'bg-blue-100' : '']"
                @click="onSelectSegment(idx)">
                <td class="border border-gray-200 px-2 py-1">{{ idx }}</td>
                <td class="border border-gray-200 px-2 py-1">
                  <span class="font-mono">{{ seg.from }}→{{ seg.to }}</span>
                </td>
                <td class="border border-gray-200 px-2 py-1">
                  <span class="font-mono">{{ formatSegmentDistance(seg) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>
      </div>

      <!-- Motion Profile Section -->
      <div class="p-4 border-b border-gray-200">
        <h4 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span class="w-1 h-4 bg-teal-600 rounded"></span>
          Motion Profile
        </h4>
        <div class="space-y-3 text-xs">
          <div>
            <div class="text-gray-600 mb-1">Type</div>
            <select
              v-model="route.motionProfile.type"
              class="w-full px-2 py-1 border border-gray-300 rounded text-xs"
            >
              <option value="simple">Simple</option>
            </select>
          </div>
          <div class="grid gap-2">
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Cruise speed (km/h)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.cruise_speed_kmh"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Acceleration (m/s2)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.accel_mps2"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Deceleration (m/s2)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.decel_mps2"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Turn slowdown per degree</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.turn_slowdown_factor_per_deg"
                step="0.01"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Minimum turn speed (km/h)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.min_turn_speed_kmh"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Turn rate (deg/s)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.turn_rate_deg_s"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Start hold (s)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.start_hold_s"
                step="1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Start speed (km/h)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.start_speed_kmh"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
            <label class="flex items-center justify-between gap-2">
              <span class="text-gray-600">Start speed duration (s)</span>
              <input
                type="number"
                v-model.number="route.motionProfile.params.start_speed_s"
                step="0.1"
                min="0"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-xs text-right"
              />
            </label>
          </div>
        </div>
      </div>

      </div>

      <div v-show="activeTab === 'simulation'">
      <!-- Build Section -->
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <span class="w-1 h-4 bg-green-600 rounded"></span>
            Build
          </h4>
          <div class="flex items-center gap-2 text-xs text-gray-600">
            <span class="font-medium text-gray-700">Status:</span>
            <span>{{ buildStatusLabel }}</span>
            <Loader2 v-if="buildRunning" class="h-3 w-3 animate-spin text-gray-400" />
          </div>
        </div>

        <div class="flex items-center gap-3 text-xs text-gray-600">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              v-model="buildStartEnabled"
              class="h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <span class="font-medium text-gray-700">Start time</span>
            <input
              v-if="buildStartEnabled"
              v-model="buildStartTime"
              type="text"
              class="w-44 px-2 py-1 border border-gray-300 rounded text-xs"
            />
          </label>
          <span
            class="ml-auto text-gray-400"
            title="Start time for generated GPS signal"
            aria-label="Start time for generated GPS signal"
          >
            <Info class="h-4 w-4" />
          </span>
        </div>

        <div class="mt-3">
          <button
            @click="buildRunning ? cancelBuild() : startBuild()"
            :disabled="route.points.length < 2 && !buildRunning"
            class="inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium border transition-colors"
            :class="route.points.length < 2 && !buildRunning ? 'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
            title="Toggle build">
            <component :is="buildRunning ? Square : Play" :size="14" />
            <span>{{ buildRunning ? 'Cancel' : 'Build' }}</span>
          </button>
        </div>
      </div>

      <!-- Run Section -->
      <div class="p-4" :class="runDisabled ? 'opacity-50 pointer-events-none' : ''">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <span class="w-1 h-4 bg-blue-600 rounded"></span>
            Run
          </h4>
          <div class="flex items-center gap-2 text-xs text-gray-600">
            <span class="font-medium text-gray-700">Status:</span>
            <span>{{ runStatusLabel }}</span>
          </div>
        </div>

        <div class="flex items-center gap-4 text-xs text-gray-600">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              v-model="realtime"
              class="h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <span class="font-medium text-gray-700">Realtime GPS</span>
          </label>
          <span
            class="ml-auto text-gray-400"
            title="Automatically build simulation data and schedule playback at start time"
            aria-label="Automatically build simulation data and schedule playback at start time"
          >
            <Info class="h-4 w-4" />
          </span>
        </div>

        <div v-if="realtime" class="mt-2 flex items-center gap-3 text-xs text-gray-600">
          <label class="flex items-center gap-2">
            <span class="font-medium text-gray-700">Start time</span>
            <input
              v-model="runStartTime"
              type="text"
              class="w-44 px-2 py-1 border border-gray-300 rounded text-xs"
            />
          </label>
          <span
            class="ml-auto text-gray-400"
            title="Playback will start automatically at this time"
            aria-label="Playback will start automatically at this time"
          >
            <Info class="h-4 w-4" />
          </span>
        </div>

        <div class="mt-2 flex items-center gap-3 text-xs text-gray-600">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              v-model="gpsOnly"
              class="h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <span class="font-medium text-gray-700">GPS only</span>
          </label>
        </div>

        <div class="mt-3">
          <button
            class="inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium border transition-colors"
            :class="runStatus === 'running' ? 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
            title="Toggle run">
            <component :is="runStatus === 'running' ? Square : Play" :size="14" />
            <span>{{ runStatus === 'running' ? 'Stop' : 'Run' }}</span>
          </button>
        </div>
      </div>

      <!-- Current Motion Status -->
      <div class="p-4 border-t border-gray-200">
        <h4 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span class="w-1 h-4 bg-red-600 rounded"></span>
          Current Motion
        </h4>
        <div class="space-y-1 text-xs">
          <div class="flex justify-between">
            <span class="text-gray-600">t:</span>
            <span class="font-mono">{{ telemetry.t ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">lat:</span>
            <span class="font-mono">{{ telemetry.lat ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">lon:</span>
            <span class="font-mono">{{ telemetry.lon ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">speed:</span>
            <span class="font-mono">{{ telemetry.speed ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">bearing:</span>
            <span class="font-mono">{{ telemetry.bearing ?? '-' }}</span>
          </div>
        </div>
      </div>
    </div>
    </div>

    <!-- Clear Confirmation Modal -->
    <div v-if="showClearConfirm" class="absolute inset-0 bg-black/50 flex items-center justify-center z-50" @click="cancelClear">
      <div class="bg-white rounded-lg shadow-xl p-6 m-4 max-w-sm w-full" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Clear All Points?</h3>
        <p class="text-sm text-gray-600 mb-4">
          This will remove all waypoints and segments. This action cannot be undone.
        </p>
        <div class="flex gap-2 justify-end">
          <button 
            @click="cancelClear"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
            Cancel
          </button>
          <button 
            @click="confirmClear"
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors">
            Clear All
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
