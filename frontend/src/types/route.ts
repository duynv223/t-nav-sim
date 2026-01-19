import { ROUTE_COLORS, ROUTE_RENDERER, ROUTE_STYLE } from './constants'
import { SelectionType, SegmentState } from './enums'

export class RoutePoint {
  lat: number
  lon: number
  isSelected: boolean = false
  
  constructor(lat: number, lon: number) {
    this.lat = lat
    this.lon = lon
  }
  
  getColor(isLocked: boolean = false): string {
    return isLocked ? ROUTE_COLORS.LOCKED : ROUTE_COLORS.NORMAL
  }
  
  getIcon(isLocked: boolean = false): string {
    const finalColor = this.getColor(isLocked)
    const svg = `<svg width="${ROUTE_RENDERER.WAYPOINT_SIZE}" height="${ROUTE_RENDERER.WAYPOINT_SIZE}" viewBox="0 0 ${ROUTE_RENDERER.WAYPOINT_SIZE} ${ROUTE_RENDERER.WAYPOINT_SIZE}" xmlns="http://www.w3.org/2000/svg">`
    
    if (this.isSelected) {
      return svg + `
      <circle cx="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" cy="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" r="${ROUTE_RENDERER.WAYPOINT_RADIUS + ROUTE_RENDERER.WAYPOINT_SELECTION_BORDER_WIDTH}" fill="none" stroke="${ROUTE_RENDERER.WAYPOINT_SELECTION_BORDER_COLOR}" stroke-width="${ROUTE_RENDERER.WAYPOINT_SELECTION_BORDER_WIDTH}"/>
      <circle cx="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" cy="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" r="${ROUTE_RENDERER.WAYPOINT_RADIUS}" fill="${finalColor}" fill-opacity="${ROUTE_RENDERER.WAYPOINT_OPACITY}" stroke="#fff" stroke-width="${ROUTE_RENDERER.WAYPOINT_STROKE_WIDTH}" stroke-opacity="${ROUTE_RENDERER.WAYPOINT_OPACITY}"/>
    </svg>`
    }
    
    return svg + `
      <circle cx="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" cy="${ROUTE_RENDERER.WAYPOINT_ANCHOR}" r="${ROUTE_RENDERER.WAYPOINT_RADIUS}" fill="${finalColor}" fill-opacity="${ROUTE_RENDERER.WAYPOINT_OPACITY}" stroke="#fff" stroke-width="${ROUTE_RENDERER.WAYPOINT_STROKE_WIDTH}" stroke-opacity="${ROUTE_RENDERER.WAYPOINT_OPACITY}"/>
    </svg>`
  }
  
  clone(): RoutePoint {
    const point = new RoutePoint(this.lat, this.lon)
    point.isSelected = this.isSelected
    return point
  }
}

export class RouteSegment {
  from: number  // index in points array
  to: number    // index in points array
  isSelected: boolean = false
  
  state: SegmentState = SegmentState.PENDING
  
  constructor(
    from: number, 
    to: number
  ) {
    this.from = from
    this.to = to
  }
  
  getState(): SegmentState {
    return this.state
  }
  
  setState(state: SegmentState): void {
    this.state = state
  }
  
  get isActive(): boolean {
    return this.state === SegmentState.ACTIVE
  }
  
  get isDone(): boolean {
    return this.state === SegmentState.DONE
  }
  
  get isPending(): boolean {
    return this.state === SegmentState.PENDING
  }
  
  getColor(isLocked: boolean = false): string {
    return isLocked ? ROUTE_COLORS.LOCKED : ROUTE_COLORS.NORMAL
  }
  
  getWidth(): number {
    return this.isSelected ? ROUTE_STYLE.SEGMENT_WIDTH_SELECTED : ROUTE_STYLE.SEGMENT_WIDTH_NORMAL
  }
  
  getOpacity(): number {
    return ROUTE_STYLE.SEGMENT_OPACITY
  }
  
  clone(): RouteSegment {
    const segment = new RouteSegment(this.from, this.to)
    segment.isSelected = this.isSelected
    segment.setState(this.state)
    return segment
  }
}

export class Route {
  routeId: string = 'Untitled Route'
  points: RoutePoint[] = []
  segments: RouteSegment[] = []
  
  simulatingSegmentRange: { start: number, end: number } | null = null
  
  selectedType: SelectionType | null = null
  
  addPoint(lat: number, lon: number): void {
    const point = new RoutePoint(lat, lon)
    this.points.push(point)
    this.rebuildSegments()
  }
  
  deletePoint(idx: number): void {
    if (idx >= 0 && idx < this.points.length) {
      if (this.isPointLocked(idx)) {
        console.warn(`Cannot delete point ${idx}: locked by simulation`)
        return
      }
      
      this.points.splice(idx, 1)
      this.rebuildSegments()
    }
  }
  
  movePoint(idx: number, lat: number, lon: number): void {
    if (idx >= 0 && idx < this.points.length) {
      if (this.isPointLocked(idx)) {
        console.warn(`Cannot move point ${idx}: locked by simulation`)
        return
      }
      
      this.points[idx].lat = lat
      this.points[idx].lon = lon
    }
  }
  
  selectPoint(idx: number): void {
    this.deselectAll()
    
    if (idx >= 0 && idx < this.points.length) {
      this.points[idx].isSelected = true
      this.selectedType = SelectionType.POINT
    }
  }
  
  selectSegment(idx: number): void {
    this.deselectAll()
    
    if (idx >= 0 && idx < this.segments.length) {
      this.segments[idx].isSelected = true
      this.selectedType = SelectionType.SEGMENT
    }
  }
  
  deselectAll(): void {
    this.points.forEach(p => p.isSelected = false)
    this.segments.forEach(s => s.isSelected = false)
    this.selectedType = null
  }
  
  getSelectedPoint(): RoutePoint | null {
    return this.points.find(p => p.isSelected) || null
  }
  
  getSelectedSegment(): RouteSegment | null {
    return this.segments.find(s => s.isSelected) || null
  }
  
  getSelectedType(): SelectionType | null {
    return this.selectedType
  }
  
  startSimulation(startSegIdx: number = 0, endSegIdx: number | null = null) {
    const end = endSegIdx !== null ? endSegIdx : this.segments.length - 1
    this.simulatingSegmentRange = { start: startSegIdx, end }
    
    this.segments.forEach(seg => {
      seg.setState(SegmentState.PENDING)
    })
  }
  
  stopSimulation() {
    this.simulatingSegmentRange = null
    
    this.segments.forEach(seg => {
      seg.setState(SegmentState.PENDING)
    })
  }
  
  isSegmentLocked(segmentIdx: number): boolean {
    if (!this.simulatingSegmentRange) return false
    
    const seg = this.segments[segmentIdx]
    if (!seg) return false
    
    const { start, end } = this.simulatingSegmentRange
    return segmentIdx >= start && segmentIdx <= end
  }
  
  isPointLocked(pointIdx: number): boolean {
    if (!this.simulatingSegmentRange) return false
    
    const { start, end } = this.simulatingSegmentRange
    
    return this.segments.some((seg, idx) => 
      idx >= start && idx <= end &&
      (seg.from === pointIdx || seg.to === pointIdx)
    )
  }
  
  canDeletePoint(pointIdx: number): boolean {
    return !this.isPointLocked(pointIdx)
  }
  
  canMovePoint(pointIdx: number): boolean {
    return !this.isPointLocked(pointIdx)
  }
  
  rebuildSegments(): void {
    const selectedIdx = this.segments.findIndex(s => s.isSelected)
    this.segments = []
    
    for (let i = 0; i + 1 < this.points.length; i++) {
      const seg = new RouteSegment(i, i + 1)
      if (i === selectedIdx) {
        seg.isSelected = true
      }
      this.segments.push(seg)
    }
  }

  splitSegment(idx: number): boolean {
    if (this.simulatingSegmentRange) return false
    if (idx < 0 || idx >= this.segments.length) return false
    if (this.isSegmentLocked(idx)) return false

    const fromPoint = this.points[idx]
    const toPoint = this.points[idx + 1]
    if (!fromPoint || !toPoint) return false

    const midPoint = new RoutePoint(
      (fromPoint.lat + toPoint.lat) / 2,
      (fromPoint.lon + toPoint.lon) / 2
    )

    const oldSegments = this.segments
    const oldSelectedIdx = oldSegments.findIndex(s => s.isSelected)

    this.points.splice(idx + 1, 0, midPoint)

    const newSegments: RouteSegment[] = []
    for (let i = 0; i + 1 < this.points.length; i++) {
      let sourceIdx: number
      if (i === idx || i === idx + 1) {
        sourceIdx = idx
      } else if (i < idx) {
        sourceIdx = i
      } else {
        sourceIdx = i - 1
      }

      const source = oldSegments[sourceIdx]
      const seg = new RouteSegment(i, i + 1)
      seg.setState(source.state)
      newSegments.push(seg)
    }

    newSegments.forEach(s => s.isSelected = false)
    if (oldSelectedIdx >= 0) {
      if (oldSelectedIdx === idx) {
        newSegments[idx].isSelected = true
        this.selectedType = SelectionType.SEGMENT
      } else if (oldSelectedIdx > idx) {
        const shiftedIdx = oldSelectedIdx + 1
        if (newSegments[shiftedIdx]) {
          newSegments[shiftedIdx].isSelected = true
          this.selectedType = SelectionType.SEGMENT
        }
      } else {
        newSegments[oldSelectedIdx].isSelected = true
        this.selectedType = SelectionType.SEGMENT
      }
    } else {
      this.selectedType = null
    }

    this.segments = newSegments
    return true
  }
  
  updateSegmentStates(currentLat: number, currentLon: number): void {
    if (this.segments.length === 0) return
    
    let minDist = Infinity
    let currentSegIdx = -1
    
    this.segments.forEach((seg, idx) => {
      const fromPt = this.points[seg.from]
      const toPt = this.points[seg.to]
      
      const midLat = (fromPt.lat + toPt.lat) / 2
      const midLon = (fromPt.lon + toPt.lon) / 2
      const dist = Math.hypot(currentLat - midLat, currentLon - midLon)
      
      if (dist < minDist) {
        minDist = dist
        currentSegIdx = idx
      }
    })
    
    this.segments.forEach((seg, idx) => {
      if (idx < currentSegIdx) {
        seg.setState(SegmentState.DONE)
      } else if (idx === currentSegIdx) {
        seg.setState(SegmentState.ACTIVE)
      } else {
        seg.setState(SegmentState.PENDING)
      }
    })
  }
  
  toBackendFormat(): { waypoints: Array<{ lat: number; lon: number }>; segments: Array<{ from: number; to: number }> } {
    return {
      waypoints: this.points.map(p => ({ lat: p.lat, lon: p.lon })),
      segments: this.segments.map(s => ({
        from: s.from,
        to: s.to
      }))
    }
  }
  
  getTotalDistance(): number {
    let total = 0
    for (let i = 0; i < this.points.length - 1; i++) {
      const p1 = this.points[i]
      const p2 = this.points[i + 1]
      total += Math.hypot(p2.lat - p1.lat, p2.lon - p1.lon) * 111000 // ~111km per degree
    }
    return total
  }
}
