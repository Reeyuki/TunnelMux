import asyncio
import websockets

domain = "localhost:8080"
clientId = "defaultclient"
session_id = "default"

LOCAL_FORWARD_HOST = "127.0.0.1"
LOCAL_FORWARD_PORT = 2222


async def tcp_to_ws(tcp_reader, ws):
    try:
        while True:
            data = await tcp_reader.read(1024)
            if not data:
                print("[Client B] TCP connection closed by SSH client")
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
        print("[Client B] WebSocket closed by server")
    except Exception as e:
        print(f"[Client B] ws_to_tcp error: {e}")
    finally:
        tcp_writer.close()
        await tcp_writer.wait_closed()


async def handle_connection(local_reader, local_writer):
    addr = local_writer.get_extra_info("peername")
    VPS_URL = f"ws://{domain}/ws/ssh/{clientId}/{session_id}"
    print(f"[Client B] New SSH client connected from {addr}")

    try:
        async with websockets.connect(VPS_URL) as ws:
            print("[Client B] WebSocket connected to VPS")
            await asyncio.gather(
                tcp_to_ws(local_reader, ws),
                ws_to_tcp(local_writer, ws),
            )
    except Exception as e:
        print(f"[Client B] WebSocket connection error: {e}")
    finally:
        print("[Client B] Closing local TCP connection")
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
