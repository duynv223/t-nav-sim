<template>
  <SidebarProvider>
    <AppSidebar @tab-change="handleTabChange" />
    
    <main class="flex-1 flex flex-col">
      <header class="flex h-14 shrink-0 items-center gap-2 border-b px-4 bg-white">
        <SidebarTrigger class="-ml-1" />
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-gray-900">{{ workspaceTitle }}</span>
          <span class="text-xs text-gray-400">•</span>
          <span class="text-xs text-gray-500">Simulator v1.0</span>
        </div>
      </header>
      
      <!-- Route Simulation Workspace -->
      <RouteSimulationWorkspace
        v-show="activeTab === 'simulation'"
        :route="route"
        :mode="mode"
        :live="live"
        :simState="simState"
        :simStatus="simStatus"
        :simMode="simMode"
        :speedMultiplier="speedMultiplier"
        :onModeChange="(newMode) => mode = newMode"
        :onSimModeChange="(newSimMode) => simMode = newSimMode"
        :onSpeedMultiplierChange="(newMultiplier) => speedMultiplier = newMultiplier"
        :onReset="resetRoute"
        :onRun="runSim"
        :onRunFromSegment="runSimFromSegment"
        :onStop="stopSim"
        :onSelectWaypoint="onSelectWaypoint"
        :onSelectSegment="onSelectSegment"
        :onAddWaypoint="onAddWaypoint"
        :onDeleteWaypoint="onDeleteWaypoint"
        :onMoveWaypoint="onMoveWaypoint"
      />
      
      <!-- Settings Workspace -->
      <SettingsPanel v-show="activeTab === 'settings'" />
    </main>
  </SidebarProvider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import RouteSimulationWorkspace from './components/RouteSimulationWorkspace.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Route } from './types/route'

const activeTab = ref('simulation')

function handleTabChange(tab: string) {
  activeTab.value = tab
}

const workspaceTitle = computed(() => {
  switch (activeTab.value) {
    case 'simulation': return 'Route Simulation'
    case 'settings': return 'Settings'
    default: return 'Simulator'
  }
})

const route = ref(new Route())
const live = ref<any>({})
const mode = ref<'view'|'add'>('view')
const mapReady = ref(false)
const simState = ref<'idle' | 'running' | 'paused' | 'stopped'>('idle')
const simMode = ref<'demo' | 'live'>('demo')  // Simulation mode: demo (fast visualization) or live (real GPS)
const simStatus = ref<{ stage: string; detail?: string } | null>(null)
const speedMultiplier = ref(10.0)  // Speed multiplier for demo mode

// Computed properties for template
const waypoints = computed(() => route.value.points.map(p => ({ lat: p.lat, lon: p.lon })))
const segments = computed(() => route.value.segments)
const selectedSegmentIdx = computed(() => route.value.segments.findIndex(s => s.isSelected))

// ESC key handler
function handleKeyDown(e: KeyboardEvent){
  if(e.key === 'Escape'){
    mode.value = 'view'
    route.value.deselectAll()
  } else if(e.key === 'Delete' || e.key === 'Backspace'){
    const selectedIdx = route.value.points.findIndex(p => p.isSelected)
    if(selectedIdx >= 0){
      route.value.deletePoint(selectedIdx)
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('load-route', handleLoadRoute as EventListener)
  window.addEventListener('map-ready', handleMapReady as EventListener)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('load-route', handleLoadRoute as EventListener)
  window.removeEventListener('map-ready', handleMapReady as EventListener)
  
  // Close WebSocket connection
  if (ws) {
    console.log('[App] Closing WebSocket on unmount')
    ws.close()
    ws = null
  }
})

// Handle map ready event
function handleMapReady() {
  console.log('[App] Map is ready')
  mapReady.value = true
  
  // Load route from backend after map is ready
  loadRouteFromBackend()
  
  // Fetch initial simulation state
  fetchSimState()
  
  // Connect WebSocket after map is ready
  connectWs()
}

// Fetch initial simulation state from backend
async function fetchSimState() {
  try {
    const response = await fetch(`${backendUrl}/sim/status`)
    if (response.ok) {
      const data = await response.json()
      if (data.state) {
        simState.value = data.state
        console.log('[App] Initial simulation state:', data.state)
      }
    }
  } catch (err) {
    console.error('[App] Failed to fetch simulation state:', err)
  }
}

// Handle load-route event from RouteControlPanel
function handleLoadRoute(event: CustomEvent) {
  const data = event.detail
  
  if (!data || !data.waypoints || !data.segments) {
    console.error('Invalid route data')
    return
  }
  
  // Create new route from loaded data
  const newRoute = new Route()
  
  // Add waypoints
  data.waypoints.forEach((wp: { lat: number, lon: number }) => {
    newRoute.addPoint(wp.lat, wp.lon)
  })
  
  // Update segments with loaded data
  data.segments.forEach((seg: any) => {
    const segIdx = newRoute.segments.findIndex(s => s.from === seg.from && s.to === seg.to)
    if (segIdx >= 0) {
      // Support both new format (speedProfile) and legacy formats
      if (seg.speedProfile) {
        newRoute.segments[segIdx].speedProfile = seg.speedProfile
      } else if (seg.speed !== undefined && seg.endSpeed !== undefined) {
        // Convert old format (speed/endSpeed) to ramp_to profile
        newRoute.segments[segIdx].speedProfile = {
          type: 'ramp_to',
          params: {
            target_kmh: seg.endSpeed
          }
        }
      }
    }
  })
  
  // Set route ID
  newRoute.routeId = data.routeId || 'Loaded Route'
  
  // Assign to reactive ref
  route.value = newRoute
  
  // Switch to view mode after loading
  mode.value = 'view'
  
  // Trigger map re-render after route is loaded
  setTimeout(() => {
    const renderEvent = new CustomEvent('route-loaded')
    window.dispatchEvent(renderEvent)
  }, 100)
  
  // Focus map on first point if available
  if (newRoute.points.length > 0) {
    const firstPoint = newRoute.points[0]
    const focusEvent = new CustomEvent('map-focus', { 
      detail: { lat: firstPoint.lat, lon: firstPoint.lon, zoom: 14 } 
    })
    window.dispatchEvent(focusEvent)
  }
}

function onAddWaypoint(pt:{lat:number,lon:number}){
  route.value.addPoint(pt.lat, pt.lon)
}

function onDeleteWaypoint(idx:number){
  route.value.deletePoint(idx)
}

function onMoveWaypoint(idx:number, pt:{lat:number,lon:number}){
  route.value.movePoint(idx, pt.lat, pt.lon)
}

function onSelectWaypoint(idx:number){
  route.value.selectPoint(idx)
}

function onSelectSegment(idx:number){
  route.value.selectSegment(idx)
}

const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
let syncTimeout: ReturnType<typeof setTimeout> | null = null

// Load route from backend (on app mount/reload)
async function loadRouteFromBackend() {
  if (!mapReady.value) {
    console.log('[App] Waiting for map to be ready before loading route...')
    return
  }
  
  try {
    const response = await fetch(`${backendUrl}/route`)
    
    if (response.status === 404) {
      // No active route on backend, that's fine
      console.log('No active route found on backend')
      return
    }
    
    if (!response.ok) {
      throw new Error(`Failed to load route: ${response.status}`)
    }
    
    const data = await response.json()
    console.log('Loaded route from backend:', data.routeId)
    
    // Use the same load logic as file load
    const event = new CustomEvent('load-route', { detail: data })
    handleLoadRoute(event)
  } catch (err) {
    console.error('Failed to load route from backend:', err)
  }
}

// Auto-sync route changes to backend (debounced)
async function syncRouteToBackend() {
  if (route.value.points.length < 2) return // Don't sync incomplete routes
  
  const body = {
    routeId: route.value.routeId || 'active-route',
    ...route.value.toBackendFormat()
  }
  
  try {
    await fetch(`${backendUrl}/route`, {
      method: 'PUT',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(body)
    })
  } catch (err) {
    console.error('Failed to sync route:', err)
  }
}

function debouncedSync() {
  if (syncTimeout) clearTimeout(syncTimeout)
  syncTimeout = setTimeout(syncRouteToBackend, 500) // Debounce 500ms
}

// Watch route changes and sync
watch(() => route.value, debouncedSync, { deep: true })
watch(() => simMode.value, () => {
  simStatus.value = null
})

async function runSim(){
  if(route.value.points.length < 2){ alert('Add at least two waypoints'); return }
  simStatus.value = null
  
  // Ensure route is synced before running
  await syncRouteToBackend()
  
  const body = {
    startSegmentIdx: 0,
    endSegmentIdx: null, // Run all segments
    mode: simMode.value,
    speedMultiplier: simMode.value === 'demo' ? speedMultiplier.value : 1.0
  }
  
  try {
    const response = await fetch(`${backendUrl}/sim/run`, {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      const error = await response.json()
      alert(`Failed to start simulation: ${error.detail}`)
      return
    }
    
    const result = await response.json()
    // Update state from backend response
    if (result.state) {
      simState.value = result.state
    }
    
    // Start simulation tracking to lock segments
    route.value.startSimulation(body.startSegmentIdx, body.endSegmentIdx)
  } catch (err) {
    console.error('Failed to start simulation:', err)
    alert('Failed to start simulation')
  }
}

async function runSimFromSegment(){
  const selectedIdx = route.value.segments.findIndex(s => s.isSelected)
  if (selectedIdx < 0) {
    alert('Please select a segment first')
    return
  }
  simStatus.value = null
  
  // Ensure route is synced before running
  await syncRouteToBackend()
  
  const body = {
    startSegmentIdx: selectedIdx,
    endSegmentIdx: null, // Run to the end
    mode: simMode.value,
    speedMultiplier: simMode.value === 'demo' ? speedMultiplier.value : 1.0
  }
  
  try {
    const response = await fetch(`${backendUrl}/sim/run`, {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      const error = await response.json()
      alert(`Failed to start simulation: ${error.detail}`)
      return
    }
    
    const result = await response.json()
    // Update state from backend response
    if (result.state) {
      simState.value = result.state
    }
    
    // Start simulation tracking to lock segments from selected index
    route.value.startSimulation(body.startSegmentIdx, body.endSegmentIdx)
  } catch (err) {
    console.error('Failed to start simulation:', err)
    alert('Failed to start simulation')
  }
}

async function stopSim(){
  try {
    const response = await fetch(`${backendUrl}/sim/stop`, { method:'POST' })
    if (response.ok) {
      const result = await response.json()
      if (result.state) {
        simState.value = result.state
      }
      
      // Stop simulation tracking to unlock segments
      route.value.stopSimulation()
    }
  } catch (err) {
    console.error('Failed to stop simulation:', err)
  }
}

function resetRoute(){
  route.value = new Route()
}

// WebSocket live updates (connect to backend)
const backendHost = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const wsUrl = backendHost.replace('http', 'ws') + '/ws/sim'
let ws: WebSocket | null = null
let wsConnected = ref(false)

function connectWs(){
  // Only connect if map is ready
  if (!mapReady.value) {
    console.log('[App] Waiting for map before connecting WebSocket...')
    return
  }
  
  try{
    console.log('[App] Connecting WebSocket...')
    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('[App] WebSocket connected')
      wsConnected.value = true
      try {
        ws?.send(JSON.stringify({ type: 'subscribe', topics: ['state', 'data', 'status'] }))
      } catch (err) {
        console.error('[App] Failed to send subscribe message:', err)
      }
    }
    
    ws.onmessage = (ev)=>{
      try{ 
        const data = JSON.parse(ev.data)
        
        // Handle message based on type
        if (data.type === 'state') {
          // State change message
          const oldState = simState.value
          simState.value = data.state
          console.log('[App] State changed:', oldState, '→', data.state)
          
          // Clear locks when simulation stops (from any source)
          if ((oldState === 'running' || oldState === 'paused') && 
              (data.state === 'idle' || data.state === 'stopped')) {
            console.log('[App] Clearing simulation locks')
            route.value.stopSimulation()
          }
        } else if (data.type === 'status') {
          simStatus.value = {
            stage: data.stage || 'unknown',
            detail: data.detail
          }
        } else if (data.type === 'data') {
          // Simulation data message
          live.value = data
          route.value.updateSegmentStates(data.lat, data.lon)
        }
      }catch(e){}
    }
    
    ws.onclose = ()=>{ 
      console.log('[App] WebSocket disconnected, reconnecting...')
      wsConnected.value = false
      setTimeout(connectWs, 1000) 
    }
    
    ws.onerror = (err) => {
      console.error('[App] WebSocket error:', err)
    }
  }catch(e){ 
    console.error('[App] Failed to create WebSocket:', e)
    setTimeout(connectWs, 1000) 
  }
}

// Don't auto-connect on mount - wait for map-ready event

// expose to MapView
const onAddWaypointRef = onAddWaypoint
</script>

<style scoped>
/* minimal */
</style>
