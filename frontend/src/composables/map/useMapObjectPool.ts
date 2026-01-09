/**
 * Map Object Pool - Manages lifecycle of all map objects (markers, lines)
 * Prevents memory leaks and provides efficient object reuse
 * 
 * @architecture
 * - Centralized object lifecycle management
 * - Automatic cleanup of event listeners
 * - Memory-efficient object reuse
 * - Type-safe operations with generics
 */

import { Ref } from 'vue'
import type { 
  MarkerConfig, 
  LineConfig, 
  Coordinate,
  EventHandlerRef,
  MarkerEventHandler,
  LineEventHandler,
  LineStyle
} from '@/types/map'
import { mapLogger } from '@/utils/logger'

/**
 * Generic map object interface
 */
interface MapObject {
  addEventListener(event: string, handler: Function): void
  removeEventListener(event: string, handler: Function): void
}

/**
 * Marker object with HERE Maps API
 */
interface HereMarker extends MapObject {
  setGeometry(coord: { lat: number; lng: number }): void
  setIcon(icon: any): void
}

/**
 * Line object with HERE Maps API
 */
interface HereLine extends MapObject {
  setGeometry(geometry: any): void
  getStyle(): any
  setStyle(style: any): void
}

export function useMapObjectPool(map: Ref<any>) {
  // Object storage with proper types
  const markers = new Map<string, HereMarker>()
  const lines = new Map<string, HereLine>()
  const markerHandlers = new Map<string, EventHandlerRef[]>()
  const lineHandlers = new Map<string, EventHandlerRef[]>()

  /**
   * Create or update a marker
   * @param id - Unique identifier for the marker
   * @param config - Marker configuration
   * @returns The created marker or null if map is not available
   */
  const createMarker = (id: string, config: MarkerConfig): HereMarker | null => {
    removeMarker(id) // Clean up old marker if exists
    
    if (!map.value) {
      mapLogger.warn(`createMarker(${id}) - no map instance`)
      return null
    }

    const { H } = window as any
    const icon = new H.map.Icon(config.svg, config.iconOptions)
    const marker: HereMarker = new H.map.Marker(
      { lat: config.lat, lng: config.lng },
      { 
        icon,
        volatility: config.volatility ?? true, // Default to true for performance
        zIndex: config.zIndex
      }
    )
    
    map.value.addObject(marker)
    markers.set(id, marker)
    mapLogger.debug(`Created marker: ${id}`)
    return marker
  }

  /**
   * Update marker position (efficient, no icon recreation)
   * @param id - Marker identifier
   * @param lat - New latitude
   * @param lng - New longitude
   */
  const updateMarker = (id: string, lat: number, lng: number): void => {
    const marker = markers.get(id)
    if (marker) {
      marker.setGeometry({ lat, lng })
    }
  }

  /**
   * Update marker icon (for rotation, color changes, etc.)
   * @param id - Marker identifier
   * @param svg - New SVG string
   * @param options - Icon options
   */
  const updateMarkerIcon = (id: string, svg: string, options: any): void => {
    const marker = markers.get(id)
    if (marker) {
      const { H } = window as any
      const icon = new H.map.Icon(svg, options)
      marker.setIcon(icon)
    }
  }

  /**
   * Get marker by id
   */
  const getMarker = (id: string): HereMarker | undefined => {
    return markers.get(id)
  }

  /**
   * Check if marker exists
   */
  const hasMarker = (id: string): boolean => {
    return markers.has(id)
  }

  /**
   * Remove marker safely with cleanup
   * @param id - Marker identifier
   */
  const removeMarker = (id: string): void => {
    const marker = markers.get(id)
    if (marker && map.value) {
      // Remove all event listeners first to prevent memory leaks
      const handlers = markerHandlers.get(id)
      if (handlers) {
        handlers.forEach(({ event, handler }) => {
          marker.removeEventListener(event, handler)
        })
        markerHandlers.delete(id)
      }
      
      try {
        map.value.removeObject(marker)
        markers.delete(id)
        mapLogger.debug(`Removed marker: ${id}`)
      } catch (e) {
        mapLogger.error(`Failed to remove marker ${id}`, e)
      }
    }
  }

  /**
   * Create or update a polyline
   * @param id - Unique identifier for the line
   * @param config - Line configuration
   * @returns The created line or null if map is not available
   */
  const createLine = (id: string, config: LineConfig): HereLine | null => {
    removeLine(id) // Clean up old line if exists
    
    if (!map.value) {
      mapLogger.warn(`createLine(${id}) - no map instance`)
      return null
    }

    const { H } = window as any
    const lineString = new H.geo.LineString()
    config.coordinates.forEach(coord => {
      lineString.pushPoint({ lat: coord.lat, lng: coord.lng })
    })

    // Build style object with defaults
    const lineStyle: Record<string, any> = {
      strokeColor: config.style?.strokeColor ?? '#2196F3',
      lineWidth: config.style?.lineWidth ?? 4
    }
    
    // Only add lineDash if it's defined
    if (config.style?.lineDash) {
      lineStyle.lineDash = config.style.lineDash
    }

    const line: HereLine = new H.map.Polyline(lineString, {
      style: lineStyle,
      volatility: config.volatility ?? true // Default to true for frequent updates
    })

    map.value.addObject(line)
    lines.set(id, line)
    mapLogger.debug(`Created line: ${id} with ${config.coordinates.length} points`)
    return line
  }

  /**
   * Update line geometry and optionally style
   * Efficient update without full recreation
   * @param id - Line identifier
   * @param coordinates - New coordinates
   * @param style - Optional style update
   * @param volatility - Optional volatility flag
   */
  const updateLine = (
    id: string, 
    coordinates: Coordinate[], 
    style?: LineStyle, 
    volatility?: boolean
  ): void => {
    const line = lines.get(id)
    
    if (!line) {
      // Line doesn't exist, create it
      createLine(id, { coordinates, style: style ?? {}, volatility })
      return
    }

    const { H } = window as any
    const lineString = new H.geo.LineString()
    coordinates.forEach(coord => {
      lineString.pushPoint({ lat: coord.lat, lng: coord.lng })
    })
    line.setGeometry(lineString)

    // Update style if provided
    if (style) {
      const currentStyle = line.getStyle()
      line.setStyle({
        ...currentStyle,
        ...style
      })
    }
  }

  /**
   * Get line by id
   */
  const getLine = (id: string): HereLine | undefined => {
    return lines.get(id)
  }

  /**
   * Check if line exists
   */
  const hasLine = (id: string): boolean => {
    return lines.has(id)
  }

  /**
   * Remove line safely with cleanup
   * @param id - Line identifier
   */
  const removeLine = (id: string): void => {
    const line = lines.get(id)
    if (line && map.value) {
      // Remove all event listeners first to prevent memory leaks
      const handlers = lineHandlers.get(id)
      if (handlers) {
        handlers.forEach(({ event, handler }) => {
          line.removeEventListener(event, handler)
        })
        lineHandlers.delete(id)
      }
      
      try {
        map.value.removeObject(line)
        lines.delete(id)
        mapLogger.debug(`Removed line: ${id}`)
      } catch (e) {
        mapLogger.error(`Failed to remove line ${id}`, e)
      }
    }
  }

  /**
   * Add event listener to marker
   * @param id - Marker identifier
   * @param eventName - Event name (e.g., 'tap', 'pointerdown')
   * @param handler - Event handler function
   */
  const addMarkerEvent = (
    id: string, 
    eventName: string, 
    handler: MarkerEventHandler
  ): void => {
    const marker = markers.get(id)
    if (marker) {
      marker.addEventListener(eventName, handler)
      
      // Store handler reference for cleanup
      if (!markerHandlers.has(id)) {
        markerHandlers.set(id, [])
      }
      markerHandlers.get(id)!.push({ event: eventName, handler })
    }
  }

  /**
   * Add event listener to line
   * @param id - Line identifier
   * @param eventName - Event name (e.g., 'tap')
   * @param handler - Event handler function
   */
  const addLineEvent = (
    id: string, 
    eventName: string, 
    handler: LineEventHandler
  ): void => {
    const line = lines.get(id)
    if (line) {
      line.addEventListener(eventName, handler)
      
      // Store handler reference for cleanup
      if (!lineHandlers.has(id)) {
        lineHandlers.set(id, [])
      }
      lineHandlers.get(id)!.push({ event: eventName, handler })
    }
  }

  /**
   * Clean up all objects and event listeners
   * Call this when disposing the map
   */
  const cleanup = (): void => {
    markers.forEach((_, id) => removeMarker(id))
    lines.forEach((_, id) => removeLine(id))
  }

  return {
    // Marker operations
    createMarker,
    updateMarker,
    updateMarkerIcon,
    getMarker,
    hasMarker,
    removeMarker,
    addMarkerEvent,
    
    // Line operations
    createLine,
    updateLine,
    getLine,
    hasLine,
    removeLine,
    addLineEvent,
    
    // Cleanup
    cleanup
  }
}
