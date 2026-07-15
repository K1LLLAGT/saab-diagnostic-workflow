# Remote CAN Protocol

Used by `RemoteCanTransport.kt` (Android) and any desktop client that
wants to reach a vehicle bus through a remote J2534 gateway instead of a
directly-attached adapter. Three transports carry the same JSON message
framing:

- **TCP**: newline-delimited JSON, one message per line.
- **UDP**: one JSON message per datagram (best-effort; used for
  high-rate live-data streaming where an occasional dropped frame is
  acceptable).
- **WebSocket**: one JSON message per text frame (preferred — used by
  the remote diagnostics server, see `backend/app/websocket_remote.py`).

## Message envelope

```json
{
  "type": "can_frame",
  "payload": { "...": "..." },
  "ts": 1718000000.123,
  "session_id": "..."
}
```

`type` is one of: `live_data`, `can_frame`, `dtc_update`, `freeze_frame`,
`chat`, `remote_command`, `guided_test_step`, `session_event` — matching
`src/remote/client.py`'s `MessageType` enum. Keep the two in sync when
adding a new message type.

## `can_frame` payload

```json
{ "id": "0x7E8", "data": "4102DC90", "dlc": 4, "protocol": "ISO15765" }
```

## Connection lifecycle (gateway side)

1. Client opens TCP/WebSocket connection, sends `remote_command`
   `{"command": "open_gateway", "args": {"protocol": "ISO15765", "baud": 500000}}`.
2. Gateway responds with a `session_event` `{"event": "gateway_ready"}`
   or `{"event": "gateway_error", "detail": "..."}`.
3. `can_frame` / `live_data` messages flow bidirectionally until either
   side sends `remote_command` `{"command": "close_gateway"}` or the
   socket closes.

## Auto-reconnect

Clients should retry a dropped connection with exponential backoff
(base 1s, factor 2x, cap 30s) and re-issue `open_gateway` on
reconnect — see `RemoteCanTransport.connectWithRetry` for the Android
reference implementation.
