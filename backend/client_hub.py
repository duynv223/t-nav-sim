from typing import Iterable
from fastapi import WebSocket


class ClientHub:
    def __init__(self):
        self._clients: dict[WebSocket, set[str]] = {}

    def add(self, ws: WebSocket, topics: Iterable[str] | None = None) -> None:
        self._clients[ws] = set(topics or {"data", "state"})

    def remove(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    def update_topics(self, ws: WebSocket, topics: Iterable[str]) -> None:
        if ws in self._clients:
            self._clients[ws] = set(topics)

    def count(self) -> int:
        return len(self._clients)

    async def publish(self, payload: dict, topic: str | None = None) -> int:
        to_remove = []
        sent = 0
        for ws, topics in list(self._clients.items()):
            if topic is not None and topic not in topics:
                continue
            try:
                await ws.send_json(payload)
                sent += 1
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self._clients.pop(ws, None)
        return sent


def get_client_hub(app) -> ClientHub:
    if not hasattr(app.state, "client_hub") or app.state.client_hub is None:
        app.state.client_hub = ClientHub()
    return app.state.client_hub
