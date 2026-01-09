/**
 * Map Editor - Handles preview and drag interactions
 * 
 * @architecture
 * - Throttled updates for performance
 * - Preview markers and lines for user feedback
 * - Drag-and-drop waypoint editing
 * - Automatic map behavior management
 */

import { Ref, reactive, readonly } from 'vue'
import { Route } from '@/types/route'
import type { EditorCallbacks, Position, Coordinate } from '@/types/map'
import { useMapObjectPool } from './useMapObjectPool'
import { useThrottle } from './useThrottle'
import { MAP_EDITOR, ROUTE_COLORS } from '@/types/constants'

// Preview marker SVG
const PREVIEW_MARKER_SVG = `<svg width="${MAP_EDITOR.PREVIEW_MARKER_SIZE}" height="${MAP_EDITOR.PREVIEW_MARKER_SIZE}" viewBox="0 0 ${MAP_EDITOR.PREVIEW_MARKER_SIZE} ${MAP_EDITOR.PREVIEW_MARKER_SIZE}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="${MAP_EDITOR.PREVIEW_MARKER_ANCHOR}" cy="${MAP_EDITOR.PREVIEW_MARKER_ANCHOR}" r="6" fill="${ROUTE_COLORS.PREVIEW}" stroke="#fff" stroke-width="2" opacity="0.7"/>
</svg>`

export function useMapEditor(
  map: Ref<any>,
  route: Ref<Route>,
  callbacks: EditorCallbacks,
  behavior?: Ref<any>
) {
  const pool = useMapObjectPool(map)
  const { throttle } = useThrottle()

  // ========== Preview State ==========
  
  interface PreviewState {
    isShowing: boolean
    position: Coordinate
  }
  
  const previewState = reactive<PreviewState>({
    isShowing: false,
    position: { lat: 0, lng: 0 }
  })

  /**
   * Show preview marker and line when hovering in add mode
   * Throttled for performance (~60fps)
   */
  const showPreview = throttle((lat: number, lng: number): void => {
    previewState.position = { lat, lng }

    if (!previewState.isShowing) {
      pool.createMarker('preview', {
        lat,
        lng,
        svg: PREVIEW_MARKER_SVG,
        iconOptions: { 
          size: { 
            w: MAP_EDITOR.PREVIEW_MARKER_SIZE, 
            h: MAP_EDITOR.PREVIEW_MARKER_SIZE 
          }, 
          anchor: { 
            x: MAP_EDITOR.PREVIEW_MARKER_ANCHOR, 
            y: MAP_EDITOR.PREVIEW_MARKER_ANCHOR 
          } 
        },
        volatility: true
      })
      previewState.isShowing = true
    } else {
      pool.updateMarker('preview', lat, lng)
    }

    // // Update preview line to last waypoint
    // if (route.value.points.length > 0) {
    //   const lastPoint = route.value.points[route.value.points.length - 1]
      
    //   if (!pool.hasLine('preview-line')) {
    //     // Create line with style once
    //     pool.createLine('preview-line', {
    //       coordinates: [
    //         { lat: lastPoint.lat, lng: lastPoint.lon },
    //         { lat, lng }
    //       ],
    //       style: {
    //         strokeColor: `rgba(150,150,150,${MAP_EDITOR.PREVIEW_LINE_OPACITY})`,
    //         lineWidth: 4,
    //         lineDash: MAP_EDITOR.PREVIEW_LINE_DASH
    //       },
    //       volatility: true
    //     })
    //   } else {
    //     // Just update coordinates, no style (much faster!)
    //     pool.updateLine(
    //       'preview-line', 
    //       [
    //         { lat: lastPoint.lat, lng: lastPoint.lon },
    //         { lat, lng }
    //       ]
    //       // No style parameter = skip style check
    //     )
    //   }
    // } else {
    //   pool.removeLine('preview-line')
    // }
  }, MAP_EDITOR.THROTTLE_PREVIEW_MS)

  /**
   * Clear preview marker and line
   */
  const clearPreview = (): void => {
    pool.removeMarker('preview')
    pool.removeLine('preview-line')
    previewState.isShowing = false
  }

  // ========== Drag State ==========
  
  interface DragState {
    isDragging: boolean
    pointIndex: number
    startPosition: Coordinate | null
  }
  
  const dragState = reactive<DragState>({
    isDragging: false,
    pointIndex: -1,
    startPosition: null
  })

  /**
   * Start dragging a waypoint
   * Only works if the point is already selected
   */
  const startDrag = (pointIndex: number, lat: number, lng: number): void => {
    // Only allow drag if point is already selected
    if (!route.value.points[pointIndex]?.isSelected) return
    
    // Prevent dragging locked points
    if (route.value.isPointLocked(pointIndex)) {
      console.warn(`Cannot drag point ${pointIndex}: locked by simulation`)
      return
    }

    dragState.isDragging = true
    dragState.pointIndex = pointIndex
    dragState.startPosition = { lat, lng }
    
    // Disable map panning during drag for better UX
    if (behavior?.value) {
      behavior.value.disable()
    }
  }

  /**
   * Update drag preview lines
   * Throttled for smooth 60fps performance
   */
  const updateDrag = throttle((lat: number, lng: number): void => {
    if (!dragState.isDragging) return

    const idx = dragState.pointIndex

    // Show preview line to previous point
    if (idx > 0) {
      const prev = route.value.points[idx - 1]
      
      if (!pool.hasLine('drag-prev')) {
        // Create line with style once
        pool.createLine('drag-prev', {
          coordinates: [
            { lat: prev.lat, lng: prev.lon },
            { lat, lng }
          ],
          style: {
            strokeColor: `rgba(33, 150, 243, ${MAP_EDITOR.DRAG_LINE_OPACITY})`,
            lineWidth: 4,
            lineDash: MAP_EDITOR.DRAG_LINE_DASH
          },
          volatility: true
        })
      } else {
        // Just update coordinates
        pool.updateLine('drag-prev', [
          { lat: prev.lat, lng: prev.lon },
          { lat, lng }
        ])
      }
    } else {
      pool.removeLine('drag-prev')
    }

    // Show preview line to next point
    if (idx < route.value.points.length - 1) {
      const next = route.value.points[idx + 1]
      
      if (!pool.hasLine('drag-next')) {
        // Create line with style once
        pool.createLine('drag-next', {
          coordinates: [
            { lat, lng },
            { lat: next.lat, lng: next.lon }
          ],
          style: {
            strokeColor: `rgba(33, 150, 243, ${MAP_EDITOR.DRAG_LINE_OPACITY})`,
            lineWidth: 4,
            lineDash: MAP_EDITOR.DRAG_LINE_DASH
          },
          volatility: true
        })
      } else {
        // Just update coordinates
        pool.updateLine('drag-next', [
          { lat, lng },
          { lat: next.lat, lng: next.lon }
        ])
      }
    } else {
      pool.removeLine('drag-next')
    }
  }, MAP_EDITOR.THROTTLE_DRAG_MS)

  /**
   * End drag and commit position
   */
  const endDrag = (lat: number, lng: number, onComplete?: () => void): void => {
    if (!dragState.isDragging) return

    callbacks.onMoveWaypoint?.(dragState.pointIndex, { lat, lon: lng })

    pool.removeLine('drag-prev')
    pool.removeLine('drag-next')
    
    dragState.isDragging = false
    dragState.pointIndex = -1
    dragState.startPosition = null
    
    // Re-enable map panning
    if (behavior?.value) {
      behavior.value.enable()
    }
    
    // Notify completion
    onComplete?.()
  }

  /**
   * Cancel drag without committing
   */
  const cancelDrag = (): void => {
    pool.removeLine('drag-prev')
    pool.removeLine('drag-next')
    dragState.isDragging = false
    dragState.pointIndex = -1
    dragState.startPosition = null
    
    // Re-enable map panning
    if (behavior?.value) {
      behavior.value.enable()
    }
  }

  return {
    // Preview
    showPreview,
    clearPreview,
    previewState: readonly(previewState),

    // Drag
    startDrag,
    updateDrag,
    endDrag,
    cancelDrag,
    dragState: readonly(dragState)
  }
}
