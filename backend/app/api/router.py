from fastapi import APIRouter

from app.api.routes import route, sim, ws

router = APIRouter()
router.include_router(route.router)
router.include_router(sim.router)
router.include_router(ws.router)
