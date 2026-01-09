/**
 * Route Renderer - Handles rendering of route segments and waypoints
 * 
 * @architecture
 * - Efficient diff-based updates
 * - Event handler management
 * - Automatic re-rendering on route changes
 */

import { Ref, watch } from 'vue'
import { Route } from '@/types/route'
import type { EditorCallbacks } from '@/types/map'
import { useMapObjectPool } from './useMapObjectPool'
import { useThrottle } from './useThrottle'
import { hexToRgba } from '@/utils/mapHelpers'
import { ROUTE_RENDERER, ROUTE_STYLE } from '@/types/constants'

export function useRouteRenderer(
  map: Ref<any>,
  route: Ref<Route>,
  callbacks?: EditorCallbacks,
  onMarkerDragStart?: (idx: number, lat: number, lng: number) => void
) {
  const pool = useMapObjectPool(map)
  const { throttle } = useThrottle()
  let lastSegmentCount = 0 // Track segment count to detect removals
  let lastWaypointCount = 0 // Track waypoint count to detect removals
  let lastRouteRenderTime = 0
  const ROUTE_RENDER_THROTTLE_MS = 100 // Throttle route rendering to prevent flicker

  /**
   * Render all route segments
   * Recreates all segments to avoid flickering (like old working code)
   */
  const renderRouteInternal = (): void => {
    if (!map.value || route.value.points.length < 2) {
      // Clear all segment lines if no route
      for (let i = 0; i < lastSegmentCount; i++) {
        pool.removeLine(`segment-${i}`)
        pool.removeLine(`segment-border-${i}`)
      }
      lastSegmentCount = 0
      return
    }

    // Clear all old segments first (batch removal to avoid flicker)
    for (let i = 0; i < lastSegmentCount; i++) {
      pool.removeLine(`segment-${i}`)
      pool.removeLine(`segment-border-${i}`)
    }

    const currentSegmentCount = route.value.segments.length
    lastSegmentCount = currentSegmentCount

    // Recreate all segments (batch creation to avoid flicker)
    route.value.segments.forEach((segment, idx) => {
      const from = route.value.points[segment.from]
      const to = route.value.points[segment.to]
      
      if (!from || !to) {
        return
      }

      // Check if segment is locked for color override
      const isLocked = route.value.isSegmentLocked(idx)
      const color = segment.getColor(isLocked)
      const strokeColor = hexToRgba(color, segment.getOpacity())
      const coordinates = [
        { lat: from.lat, lng: from.lon },
        { lat: to.lat, lng: to.lon }
      ]

      // Create transparent border for selected segments
      if (segment.isSelected) {
        pool.createLine(`segment-border-${idx}`, {
          coordinates,
          style: {
            lineWidth: ROUTE_STYLE.SEGMENT_SELECTION_BORDER_WIDTH,
            strokeColor: ROUTE_STYLE.SEGMENT_SELECTION_BORDER_COLOR
          },
          volatility: true
        })
      }

      // Create main line (volatility=true for better rendering performance)
      pool.createLine(`segment-${idx}`, {
        coordinates,
        style: {
          lineWidth: segment.getWidth(),
          strokeColor
        },
        volatility: true // Important: enables efficient rendering
      })

      // Add click handler for segment selection
      if (callbacks?.onSelectSegment) {
        pool.addLineEvent(`segment-${idx}`, 'tap', (evt: any) => {
          evt.stopPropagation()
          callbacks.onSelectSegment!(idx)
        })
      }
    })

    // Update tracked count
    lastWaypointCount = route.value.points.length
  }

  /**
   * Throttled version of renderRoute to prevent excessive updates
   */
  const renderRoute = (): void => {
    const now = Date.now()
    if (now - lastRouteRenderTime < ROUTE_RENDER_THROTTLE_MS) {
      return
    }
    lastRouteRenderTime = now
    renderRouteInternal()
  }

  /**
   * Render all waypoint markers
   * Recreates all markers for simplicity (they change less frequently than positions)
   */
  const renderWaypoints = (): void => {
    if (!map.value) return

    // Remove all old waypoint markers using tracked count
    const maxToRemove = Math.max(lastWaypointCount, route.value.points.length)
    for (let i = 0; i < maxToRemove; i++) {
      if (pool.hasMarker(`waypoint-${i}`)) {
        pool.removeMarker(`waypoint-${i}`)
      }
    }

    // Create all new waypoint markers
    route.value.points.forEach((point, idx) => {
      const markerId = `waypoint-${idx}`
      
      // Check if point is locked for color synchronization
      const isPointLocked = route.value.isPointLocked(idx)
      
      pool.createMarker(markerId, {
        lat: point.lat,
        lng: point.lon,
        svg: point.getIcon(isPointLocked),
        iconOptions: { 
          size: { 
            w: ROUTE_RENDERER.WAYPOINT_SIZE, 
            h: ROUTE_RENDERER.WAYPOINT_SIZE 
          }, 
          anchor: { 
            x: ROUTE_RENDERER.WAYPOINT_ANCHOR, 
            y: ROUTE_RENDERER.WAYPOINT_ANCHOR 
          } 
        },
        data: { index: idx },
        volatility: true // Need to update when selection state changes
      })

      // Add event handlers
      if (callbacks?.onSelectWaypoint) {
        pool.addMarkerEvent(markerId, 'tap', (evt: any) => {
          evt.stopPropagation()
          callbacks.onSelectWaypoint!(idx)
        })
      }

      if (onMarkerDragStart) {
        pool.addMarkerEvent(markerId, 'pointerdown', (evt: any) => {
          if (point.isSelected) {
            evt.stopPropagation()
            onMarkerDragStart(idx, point.lat, point.lon)
            
            // Change cursor
            const mapEl = map.value?.getElement()
            if (mapEl) {
              mapEl.style.cursor = 'grabbing'
            }
          }
        })
      }

      // Add hover effects
      pool.addMarkerEvent(markerId, 'pointerenter', () => {
        const mapEl = map.value?.getElement()
        if (mapEl) {
          mapEl.style.cursor = point.isSelected ? 'move' : 'pointer'
        }
      })

      pool.addMarkerEvent(markerId, 'pointerleave', () => {
        const mapEl = map.value?.getElement()
        if (mapEl) {
          mapEl.style.cursor = 'default'
        }
      })
    })
  }

  /**
   * Clear all rendered objects
   */
  const clearAll = (): void => {
    // Clear all segments
    route.value.segments.forEach((_, idx) => {
      pool.removeLine(`segment-${idx}`)
    })

    // Clear all waypoints
    route.value.points.forEach((_, idx) => {
      pool.removeMarker(`waypoint-${idx}`)
    })
  }

  /**
   * Clean up pool resources
   */
  const cleanup = (): void => {
    pool.cleanup()
  }

  // Auto-update when route changes (like old working code)
  watch(
    () => route.value,
    () => {
      renderWaypoints()
      renderRoute()
    },
    { deep: true }
  )

  return {
    renderRoute,
    renderWaypoints,
    clearAll,
    cleanup: pool.cleanup // Expose pool cleanup for unmount
  }
}
