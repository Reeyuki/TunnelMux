import asyncio
from urllib.parse import urlparse
from dotenv import load_dotenv
import websockets, os
import ssl
import certifi

load_dotenv()
domain = os.getenv("DOMAIN")

clientId = "defaultclient"
session_id = "default"

LOCAL_FORWARD_HOST = "127.0.0.1"
LOCAL_FORWARD_PORT = 2222


async def tcp_to_ws(tcp_reader, ws):
    try:
        while True:
            data = await tcp_reader.read(1024)
            if not data:
                await ws.close()
                break
            await ws.send(data)
    except Exception as e:
        print(f"[Client B] tcp_to_ws error: {e}")


async def ws_to_tcp(tcp_writer, ws):
    try:
        async for message in ws:
            tcp_writer.write(message)
            await tcp_writer.drain()
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except Exception as e:
        print(f"[Client B] ws_to_tcp error: {e}")
    finally:
        tcp_writer.close()
        await tcp_writer.wait_closed()


async def handle_connection(local_reader, local_writer):
    addr = local_writer.get_extra_info("peername")
    print(f"[Client B] New SSH client connected from {addr}")

    parsed = urlparse(domain)

    if parsed.scheme in ("http", "https"):
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc
    else:
        scheme = "ws"
        netloc = domain

    VPS_URL = f"{scheme}://{netloc}/ws/client/{clientId}/{session_id}"

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with websockets.connect(VPS_URL, ssl=ssl_context) as ws:
            await asyncio.gather(
                tcp_to_ws(local_reader, ws),
                ws_to_tcp(local_writer, ws),
            )
    except Exception as e:
        print(f"[Client B] WebSocket connection error: {e}")
    finally:
        local_writer.close()
        await local_writer.wait_closed()


async def server():
    server = await asyncio.start_server(
        handle_connection, LOCAL_FORWARD_HOST, LOCAL_FORWARD_PORT
    )
    print(f"[Client B] Listening on {LOCAL_FORWARD_HOST}:{LOCAL_FORWARD_PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    print("[Client B] Starting forwarder...")
    asyncio.run(server())
