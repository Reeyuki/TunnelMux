import asyncio
from urllib.parse import urlparse
import websockets
import os
from dotenv import load_dotenv
import ssl
import certifi

load_dotenv()

domain = os.getenv("DOMAIN")
clientId = os.getenv("CLIENT_ID", "defaultclient")
session_id = os.getenv("SESSION_ID", "default")
LOCAL_SSH_PORT = int(os.getenv("SSH_PORT", "22"))

LOCAL_SSH_HOST = "127.0.0.1"


def build_ws_url(path):
    parsed = urlparse(domain)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc if parsed.netloc else parsed.path
    return f"{scheme}://{netloc}{path}"


ssl_context = ssl.create_default_context(cafile=certifi.where())


async def remote_agent_main():
    url = build_ws_url(f"/ws/ssh/{clientId}/{session_id}")
    async with websockets.connect(url, ssl=ssl_context) as ws:
        reader, writer = await asyncio.open_connection(LOCAL_SSH_HOST, LOCAL_SSH_PORT)
        print("[Client A] Connected to local SSH and relay")

        await asyncio.gather(
            tcp_to_ws(reader, ws),
            ws_to_tcp(writer, ws),
        )


async def tcp_to_ws(reader, ws):
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                print("[Client A] Local SSH connection closed")
                await ws.close()
                break
            await ws.send(data)
    except Exception as e:
        print(f"[Client A] tcp_to_ws error: {e}")


async def ws_to_tcp(writer, ws):
    try:
        async for message in ws:
            writer.write(message)
            await writer.drain()
    except websockets.exceptions.ConnectionClosedOK:
        print("[Client A] WebSocket closed")
    except Exception as e:
        print(f"[Client A] ws_to_tcp error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main_loop():
    while True:
        try:
            await remote_agent_main()
        except Exception as e:
            print(f"[Client A] Connection/session error: {e}")
        print("[Client A] Session ended, reconnecting...")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main_loop())
