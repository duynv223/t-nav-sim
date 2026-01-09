from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from api_route import router as route_router
from api_sim import router as sim_router
from api_ws import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-15s %(levelname)-5s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(name)-15s %(levelname)-5s %(message)s',
        datefmt='%H:%M:%S'
    ))
    uvicorn_logger.addHandler(handler)
    uvicorn_logger.setLevel(logging.INFO)

app = FastAPI()
app.state.active_route = None
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(route_router)
app.include_router(sim_router)
app.include_router(ws_router)
