from app.services.client_hub import get_client_hub
from app.services.route_service import RouteService
from app.services.sim_service import SimulationService


def get_sim_service(app) -> SimulationService:
    if not getattr(app.state, "sim_service", None):
        hub = get_client_hub(app)
        app.state.sim_service = SimulationService(hub)
    return app.state.sim_service


def get_route_service(app) -> RouteService:
    if not getattr(app.state, "route_service", None):
        app.state.route_service = RouteService(app)
    return app.state.route_service
