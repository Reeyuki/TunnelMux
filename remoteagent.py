import asyncio
from urllib.parse import urlparse
import websockets
import os
from dotenv import load_dotenv
import ssl
import certifi

load_dotenv()
domain = os.getenv("DOMAIN")

clientId = "defaultclient"
session_id = "default"
LOCAL_SSH_HOST = "127.0.0.1"
LOCAL_SSH_PORT = 22


async def tcp_to_ws(tcp_reader, ws):
    try:
        while True:
            data = await tcp_reader.read(1024)
            if not data:
                print("[Client A] Local SSH connection closed")
                await ws.close()
                break
            await ws.send(data)
    except Exception as e:
        print(f"[Client A] tcp_to_ws error: {e}")


async def ws_to_tcp(tcp_writer, ws):
    try:
        async for message in ws:
            tcp_writer.write(message)
            await tcp_writer.drain()
    except websockets.exceptions.ConnectionClosedOK:
        print("[Client A] WebSocket closed by server")
    except Exception as e:
        print(f"[Client A] ws_to_tcp error: {e}")
    finally:
        tcp_writer.close()
        await tcp_writer.wait_closed()


async def run_session():
    parsed = urlparse(domain)
    if parsed.scheme in ("http", "https"):
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc
    else:
        scheme = "ws"
        netloc = domain
    VPS_URL = f"{scheme}://{netloc}/ws/client/{clientId}/{session_id}"

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with websockets.connect(VPS_URL, ssl=ssl_context) as ws:
        reader, writer = await asyncio.open_connection(LOCAL_SSH_HOST, LOCAL_SSH_PORT)
        print("[Client A] Connected to VPS and local SSH")
        await asyncio.gather(
            tcp_to_ws(reader, ws),
            ws_to_tcp(writer, ws),
        )


async def main_loop():
    while True:
        try:
            await run_session()
        except Exception as e:
            print(f"[Client A] Connection/session error: {e}")
        print("[Client A] Session ended, reconnecting ...")
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main_loop())
