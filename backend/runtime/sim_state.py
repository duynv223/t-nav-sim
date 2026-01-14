from enum import Enum


class SimulationState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class SimulationMode(str, Enum):
    DEMO = "demo"
    LIVE = "live"
