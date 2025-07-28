import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from typing import Dict, Tuple
from starlette.websockets import WebSocketState

app = FastAPI()

sessions: Dict[Tuple[str, str], Tuple[WebSocket, WebSocket]] = {}


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


async def safe_ws_close(ws: WebSocket):
    try:
        if ws and ws.application_state != WebSocketState.DISCONNECTED:
            await ws.close()
            print("[Relay] Closed websocket safely")
    except Exception as e:
        print(f"[Relay] Error closing websocket: {e}")


async def forward(src: WebSocket, dst: WebSocket):
    try:
        while True:
            data = await src.receive_bytes()
            print(f"[Relay] Forwarding {len(data)} bytes")
            if dst.application_state != WebSocketState.CONNECTED:
                print("[Relay] Destination WS not connected, exiting forward loop")
                break
            try:
                await dst.send_bytes(data)
            except RuntimeError as e:
                if 'Cannot call "send" once a close message has been sent.' in str(e):
                    print(
                        "[Relay] Tried to send on closed websocket, exiting forward loop"
                    )
                    break
                else:
                    raise
    except Exception as e:
        print(f"[Relay] Forward error: {e}")


@app.websocket("/ws/client/{client_id}/{session_id}")
async def websocket_client(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    print(f"[Relay] Client WS connected: {client_id}, session: {session_id}")

    key = (client_id, session_id)
    while True:
        old = sessions.get(key)
        if old is None:
            sessions[key] = (websocket, None)
            print(f"[Relay] Session created for {key} with client WS only")
            break
        else:
            client_ws, ssh_ws = old
            if ssh_ws is not None:
                if client_ws != websocket:
                    sessions[key] = (websocket, ssh_ws)
                    print(f"[Relay] SSH WS present, session ready: {key}")
                else:
                    print(f"[Relay] Client WS already set for session: {key}")
                break
            else:
                if client_ws != websocket:
                    sessions[key] = (websocket, None)
                    print(
                        f"[Relay] Waiting for SSH WS for session {key} - updated client WS"
                    )
                else:
                    print(f"[Relay] Waiting for SSH WS for session {key}")
                await asyncio.sleep(0.1)

    ssh_ws = sessions[key][1]
    print(f"[Relay] Starting forwarding tasks for session {key}")

    forward_client = asyncio.create_task(forward(websocket, ssh_ws))
    forward_ssh = asyncio.create_task(forward(ssh_ws, websocket))

    done, pending = await asyncio.wait(
        [forward_client, forward_ssh],
        return_when=asyncio.FIRST_COMPLETED,
    )

    print(f"[Relay] Forwarding tasks done for session {key}. Cancelling pending.")
    for task in pending:
        task.cancel()

    await safe_ws_close(websocket)
    await safe_ws_close(ssh_ws)
    sessions.pop(key, None)
    print(f"[Relay] Session closed: {client_id}, {session_id}")


@app.websocket("/ws/ssh/{client_id}/{session_id}")
async def websocket_ssh(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    print(f"[Relay] SSH WS connected: {client_id}, session: {session_id}")

    key = (client_id, session_id)
    while True:
        old = sessions.get(key)
        if old is None:
            sessions[key] = (None, websocket)
            print(f"[Relay] Session created for {key} with SSH WS only")
            break
        else:
            client_ws, ssh_ws = old
            if client_ws is not None:
                if ssh_ws != websocket:
                    sessions[key] = (client_ws, websocket)
                    print(f"[Relay] Client WS present, session ready: {key}")
                else:
                    print(f"[Relay] SSH WS already set for session: {key}")
                break
            else:
                if ssh_ws != websocket:
                    sessions[key] = (client_ws, websocket)
                    print(
                        f"[Relay] Waiting for Client WS for session {key} - updated SSH WS"
                    )
                else:
                    print(f"[Relay] Waiting for Client WS for session {key}")
                await asyncio.sleep(0.1)

    client_ws = sessions[key][0]

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        if key in sessions:
            client_ws, ssh_ws = sessions.pop(key)
            if client_ws:
                await safe_ws_close(client_ws)
            if ssh_ws:
                await safe_ws_close(ssh_ws)
        print(f"[Relay] SSH disconnected: {client_id}, {session_id}")
