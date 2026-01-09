<template>
  <div class="relative w-full h-full">
    <div ref="mapEl" style="width:100%; height:100%;"></div>
    
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
import type { EditorCallbacks, LiveData } from '@/types/map'
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
  live: { type: Object as PropType<Record<string, any>>, required: false }
})

const mapEl = ref<HTMLDivElement | null>(null)
const map = ref<any>(null)
const behavior = ref<any>(null)
let platform: any = null
let ui: any = null

const isLoading = ref(true)

// Setup composables
const callbacks: EditorCallbacks = {
  onAddWaypoint: props.onAddWaypoint,
  onMoveWaypoint: props.onMoveWaypoint,
  onSelectWaypoint: props.onSelectWaypoint,
  onSelectSegment: props.onSelectSegment,
  onDeleteWaypoint: props.onDeleteWaypoint
}

const editor = useMapEditor(map, toRef(props, 'route'), callbacks, behavior)
const simulation = useCarSimulation(map, toRef(props, 'live') as Ref<LiveData | undefined>)
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
div { height: 100% }
</style>
