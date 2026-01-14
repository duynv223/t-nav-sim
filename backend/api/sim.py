from fastapi import APIRouter, HTTPException, Request
from models import SimRunRequest, SimulationState, SimulationMode
from services.simulation_service import get_sim_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_sim_state(app):
    return get_sim_service(app).get_state()

@router.post("/sim/run")
async def sim_run(req: SimRunRequest, request: Request):
    app = request.app
    active_route = getattr(app.state, "active_route", None)
    if active_route is None:
        logger.error("Attempted to run simulation without active route")
        raise HTTPException(status_code=404, detail="No active route. Please set a route first.")
    service = get_sim_service(app)
    if req.startSegmentIdx < 0 or req.startSegmentIdx >= len(active_route.segments):
        logger.warning(f"Invalid startSegmentIdx: {req.startSegmentIdx}")
        raise HTTPException(status_code=400, detail=f"Invalid startSegmentIdx: {req.startSegmentIdx}")
    end_idx = req.endSegmentIdx if req.endSegmentIdx is not None else len(active_route.segments) - 1
    if end_idx < req.startSegmentIdx or end_idx >= len(active_route.segments):
        logger.warning(f"Invalid endSegmentIdx: {end_idx}")
        raise HTTPException(status_code=400, detail=f"Invalid endSegmentIdx: {end_idx}")
    try:
        mode_str, speed_multiplier = await service.run(
            active_route, req.startSegmentIdx, end_idx, req.mode, req.speedMultiplier, req.dryRun
        )
    except RuntimeError:
        raise HTTPException(status_code=400, detail="Simulation already running")
    logger.info(f"Simulation Started [{mode_str}]: {active_route.routeId} | Segments {req.startSegmentIdx}-{end_idx} ({end_idx - req.startSegmentIdx + 1}) | {service.client_count()} clients")
    return {"status": "started", "state": get_sim_state(app).value, "routeId": active_route.routeId, "startSegmentIdx": req.startSegmentIdx, "endSegmentIdx": end_idx, "mode": req.mode.value, "speedMultiplier": speed_multiplier}

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
    active_route = getattr(app.state, "active_route", None)
    service = get_sim_service(app)
    return {
        "state": sim_state.value,
        "isRunning": sim_state == SimulationState.RUNNING,
        "hasActiveRoute": active_route is not None,
        "routeId": active_route.routeId if active_route else None,
        "clientCount": service.client_count()
    }
