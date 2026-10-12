from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[job_id] = websocket

    def disconnect(self, job_id: str) -> None:
        self.active_connections.pop(job_id, None)

    async def send_progress(self, job_id: str, data: dict) -> None:
        #Sends a progress event to the client connected to this job, if any
        websocket = self.active_connections.get(job_id)
        if websocket is not None:
            try:
                await websocket.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()