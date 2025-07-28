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
        if ws.application_state != WebSocketState.DISCONNECTED:
            await ws.close()
    except Exception as e:
        print(f"[Relay] Error closing websocket: {e}")


async def forward(src: WebSocket, dst: WebSocket):
    try:
        while True:
            data = await src.receive_bytes()
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
    except Exception:
        pass


@app.websocket("/ws/client/{client_id}/{session_id}")
async def websocket_client(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    print(f"[Relay] Client connected: {client_id}, session: {session_id}")

    while (client_id, session_id) not in sessions or sessions[(client_id, session_id)][
        1
    ] is None:
        sessions[(client_id, session_id)] = (websocket, None)
        await asyncio.sleep(0.1)

    ssh_ws = sessions[(client_id, session_id)][1]
    sessions[(client_id, session_id)] = (websocket, ssh_ws)

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
    sessions.pop((client_id, session_id), None)
    print(f"[Relay] Session closed: {client_id}, {session_id}")


@app.websocket("/ws/ssh/{client_id}/{session_id}")
async def websocket_ssh(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    print(f"[Relay] SSH connected: {client_id}, session: {session_id}")

    if (client_id, session_id) in sessions:
        client_ws, _ = sessions[(client_id, session_id)]
        sessions[(client_id, session_id)] = (client_ws, websocket)
    else:
        sessions[(client_id, session_id)] = (None, websocket)

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        if (client_id, session_id) in sessions:
            client_ws, ssh_ws = sessions.pop((client_id, session_id))
            if client_ws:
                await safe_ws_close(client_ws)
            if ssh_ws:
                await safe_ws_close(ssh_ws)
        print(f"[Relay] SSH disconnected: {client_id}, {session_id}")
