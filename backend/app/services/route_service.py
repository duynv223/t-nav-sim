from app.schemas.route import RouteDefinition


class RouteService:
    def __init__(self, app):
        self._app = app

    def set_active_route(self, route: RouteDefinition) -> None:
        self._app.state.active_route = route

    def get_active_route(self) -> RouteDefinition | None:
        return getattr(self._app.state, "active_route", None)
