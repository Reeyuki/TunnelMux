

# WebSocket SSH Relay

This project allows you to **access a remote SSH server through a WebSocket tunnel**. It is useful for bypassing NAT/firewall restrictions, exposing SSH over HTTPS/WSS, or securely tunneling SSH sessions via a central relay server.

The system consists of **three main components**:

1. **Local Proxy (`localproxy.py`)**
2. **Relay Server (`app.py`)**
3. **Remote Agent (`remoteagent.py`)**

---

## **1. Local Proxy (`localproxy.py`)**

Acts as a **local TCP-to-WebSocket forwarder**.

* Listens on your local machine (e.g., `127.0.0.1:22`) for incoming SSH connections.
* Forwards the TCP traffic to the **Relay Server** over a WebSocket connection.
* Converts TCP → WebSocket and WebSocket → TCP.

**Configuration:**

* `.env` file:

  ```env
  DOMAIN=<relay-server-domain>
  TOKEN=<auth-token>
  SESSION_ID=<session-id>
  SSH_PORT=<local-port-to-forward>  # default 22
  ```

**Run:**

```bash
python localproxy.py
```

After starting, you can SSH to `127.0.0.1` and your traffic will be forwarded to the remote SSH server through the relay.

---

## **2. Relay Server (`app.py`)**

Acts as a **central hub** that connects the local proxy with the remote agent.

* Implements a FastAPI WebSocket server.
* Endpoints:

  * `/ws/client/{client_id}/{session_id}` → for local proxy connections.
  * `/ws/ssh/{client_id}/{session_id}` → for remote agent connections.
* Forwards bytes between connected client and SSH WebSockets.
* Authenticates connections using a shared token from `.env`.

**Features:**

* Session management via `(client_id, session_id)` keys.
* Safe WebSocket closing and timeout handling.
* Logging of connections and disconnections.

**Run:**

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## **3. Remote Agent (`remoteagent.py`)**

Runs on the remote machine (or where the SSH server is accessible).

* Connects to the relay server via WebSocket (`/ws/ssh/<clientId>/<session_id>`).
* Opens a TCP connection to the local SSH server.
* Forwards TCP → WebSocket and WebSocket → TCP.
* Automatically reconnects if the connection fails.

**Configuration:**

* `.env` file:

  ```env
  DOMAIN=<relay-server-domain>
  CLIENT_ID=<client-id>
  SESSION_ID=<session-id>
  SSH_PORT=<remote-ssh-port>  # usually 22
  ```

**Run:**

```bash
python remoteagent.py
```

---

## **How It Works**

```
[Your SSH Client] 
      │
      ▼
[localproxy.py] --TCP--> [Relay Server (app.py)] --WS--> [remoteagent.py] --TCP--> [Remote SSH Server]
```

1. You SSH to `127.0.0.1` on your local machine.
2. `localproxy.py` forwards TCP traffic over WebSocket to the relay server.
3. Relay waits for the remote agent to connect.
4. Relay forwards bytes between local proxy and remote agent.
5. `remoteagent.py` converts WebSocket traffic back to TCP and sends it to the SSH server.

---

## **Use Cases**

* SSH to servers behind NAT/firewalls without port forwarding.
* Tunnel SSH over HTTPS/WSS to bypass network restrictions.
* Secure session-based SSH access with token authentication.
