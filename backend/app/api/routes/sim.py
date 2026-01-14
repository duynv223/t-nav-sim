from fastapi import APIRouter, HTTPException, Request

from app.deps import get_route_service, get_sim_service
from app.schemas.sim import SimRunRequest
from runtime.sim_state import SimulationState
from sim_core.route.models import SegmentRange
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_sim_state(app):
    return get_sim_service(app).get_state()

@router.post("/sim/run")
async def sim_run(req: SimRunRequest, request: Request):
    app = request.app
    active_route = get_route_service(app).get_active_route()
    if active_route is None:
        logger.error("Attempted to run simulation without active route")
        raise HTTPException(status_code=404, detail="No active route. Please set a route first.")
    service = get_sim_service(app)
    segment_range = req.segmentRange
    start = segment_range.start
    if start < 0 or start >= len(active_route.segments):
        logger.warning(f"Invalid segmentRange.start: {start}")
        raise HTTPException(status_code=400, detail=f"Invalid segmentRange.start: {start}")
    end = segment_range.end if segment_range.end is not None else len(active_route.segments) - 1
    if end < start or end >= len(active_route.segments):
        logger.warning(f"Invalid segmentRange.end: {end}")
        raise HTTPException(status_code=400, detail=f"Invalid segmentRange.end: {end}")
    try:
        mode_str, speed_multiplier = await service.run(
            active_route,
            SegmentRange(start=start, end=end),
            req.mode,
            req.speedMultiplier,
            req.dryRun,
        )
    except RuntimeError:
        raise HTTPException(status_code=400, detail="Simulation already running")
    logger.info(
        "Simulation Started [%s]: %s | Segments %s-%s (%s) | %s clients",
        mode_str,
        active_route.routeId,
        start,
        end,
        end - start + 1,
        service.client_count(),
    )
    return {
        "status": "started",
        "state": get_sim_state(app).value,
        "routeId": active_route.routeId,
        "segmentRange": {
            "start": start,
            "end": end,
        },
        "mode": req.mode.value,
        "speedMultiplier": speed_multiplier,
    }

@router.post("/sim/stop")
async def sim_stop(request: Request):
    app = request.app
    service = get_sim_service(app)
    await service.stop()
    return {"status": "stopped", "state": get_sim_state(app).value}

@router.get("/sim/status")
async def sim_status(request: Request):
    app = request.app
    sim_state = get_sim_state(app)
    active_route = get_route_service(app).get_active_route()
    service = get_sim_service(app)
    return {
        "state": sim_state.value,
        "isRunning": sim_state == SimulationState.RUNNING,
        "hasActiveRoute": active_route is not None,
        "routeId": active_route.routeId if active_route else None,
        "clientCount": service.client_count()
    }
