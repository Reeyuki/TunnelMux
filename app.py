import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from typing import Dict, Tuple
from starlette.websockets import WebSocketState
import os, time
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

token = os.getenv("TOKEN")

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
            if dst.application_state != WebSocketState.CONNECTED:
                print("[Relay] Destination WS not connected, exiting forward loop")
                break
            await dst.send_bytes(data)
    except Exception as e:
        print(f"[Relay] Forward error: {e}")


@app.websocket("/ws/client/{client_id}/{session_id}")
async def websocket_client(websocket: WebSocket, client_id: str, session_id: str):
    query_params = websocket.query_params
    _token = query_params.get("token")
    if _token != token:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    print(f"[Relay] Client WS connected: {client_id}, session: {session_id}")
    key = (client_id, session_id)
    sessions[key] = (websocket, sessions.get(key, (None, None))[1])

    while sessions[key][1] is None:
        await asyncio.sleep(0.1)

    ssh_ws = sessions[key][1]
    print(f"[Relay] Both sides ready, starting forwarding: {key}")

    forward_client = asyncio.create_task(forward(websocket, ssh_ws))
    forward_ssh = asyncio.create_task(forward(ssh_ws, websocket))

    done, pending = await asyncio.wait(
        [forward_client, forward_ssh],
        return_when=asyncio.FIRST_COMPLETED,
    )

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
    sessions[key] = (sessions.get(key, (None, None))[0], websocket)

    while sessions[key][0] is None:
        await asyncio.sleep(0.1)

    try:
        timeout = 300
        start_time = time.time()
        while True:
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            if time.time() - start_time > timeout:
                print(f"[Relay] SSH WS timeout reached, closing: {key}")
                break
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if key in sessions:
            client_ws, ssh_ws = sessions.pop(key)
            await safe_ws_close(client_ws)
            await safe_ws_close(ssh_ws)
        print(f"[Relay] SSH disconnected: {client_id}, {session_id}")
