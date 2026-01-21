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
        :telemetry="telemetry"
        :simState="simState"
        :simStatus="simStatus"
        :onTelemetryUpdate="updateTelemetry"
        :onModeChange="(newMode) => mode = newMode"
        :onReset="resetRoute"
        :onRun="runSim"
        :onRunFromSegment="runSimFromSegment"
        :onStop="stopSim"
        :onSelectWaypoint="onSelectWaypoint"
        :onSelectSegment="onSelectSegment"
        :onFocusStart="focusStart"
        :onSplitSegment="splitSelectedSegment"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
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
const telemetry = ref<any>({})
const mode = ref<'view'|'add'>('view')
const simState = ref<'idle' | 'running' | 'paused' | 'stopped'>('idle')
const simStatus = ref<{ stage: string; detail?: string } | null>(null)

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
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('load-route', handleLoadRoute as EventListener)
})

// Handle load-route event from RouteControlPanel
function handleLoadRoute(event: CustomEvent) {
  const data = event.detail
  if (!data || data.schema_version !== 1 || !Array.isArray(data.scenario?.route?.points)) {
    console.error('Invalid route data')
    return
  }

  const waypoints = data.scenario.route.points
  const motionProfile = data.scenario.motion_profile
  const routeId = data.scenario.meta?.name

  // Create new route from loaded data
  const newRoute = new Route()
  
  // Add waypoints
  waypoints.forEach((wp: { lat: number, lon: number }) => {
    newRoute.addPoint(wp.lat, wp.lon)
  })
  
  // Set route ID
  newRoute.routeId = routeId || 'Loaded Route'

  if (motionProfile && motionProfile.type === 'simple' && motionProfile.params) {
    newRoute.motionProfile = motionProfile
  }
  
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

function focusStart(){
  if (route.value.points.length === 0) return
  const firstPoint = route.value.points[0]
  const focusEvent = new CustomEvent('map-focus', {
    detail: { lat: firstPoint.lat, lon: firstPoint.lon, zoom: 14 }
  })
  window.dispatchEvent(focusEvent)
}

function splitSelectedSegment(){
  const idx = route.value.segments.findIndex(s => s.isSelected)
  if (idx < 0) {
    alert('Please select a segment to split')
    return
  }
  const ok = route.value.splitSegment(idx)
  if (!ok) {
    alert('Cannot split this segment right now')
  }
}

function runSim(){
  if(route.value.points.length < 2){ alert('Add at least two waypoints'); return }
  simStatus.value = null
  route.value.startSimulation(0, null)
  simState.value = 'running'
}

function runSimFromSegment(){
  const selectedIdx = route.value.segments.findIndex(s => s.isSelected)
  if (selectedIdx < 0) {
    alert('Please select a segment first')
    return
  }
  simStatus.value = null
  route.value.startSimulation(selectedIdx, null)
  simState.value = 'running'
}

function stopSim(){
  simState.value = 'stopped'
  route.value.stopSimulation()
}

function resetRoute(){
  route.value = new Route()
}

function updateTelemetry(next: any) {
  telemetry.value = next
}

// expose to MapView
const onAddWaypointRef = onAddWaypoint
</script>

<style scoped>
/* minimal */
</style>
