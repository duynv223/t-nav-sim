
export type SpeedProfileType = 'constant' | 'ramp_to' | 'cruise_to' | 'stop_at_end'

export interface ConstantSpeedProfile {
  type: 'constant'
  params: {
    speed_kmh: number
  }
}

export interface RampToSpeedProfile {
  type: 'ramp_to'
  params: {
    target_kmh: number
  }
}

export interface CruiseToSpeedProfile {
  type: 'cruise_to'
  params: {
    speed_kmh: number
  }
}

export interface StopAtEndSpeedProfile {
  type: 'stop_at_end'
  params: {
    stop_duration_s: number
  }
}

export type SpeedProfile = 
  | ConstantSpeedProfile 
  | RampToSpeedProfile 
  | CruiseToSpeedProfile 
  | StopAtEndSpeedProfile

export function createDefaultSpeedProfile(): SpeedProfile {
  return {
    type: 'constant',
    params: {
      speed_kmh: 25
    }
  }
}

export function createConstantProfile(speed_kmh: number): ConstantSpeedProfile {
  return {
    type: 'constant',
    params: { speed_kmh }
  }
}

export function createRampToProfile(target_kmh: number): RampToSpeedProfile {
  return {
    type: 'ramp_to',
    params: { target_kmh }
  }
}

export function createCruiseToProfile(speed_kmh: number): CruiseToSpeedProfile {
  return {
    type: 'cruise_to',
    params: { speed_kmh }
  }
}

export function createStopAtEndProfile(stop_duration_s: number): StopAtEndSpeedProfile {
  return {
    type: 'stop_at_end',
    params: { stop_duration_s }
  }
}
