from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio
from client_hub import get_client_hub

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/sim")
async def websocket_sim(ws: WebSocket):
    app = ws.app
    hub = get_client_hub(app)
    await ws.accept()
    hub.add(ws)
    client_id = id(ws)
    logger.info(f"WebSocket client connected [ID: {client_id}]. Total clients: {hub.count()}")
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            except asyncio.TimeoutError:
                if ws.client_state.name != "CONNECTED":
                    logger.info(f"WebSocket state changed to {ws.client_state.name} [ID: {client_id}]")
                    break
                continue
            if isinstance(msg, dict) and msg.get("type") == "subscribe":
                topics = msg.get("topics")
                if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
                    hub.update_topics(ws, topics)
                    logger.info(f"WebSocket subscriptions updated [ID: {client_id}] -> {topics}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (WebSocketDisconnect) [ID: {client_id}]")
    except Exception as e:
        logger.error(f"WebSocket error [ID: {client_id}]: {e}")
    finally:
        try:
            await ws.close()
        except Exception:
            pass
        hub.remove(ws)
        remaining = hub.count()
        logger.info(f"WebSocket cleanup [ID: {client_id}]. Remaining clients: {remaining}")
