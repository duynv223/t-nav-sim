/**
 * Car Simulation - Handles car marker updates during simulation
 * 
 * @architecture
 * - Throttled updates for performance
 * - Smart icon updates (only when bearing changes significantly)
 * - Automatic lifecycle management via watchers
 */

import { Ref, reactive, readonly, watch } from 'vue'
import type { LiveData } from '@/types/map'
import { useMapObjectPool } from './useMapObjectPool'
import { useThrottle } from './useThrottle'
import { generateCarSVG } from '@/utils/mapHelpers'
import { CAR_SIMULATION } from '@/types/constants'

export function useCarSimulation(
  map: Ref<any>,
  live: Ref<LiveData | undefined>
) {
  const pool = useMapObjectPool(map)
  const { throttle } = useThrottle()

  interface CarState {
    bearing: number
    lastIconUpdate: number
  }

  const carState = reactive<CarState>({
    bearing: 0,
    lastIconUpdate: 0
  })

  /**
   * Update car marker position and rotation
   * Only updates icon when bearing changes significantly (performance optimization)
   */
  const updateCar = throttle((): void => {
    if (!live.value || !map.value) return

    const { lat, lon, bearing = 0 } = live.value
    const bearingChanged = Math.abs(bearing - carState.bearing) > CAR_SIMULATION.BEARING_THRESHOLD

    if (bearingChanged || !pool.hasMarker('car')) {
      // Bearing changed significantly or first time - recreate icon with rotation
      carState.bearing = bearing
      carState.lastIconUpdate = Date.now()
      const svg = generateCarSVG(bearing)

      pool.createMarker('car', {
        lat,
        lng: lon,
        svg,
        iconOptions: { 
          anchor: { 
            x: CAR_SIMULATION.CAR_ANCHOR, 
            y: CAR_SIMULATION.CAR_ANCHOR 
          } 
        },
        volatility: true,
        zIndex: 1000
      })
    } else {
      // Just update position, keep icon (more efficient)
      pool.updateMarker('car', lat, lon)
    }
  }, CAR_SIMULATION.UPDATE_THROTTLE_MS)

  /**
   * Clear car marker
   */
  const clearCar = (): void => {
    pool.removeMarker('car')
    carState.bearing = 0
    carState.lastIconUpdate = 0
  }

  // Auto-update when live data changes
  watch(
    live,
    () => {
      if (live.value) {
        updateCar()
      } else {
        clearCar()
      }
    },
    { deep: true }
  )

  return {
    carState: readonly(carState),
    updateCar,
    clearCar
  }
}
