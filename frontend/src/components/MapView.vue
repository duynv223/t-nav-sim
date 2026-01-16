<template>
  <div class="map-root relative w-full h-full">
    <div ref="mapEl" class="map-canvas" style="width:100%; height:100%;"></div>

    <div class="absolute top-3 left-3 z-40 w-[320px]">
      <div class="bg-white/95 backdrop-blur rounded-lg shadow-lg border border-gray-200 overflow-hidden">
        <div class="p-2">
          <div class="relative">
            <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
                <circle cx="11" cy="11" r="7"></circle>
                <line x1="16.65" y1="16.65" x2="21" y2="21"></line>
              </svg>
            </span>
            <input
              v-model="searchQuery"
              type="text"
              class="w-full h-9 pl-9 pr-8 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Search address or place"
              @keydown.enter.prevent="runSearch"
            />
            <button
              v-if="searchQuery.length > 0"
              @click="searchQuery = ''; searchResults = []; searchError = ''"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              title="Clear search"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        <div v-if="searchError" class="px-3 pb-2 text-xs text-red-600">
          {{ searchError }}
        </div>
        <div v-if="searchResults.length > 0" class="max-h-60 overflow-y-auto border-t border-gray-200">
          <button
            v-for="(result, idx) in searchResults"
            :key="idx"
            class="w-full text-left px-3 py-2 hover:bg-gray-50 text-xs text-gray-700 border-b border-gray-100"
            @click="selectSearchResult(result)"
          >
            <div class="font-medium">{{ result.title }}</div>
            <div v-if="result.address" class="text-[11px] text-gray-500">{{ result.address }}</div>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Loading Spinner -->
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm z-50">
      <div class="flex flex-col items-center justify-center gap-3">
        <div 
          class="animate-spin" 
          style="width: 48px; height: 48px; border: 4px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%;"
        ></div>
        <p class="text-sm font-medium text-gray-600 text-center">Loading map...</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, toRef, watch, PropType, Ref } from 'vue'
import { Route } from '../types/route'
import type { EditorCallbacks, TelemetryData } from '@/types/map'
import { useMapEditor } from '@/composables/map/useMapEditor'
import { useCarSimulation } from '@/composables/map/useCarSimulation'
import { useRouteRenderer } from '@/composables/map/useRouteRenderer'

const props = defineProps({
  mode: { type: String as PropType<'view'|'add'>, required: true },
  onAddWaypoint: { type: Function as PropType<(p:{lat:number,lon:number})=>void>, required: true },
  onDeleteWaypoint: { type: Function as PropType<(idx:number)=>void>, required: false },
  onMoveWaypoint: { type: Function as PropType<(idx:number, p:{lat:number,lon:number})=>void>, required: false },
  onSelectWaypoint: { type: Function as PropType<(idx:number)=>void>, required: false },
  onSelectSegment: { type: Function as PropType<(idx:number)=>void>, required: false },
  route: { type: Object as PropType<Route>, required: true },
  telemetry: { type: Object as PropType<Record<string, any>>, required: false }
})

const mapEl = ref<HTMLDivElement | null>(null)
const map = ref<any>(null)
const behavior = ref<any>(null)
let platform: any = null
let ui: any = null

const isLoading = ref(true)
const searchQuery = ref('')
const searchResults = ref<Array<{ title: string; lat: number; lon: number; address?: string }>>([])
const searchError = ref('')
const isSearching = ref(false)
const hereApiKey = import.meta.env.VITE_HERE_API_KEY || ''

// Setup composables
const callbacks: EditorCallbacks = {
  onAddWaypoint: props.onAddWaypoint,
  onMoveWaypoint: props.onMoveWaypoint,
  onSelectWaypoint: props.onSelectWaypoint,
  onSelectSegment: props.onSelectSegment,
  onDeleteWaypoint: props.onDeleteWaypoint
}

const editor = useMapEditor(map, toRef(props, 'route'), callbacks, behavior)
const simulation = useCarSimulation(map, toRef(props, 'telemetry') as Ref<TelemetryData | undefined>)
const renderer = useRouteRenderer(
  map, 
  toRef(props, 'route'), 
  callbacks,
  (idx, lat, lng) => editor.startDrag(idx, lat, lng)
)

// Handle map focus event from App
function handleMapFocus(event: CustomEvent) {
  const { lat, lon, zoom } = event.detail
  if (map.value) {
    map.value.setCenter({ lat, lng: lon })
    if (zoom) map.value.setZoom(zoom)
  }
}

// Handle route loaded event - trigger re-render
function handleRouteLoaded() {
  console.log('[MapView] Route loaded, re-rendering...')
  if (map.value) {
    renderer.renderWaypoints()
    renderer.renderRoute()
  }
}

function loadHere(apiKey: string){
  return new Promise<void>((resolve, reject)=>{
    if((window as any).H){ resolve(); return }
    
    // Monkey-patch getContext to add willReadFrequently before HERE Maps loads
    const originalGetContext = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function(this: HTMLCanvasElement, contextType: string, contextAttributes?: any): RenderingContext | null {
      if (contextType === '2d') {
        return originalGetContext.call(this, contextType, { 
          ...contextAttributes, 
          willReadFrequently: true 
        }) as RenderingContext | null
      }
      return originalGetContext.call(this, contextType, contextAttributes) as RenderingContext | null
    } as any
    
    // Load core library
    const core = document.createElement('script')
    core.src = 'https://js.api.here.com/v3/3.1/mapsjs-core.js'
    core.onload = ()=>{
      // Load service
      const service = document.createElement('script')
      service.src = 'https://js.api.here.com/v3/3.1/mapsjs-service.js'
      service.onload = ()=>{
        // Load UI
        const uiScript = document.createElement('script')
        uiScript.src = 'https://js.api.here.com/v3/3.1/mapsjs-ui.js'
        uiScript.onload = ()=>{
          // Load map events
          const events = document.createElement('script')
          events.src = 'https://js.api.here.com/v3/3.1/mapsjs-mapevents.js'
          events.onload = ()=> resolve()
          events.onerror = (e)=>reject(e)
          document.head.appendChild(events)
        }
        uiScript.onerror = (e)=>reject(e)
        document.head.appendChild(uiScript)
      }
      service.onerror = (e)=>reject(e)
      document.head.appendChild(service)
    }
    core.onerror = (e)=>reject(e)
    document.head.appendChild(core)
    
    // Load CSS
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = 'https://js.api.here.com/v3/3.1/mapsjs-ui.css'
    document.head.appendChild(css)
  })
}

function handleMapClick(coord: {lat:number, lng:number}){
  if(props.mode === 'add'){
    props.onAddWaypoint({ lat: coord.lat, lon: coord.lng })
    editor.clearPreview()
    // Watchers will auto-render
  } else if(props.mode === 'view'){
    // Click map to deselect
    props.route.deselectAll()
    renderer.renderWaypoints()
  }
}

async function runSearch() {
  const query = searchQuery.value.trim()
  if (!query) return
  if (!hereApiKey) {
    searchError.value = 'Missing VITE_HERE_API_KEY in frontend/.env'
    return
  }

  isSearching.value = true
  searchError.value = ''
  searchResults.value = []

  try {
    const url = `https://geocode.search.hereapi.com/v1/geocode?q=${encodeURIComponent(query)}&limit=5&apiKey=${hereApiKey}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`)
    }
    const data = await response.json()
    const items = Array.isArray(data.items) ? data.items : []
    searchResults.value = items.map((item: any) => ({
      title: item.title || query,
      lat: item.position?.lat,
      lon: item.position?.lng,
      address: item.address?.label
    })).filter((item: any) => typeof item.lat === 'number' && typeof item.lon === 'number')

    if (searchResults.value.length === 0) {
      searchError.value = 'No results found'
    }
  } catch (err) {
    console.error('Search failed:', err)
    searchError.value = 'Search failed. Please try again.'
  } finally {
    isSearching.value = false
  }
}

function selectSearchResult(result: { lat: number; lon: number }) {
  window.dispatchEvent(new CustomEvent('map-focus', {
    detail: { lat: result.lat, lon: result.lon, zoom: 16 }
  }))
}


onMounted(async ()=>{
  const apiKey = import.meta.env.VITE_HERE_API_KEY || ''
  if(!apiKey){
    console.error('❌ VITE_HERE_API_KEY not set! Please set in frontend/.env')
    console.log('Get your free API key at: https://developer.here.com/')
    return
  }
  
  // Skip if map already exists (for HMR)
  if (map.value) {
    console.log('[MapView] Map already exists, skipping initialization')
    return
  }
  
  try {
    isLoading.value = true
    
    await loadHere(apiKey)
    const H = (window as any).H
    
    if(!H) {
      console.error('❌ HERE Maps failed to load')
      isLoading.value = false
      return
    }
    
    console.log('[MapView] Creating new map instance...')
    
    platform = new H.service.Platform({ apikey: apiKey })
    const defaultLayers = platform.createDefaultLayers()
    
    map.value = new H.Map(mapEl.value!, defaultLayers.vector.normal.map, { 
      center: { lat: 10.776, lng: 106.700 }, 
      zoom: 14,
      pixelRatio: window.devicePixelRatio || 1
    })
    behavior.value = new H.mapevents.Behavior(new H.mapevents.MapEvents(map.value))
    ui = H.ui.UI.createDefault(map.value, defaultLayers)
    
    // Listen for map focus events AFTER map is initialized
    window.addEventListener('map-focus', handleMapFocus as EventListener)
    
    // Listen for route-loaded event to trigger re-render
    window.addEventListener('route-loaded', handleRouteLoaded as EventListener)

    // Map click handler
    map.value.addEventListener('tap', function(evt:any){
      const pointer = evt.currentPointer
      const coord = map.value!.screenToGeo(pointer.viewportX, pointer.viewportY)
      handleMapClick(coord)
    })
    
    // Mouse move for preview (only in add mode) and drag
    map.value.addEventListener('pointermove', function(evt:any){
      const coord = map.value!.screenToGeo(evt.currentPointer.viewportX, evt.currentPointer.viewportY)
      
      if(props.mode === 'add' && !editor.dragState.isDragging){
        editor.showPreview(coord.lat, coord.lng)
      } else if(editor.dragState.isDragging){
        editor.updateDrag(coord.lat, coord.lng)
      }
    })
    
    // Mouse down on marker to start drag (handled by marker event in renderer)
    // But we need pointerdown on marker - add this via renderer callbacks
    
    // Mouse up to finish drag
    map.value.addEventListener('pointerup', function(evt:any){
      if(editor.dragState.isDragging){
        const coord = map.value!.screenToGeo(evt.currentPointer.viewportX, evt.currentPointer.viewportY)
        editor.endDrag(coord.lat, coord.lng, () => {
          // Re-render after drag completes
          setTimeout(() => {
            renderer.renderWaypoints()
            renderer.renderRoute()
          }, 0)
        })
      }
    })
    
    // Initial render
    renderer.renderWaypoints()
    renderer.renderRoute()
    
    console.log('✅ HERE Maps initialized successfully')
    
    // Wait for map to complete initial rendering before dispatching ready event
    // Using mapviewchangeend ensures the map has finished its first render cycle
    let mapReadyDispatched = false
    
    const dispatchMapReady = () => {
      if (!mapReadyDispatched) {
        mapReadyDispatched = true
        console.log('[MapView] Map rendering complete, dispatching map-ready event')
        isLoading.value = false // Hide loading overlay
        window.dispatchEvent(new CustomEvent('map-ready'))
      }
    }
    
    // Listen for first viewchange completion (indicates map is fully rendered)
    map.value.addEventListener('mapviewchangeend', dispatchMapReady, { once: true })
    
    // Fallback: if mapviewchangeend doesn't fire within 2s, dispatch anyway
    setTimeout(() => {
      if (!mapReadyDispatched) {
        console.warn('[MapView] mapviewchangeend timeout, dispatching map-ready anyway')
        dispatchMapReady()
      }
    }, 2000)
  } catch(e) {
    console.error('❌ Failed to initialize HERE Maps:', e)
    isLoading.value = false
  }
})

// Cleanup on unmount
onUnmounted(() => {
  console.log('[MapView] Cleaning up...')
  
  // Remove event listeners
  window.removeEventListener('map-focus', handleMapFocus as EventListener)
  window.removeEventListener('route-loaded', handleRouteLoaded as EventListener)
  
  // Clear all map objects and their event listeners
  editor.clearPreview()
  simulation.clearCar()
  renderer.clearAll()
  renderer.cleanup() // Clean up pool (remove event listeners)
  
  // Dispose behavior first (to stop event processing)
  if (behavior.value) {
    try {
      behavior.value.dispose()
    } catch (e) {
      console.warn('[MapView] Error disposing behavior:', e)
    }
    behavior.value = null
  }
  
  // Dispose UI
  if (ui) {
    try {
      ui.dispose()
    } catch (e) {
      console.warn('[MapView] Error disposing UI:', e)
    }
    ui = null
  }
  
  // Dispose map instance
  if (map.value) {
    try {
      map.value.dispose()
    } catch (e) {
      console.warn('[MapView] Error disposing map:', e)
    }
    map.value = null
  }
  
  // Clear platform reference
  if (platform) {
    platform = null
  }
  
  // Force clear the map container DOM to ensure no leftover canvas/elements
  if (mapEl.value) {
    mapEl.value.innerHTML = ''
  }
  
  console.log('[MapView] Cleanup complete')
})

// Clear preview when mode changes
watch(()=>props.mode, ()=>{ 
  editor.clearPreview()
  props.route.deselectAll()
  renderer.renderWaypoints()
})

</script>

<style scoped>
.map-root,
.map-canvas {
  height: 100%;
}
</style>
