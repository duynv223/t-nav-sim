from fastapi import APIRouter, HTTPException, Request

from app.deps import get_route_service
from app.schemas.route import RouteDefinition
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.put("/route")
async def update_active_route(route: RouteDefinition, request: Request):
    service = get_route_service(request.app)
    service.set_active_route(route)
    logger.info(f"Route Sync: {route.routeId} | {len(route.waypoints)} waypoints, {len(route.segments)} segments")
    for idx, seg in enumerate(route.segments):
        profile = seg.speedProfile if isinstance(seg.speedProfile, dict) else seg.speedProfile.dict()
        profile_type = profile['type']
        params_str = ', '.join(f"{k}={v}" for k, v in profile['params'].items())
        logger.info(f"  Seg {idx}: {seg.from_} → {seg.to} | {profile_type}({params_str})")
    return {"status": "updated", "routeId": route.routeId}

@router.get("/route")
async def get_active_route(request: Request):
    service = get_route_service(request.app)
    active_route = service.get_active_route()
    if active_route is None:
        raise HTTPException(status_code=404, detail="No active route")
    return active_route
