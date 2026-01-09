

export interface Coordinate {
  lat: number
  lng: number
}

export interface Position {
  lat: number
  lon: number
}


export interface IconOptions {
  size?: { w: number; h: number }
  anchor?: { x: number; y: number }
}

export interface MarkerConfig {
  lat: number
  lng: number
  svg: string
  iconOptions: IconOptions
  data?: Record<string, any>
  volatility?: boolean // For objects that update frequently
  zIndex?: number
}

export interface LineStyle {
  lineWidth?: number
  strokeColor?: string
  lineDash?: [number, number]
}

export interface LineConfig {
  coordinates: Coordinate[]
  style?: LineStyle
  volatility?: boolean
}


export type MarkerEventHandler = (evt: any) => void
export type LineEventHandler = (evt: any) => void

export interface EventHandlerRef {
  event: string
  handler: MarkerEventHandler | LineEventHandler
}


export interface EditorCallbacks {
  onAddWaypoint?: (p: Position) => void
  onMoveWaypoint?: (idx: number, p: Position) => void
  onSelectWaypoint?: (idx: number) => void
  onSelectSegment?: (idx: number) => void
  onDeleteWaypoint?: (idx: number) => void
}


export interface LiveData {
  lat: number
  lon: number
  bearing?: number
  speed?: number
  timestamp?: number
}
