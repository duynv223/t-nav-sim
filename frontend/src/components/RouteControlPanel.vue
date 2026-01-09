<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { Route as MapRoute } from '@/types/route'
import { MapPinPlus, Trash2, Play, Square, Pause, SkipForward, ChevronDown, Download, Upload, LocateFixed } from 'lucide-vue-next'

const props = defineProps<{
  route: MapRoute
  mode: 'view' | 'add'
  live: any
  simState: 'idle' | 'running' | 'paused' | 'stopped'
  simStatus: { stage: string; detail?: string } | null
  simMode: 'demo' | 'live'
  speedMultiplier: number
  onModeChange: (mode: 'view' | 'add') => void
  onReset: () => void
  onRun: () => void
  onRunFromSegment: () => void
  onStop: () => void
  onSimModeChange: (simMode: 'demo' | 'live') => void
  onSpeedMultiplierChange: (multiplier: number) => void
  onSelectWaypoint: (idx: number) => void
  onSelectSegment: (idx: number) => void
  onFocusStart: () => void
}>()

const showClearConfirm = ref(false)
const isPointsCollapsed = ref(true)
const isSegmentsCollapsed = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// Check if a segment is selected
const hasSelectedSegment = computed(() => {
  return props.route.segments.some(s => s.isSelected)
})

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

function buildRouteData() {
  return {
    routeId: props.route.routeId || `Route-${Date.now()}`,
    waypoints: props.route.points.map(p => ({ lat: p.lat, lon: p.lon })),
    segments: props.route.segments.map(s => ({
      from: s.from,
      to: s.to,
      speedProfile: s.speedProfile
    }))
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
    
    // Use file name as routeId if data.routeId is default/empty
    const fileName = file.name.replace('.json', '')
    if (!data.routeId || data.routeId === 'Untitled Route' || data.routeId.startsWith('Route-')) {
      data.routeId = fileName
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

// Helper function to initialize speed profile params based on type
function initializeProfileParams(type: string): any {
  switch(type) {
    case 'constant':
      return { speed_kmh: 25 }
    case 'ramp_to':
      return { target_kmh: 50 }
    case 'cruise_to':
      return { speed_kmh: 50 }
    case 'stop_at_end':
      return { stop_duration_s: 3 }
    default:
      return { speed_kmh: 25 }
  }
}

// Watch for profile type changes and reset params
watch(() => props.route.segments.map(s => s.speedProfile.type), (newTypes, oldTypes) => {
  if (!oldTypes) return
  
  props.route.segments.forEach((seg, idx) => {
    if (oldTypes[idx] && newTypes[idx] !== oldTypes[idx]) {
      // Profile type changed, reset params
      seg.speedProfile.params = initializeProfileParams(newTypes[idx])
    }
  })
}, { deep: true })
</script>

<template>
  <div class="flex flex-col h-full w-80 border-r border-gray-200 bg-white">

    <div class="flex-1 overflow-y-auto">
      <!-- Route File Management Section -->
      <div class="p-4 border-b border-gray-200 bg-gray-50">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-sm font-semibold text-gray-900">Route File</h4>
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
            @click="handleClear"
            :disabled="route.points.length === 0"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors',
              route.points.length === 0
                ? 'bg-gray-50 text-gray-300 cursor-not-allowed'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
            :title="route.points.length === 0 ? 'No points to clear' : 'Clear all waypoints and segments'">
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
                <th class="border border-gray-200 px-2 py-1 text-left font-semibold">
                  Speed Profile
                </th>
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
                  <!-- Profile Type Selector -->
                  <select 
                    v-model="seg.speedProfile.type" 
                    class="w-full px-1 py-0.5 border border-gray-300 rounded text-xs mb-1"
                    @click.stop>
                    <option value="constant">Constant</option>
                    <option value="ramp_to">Ramp To</option>
                    <option value="cruise_to">Cruise To</option>
                    <option value="stop_at_end">Stop at End</option>
                  </select>
                  
                  <!-- Constant Profile -->
                  <div v-if="seg.speedProfile.type === 'constant'" class="flex gap-1 items-center" @click.stop>
                    <label class="text-[10px] text-gray-600">Speed:</label>
                    <input 
                      type="number" 
                      v-model.number="seg.speedProfile.params.speed_kmh" 
                      step="1"
                      min="0"
                      class="w-14 px-1 py-0.5 border border-gray-300 rounded text-xs text-center" 
                    />
                    <span class="text-[10px] text-gray-500">km/h</span>
                  </div>
                  
                  <!-- Ramp To Profile -->
                  <div v-if="seg.speedProfile.type === 'ramp_to'" class="flex gap-1 items-center" @click.stop>
                    <label class="text-[10px] text-gray-600">Target:</label>
                    <input 
                      type="number" 
                      v-model.number="seg.speedProfile.params.target_kmh" 
                      step="1"
                      min="0"
                      class="w-14 px-1 py-0.5 border border-gray-300 rounded text-xs text-center" 
                    />
                    <span class="text-[10px] text-gray-500">km/h</span>
                  </div>
                  
                  <!-- Cruise To Profile -->
                  <div v-if="seg.speedProfile.type === 'cruise_to'" class="flex gap-1 items-center" @click.stop>
                    <label class="text-[10px] text-gray-600">Speed:</label>
                    <input 
                      type="number" 
                      v-model.number="seg.speedProfile.params.speed_kmh" 
                      step="1"
                      min="0"
                      class="w-14 px-1 py-0.5 border border-gray-300 rounded text-xs text-center" 
                    />
                    <span class="text-[10px] text-gray-500">km/h</span>
                  </div>
                  
                  <!-- Stop at End Profile -->
                  <div v-if="seg.speedProfile.type === 'stop_at_end'" class="flex gap-1 items-center" @click.stop>
                    <label class="text-[10px] text-gray-600">Stop:</label>
                    <input 
                      type="number" 
                      v-model.number="seg.speedProfile.params.stop_duration_s" 
                      step="0.5"
                      min="0"
                      class="w-14 px-1 py-0.5 border border-gray-300 rounded text-xs text-center" 
                    />
                    <span class="text-[10px] text-gray-500">s</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="mt-2 text-xs text-gray-500 italic">
            💡 Select profile type and configure parameters for each segment
          </div>
          </div>
        </div>
      </div>

      <!-- Simulation Control Section -->
      <div class="p-4 border-b border-gray-200">
        <h4 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span class="w-1 h-4 bg-green-600 rounded"></span>
          Simulation Control
        </h4>
        
        <!-- Simulation Mode Selection -->
        <div class="mb-3">
          <label class="block text-xs font-medium text-gray-700 mb-2">Simulation Mode</label>
          <div class="flex gap-3">
            <label class="flex items-center gap-2 cursor-pointer">
              <input 
                type="radio" 
                name="sim-mode"
                value="demo"
                :checked="props.simMode === 'demo'"
                @change="props.onSimModeChange('demo')"
                :disabled="props.simState === 'running'"
                class="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <span class="text-sm text-gray-700" :class="{ 'opacity-50': props.simState === 'running' }">
                Demo
              </span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input 
                type="radio" 
                name="sim-mode"
                value="live"
                :checked="props.simMode === 'live'"
                @change="props.onSimModeChange('live')"
                :disabled="props.simState === 'running'"
                class="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <span class="text-sm text-gray-700" :class="{ 'opacity-50': props.simState === 'running' }">
                Live
              </span>
            </label>
          </div>
        </div>
        
        <!-- Speed Multiplier (only for Demo mode) -->
        <div v-if="props.simMode === 'demo'" class="mb-3">
          <label class="block text-xs font-medium text-gray-700 mb-1">Speed Multiplier</label>
          <div class="flex items-center gap-2">
            <input 
              type="range" 
              min="1" 
              max="50" 
              step="1"
              :value="props.speedMultiplier"
              @input="(e) => props.onSpeedMultiplierChange(Number((e.target as HTMLInputElement).value))"
              :disabled="props.simState === 'running'"
              class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <span class="text-sm font-medium text-gray-700 w-12 text-right">{{ props.speedMultiplier }}×</span>
          </div>
          <div class="mt-1 text-xs text-gray-500">1× = real-time, higher = faster visualization</div>
        </div>
        
        <!-- Status Bar -->
        <div class="mb-3 px-3 py-2 rounded-md border border-gray-300 bg-gray-50">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full" :class="{
                'bg-gray-400': props.simState === 'idle' || props.simState === 'stopped',
                'bg-gray-600 animate-pulse': props.simState === 'running',
                'bg-gray-500': props.simState === 'paused'
              }"></div>
              <span class="text-xs font-medium text-gray-700">
                {{ props.simState.toUpperCase() }}
              </span>
              <span v-if="props.simState === 'running'" class="text-xs font-medium" :class="{
                'text-blue-600': props.simMode === 'demo',
                'text-green-600': props.simMode === 'live'
              }">
                [{{ props.simMode === 'demo' ? `${props.speedMultiplier}×` : 'LIVE' }}]
              </span>
            </div>
            <span v-if="props.live?.segmentIdx !== undefined" class="text-xs text-gray-600">
              Seg {{ props.live.segmentIdx + 1 }}/{{ props.route.segments.length }}
            </span>
          </div>
          <div v-if="props.simStatus" class="mt-1 text-[11px] text-gray-600">
            Status: <span class="font-medium text-gray-700">{{ props.simStatus.stage }}</span>
            <span v-if="props.simStatus.detail">- {{ props.simStatus.detail }}</span>
          </div>
        </div>
        
        <div class="flex flex-wrap gap-2">
          <button 
            @click="onRun"
            :disabled="route.points.length < 2 || props.simState === 'running'"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors border',
              route.points.length < 2 || props.simState === 'running'
                ? 'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400'
            ]"
            :title="route.points.length < 2 ? 'Add at least 2 points to run' : props.simState === 'running' ? 'Simulation already running' : 'Start simulation'">
            <Play :size="18" />
          </button>
          
          <button 
            :disabled="true"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors border',
              'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed'
            ]"
            title="Pause simulation (coming soon)">
            <Pause :size="18" />
          </button>
          
          <button 
            @click="onStop"
            :disabled="props.simState !== 'running'"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors border',
              props.simState !== 'running'
                ? 'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400'
            ]"
            title="Stop simulation">
            <Square :size="18" />
          </button>
          
          <button
            @click="props.onRunFromSegment"
            :disabled="props.simState === 'running' || !hasSelectedSegment"
            :class="[
              'h-10 w-10 flex items-center justify-center rounded-md transition-colors border',
              props.simState === 'running' || !hasSelectedSegment
                ? 'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed'
                : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50 hover:border-gray-400 cursor-pointer'
            ]"
            :title="hasSelectedSegment ? 'Run from selected segment' : 'Select a segment first'">
            <SkipForward :size="18" />
          </button>
        </div>
        
        <div class="mt-2 text-xs text-gray-500 text-center">
          {{ route.points.length < 2 ? 'Add at least 2 points' : 'Ready' }}
        </div>
      </div>

      <!-- Simulation Data Section -->
      <div class="p-4">
        <h4 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span class="w-1 h-4 bg-red-600 rounded"></span>
          Simulation Data
        </h4>
        <div class="space-y-1 text-xs">
          <div class="flex justify-between">
            <span class="text-gray-600">t:</span>
            <span class="font-mono">{{ live.t ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">lat:</span>
            <span class="font-mono">{{ live.lat ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">lon:</span>
            <span class="font-mono">{{ live.lon ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">speed:</span>
            <span class="font-mono">{{ live.speed ?? '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">bearing:</span>
            <span class="font-mono">{{ live.bearing ?? '-' }}</span>
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
