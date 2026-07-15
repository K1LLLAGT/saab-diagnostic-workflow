"""
SAAB-SUITE — remote diagnostics client.

Thin client for the remote diagnostics WebSocket server
(backend/app/websocket_remote.py): streams live data / CAN frames out,
receives remote commands and technician chat in. Session recording is
handled server-side (see docs/ecosystem-architecture.md).

This module defines the message contract and a synchronous stub client;
a real deployment would use `websockets` or `httpx` async clients from
the desktop/Android UI layer.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MessageType(str, Enum):
    LIVE_DATA = "live_data"
    CAN_FRAME = "can_frame"
    DTC_UPDATE = "dtc_update"
    FREEZE_FRAME = "freeze_frame"
    CHAT = "chat"
    REMOTE_COMMAND = "remote_command"
    GUIDED_TEST_STEP = "guided_test_step"
    SESSION_EVENT = "session_event"


@dataclass
class RemoteMessage:
    type: MessageType
    payload: Dict[str, Any]
    ts: float = field(default_factory=time.time)
    session_id: str = ""

    def to_json(self) -> str:
        return json.dumps({"type": self.type.value, "payload": self.payload,
                            "ts": self.ts, "session_id": self.session_id})

    @classmethod
    def from_json(cls, raw: str) -> "RemoteMessage":
        data = json.loads(raw)
        return cls(type=MessageType(data["type"]), payload=data["payload"],
                    ts=data.get("ts", time.time()), session_id=data.get("session_id", ""))


class RemoteDiagnosticsClient:
    """
    Role-based access is enforced server-side (see backend/app/auth.py);
    this client only carries the bearer token and session id. End-to-end
    encryption is provided by TLS (wss://) at the transport layer — no
    payload-level encryption is implemented here.
    """

    def __init__(self, ws_url: str, access_token: str, session_id: str):
        self.ws_url = ws_url
        self.access_token = access_token
        self.session_id = session_id
        self._handlers: Dict[MessageType, List[Callable[[RemoteMessage], None]]] = {}

    def on(self, msg_type: MessageType, handler: Callable[[RemoteMessage], None]) -> None:
        self._handlers.setdefault(msg_type, []).append(handler)

    def dispatch(self, raw: str) -> None:
        msg = RemoteMessage.from_json(raw)
        for handler in self._handlers.get(msg.type, []):
            handler(msg)

    def build_live_data(self, values: Dict[str, float]) -> RemoteMessage:
        return RemoteMessage(MessageType.LIVE_DATA, {"values": values}, session_id=self.session_id)

    def build_chat(self, author: str, text: str) -> RemoteMessage:
        return RemoteMessage(MessageType.CHAT, {"author": author, "text": text}, session_id=self.session_id)

    def build_remote_command(self, command: str, args: Optional[dict] = None) -> RemoteMessage:
        return RemoteMessage(MessageType.REMOTE_COMMAND, {"command": command, "args": args or {}},
                              session_id=self.session_id)
