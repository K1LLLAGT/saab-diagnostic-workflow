"""
SAAB-SUITE cloud backend — remote diagnostics WebSocket server.

Streams live data / CAN frames / DTC updates to connected remote
viewers and relays technician chat + remote commands, per session.
Session frames are recorded to disk (JSON-lines) for later playback in
the remote UI's session timeline.

Auth: token passed as a query param (?token=...) since browser
WebSocket clients cannot set Authorization headers; validated the same
way as REST bearer tokens (see backend/app/auth.py).
"""

from __future__ import annotations
import json
import pathlib
import time
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from backend.app.auth import SECRET_KEY, ALGORITHM

router = APIRouter()

SESSION_LOG_DIR = pathlib.Path("remote_sessions")
SESSION_LOG_DIR.mkdir(exist_ok=True)


class SessionHub:
    def __init__(self) -> None:
        self.sessions: Dict[str, List[WebSocket]] = {}

    async def join(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.sessions.setdefault(session_id, []).append(ws)

    def leave(self, session_id: str, ws: WebSocket) -> None:
        peers = self.sessions.get(session_id, [])
        if ws in peers:
            peers.remove(ws)
        if not peers and session_id in self.sessions:
            del self.sessions[session_id]

    async def broadcast(self, session_id: str, message: dict, exclude: WebSocket = None) -> None:
        record_session_event(session_id, message)
        for peer in self.sessions.get(session_id, []):
            if peer is not exclude:
                await peer.send_text(json.dumps(message))


hub = SessionHub()


def record_session_event(session_id: str, message: dict) -> None:
    path = SESSION_LOG_DIR / f"{session_id}.jsonl"
    with open(path, "a") as fh:
        fh.write(json.dumps({**message, "_recorded_at": time.time()}) + "\n")


def _validate_token(token: str) -> bool:
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False


@router.websocket("/remote/{session_id}")
async def remote_session(websocket: WebSocket, session_id: str, token: str = Query(...)):
    if not _validate_token(token):
        await websocket.close(code=4401)
        return

    await hub.join(session_id, websocket)
    await hub.broadcast(session_id, {"type": "session_event", "payload": {"event": "peer_joined"}})

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            # Message types: live_data, can_frame, dtc_update, freeze_frame,
            # chat, remote_command, guided_test_step (see src.remote.client.MessageType)
            await hub.broadcast(session_id, message, exclude=websocket)
    except WebSocketDisconnect:
        hub.leave(session_id, websocket)
        await hub.broadcast(session_id, {"type": "session_event", "payload": {"event": "peer_left"}})


@router.get("/remote/{session_id}/timeline")
def session_timeline(session_id: str):
    path = SESSION_LOG_DIR / f"{session_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
