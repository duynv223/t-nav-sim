
export enum MapMode {
  VIEW = 'view',
  ADD = 'add',
}

export enum SelectionType {
  POINT = 'point',
  SEGMENT = 'segment',
}

export enum SegmentState {
  PENDING = 'pending',
  ACTIVE = 'active',
  DONE = 'done',
}

export enum MapObjectType {
  MARKER = 'marker',
  LINE = 'line',
}

export enum MapEventType {
  TAP = 'tap',
  POINTER_DOWN = 'pointerdown',
  POINTER_UP = 'pointerup',
  POINTER_MOVE = 'pointermove',
  POINTER_ENTER = 'pointerenter',
  POINTER_LEAVE = 'pointerleave',
}
