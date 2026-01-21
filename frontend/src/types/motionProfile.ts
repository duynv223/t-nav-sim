export type MotionProfileType = 'simple' | 'advance'

export interface SimpleMotionProfile {
  type: 'simple'
  params: {
    cruise_speed_kmh: number
    accel_mps2: number
    decel_mps2: number
    turn_slowdown_factor_per_deg: number
    min_turn_speed_kmh: number
    turn_rate_deg_s: number
    start_hold_s: number
    start_speed_kmh: number
    start_speed_s: number
  }
}

export interface AdvanceMotionProfile {
  type: 'advance'
  params: SimpleMotionProfile['params']
}

export type MotionProfile = SimpleMotionProfile | AdvanceMotionProfile

export function createDefaultMotionProfile(): MotionProfile {
  return {
    type: 'simple',
    params: {
      cruise_speed_kmh: 20.0,
      accel_mps2: 1.0,
      decel_mps2: 1.0,
      turn_slowdown_factor_per_deg: 0.1,
      min_turn_speed_kmh: 5,
      turn_rate_deg_s: 20.0,
      start_hold_s: 60,
      start_speed_kmh: 3.0,
      start_speed_s: 30.0
    }
  }
}
