# Tunneling

## Overview
A tunneling app written in go that forwards HTTP requests from a cloud server to remote machines running a local API (`localhost:5005`). Supports multiple clients.

---

## Components

### **Server (cloud)**
- Receives HTTP requests.
- Forwards requests to connected clients via WebSocket.
- Returns client responses to the requester.

### **Client (remote machine)**
- Connects to the server via WebSocket.
- Forwards requests to local API (`localhost:5005`).
- Sends response back to the server.

---

## Environment Variables

**Client:**
- `CLIENT_ID` – Unique identifier for the remote machine (e.g., `machine1`).
- `CLOUD_DOMAIN` – Cloud server address (IP or domain).
- `LOCAL_API` – Local API URL (`http://127.0.0.1:5005` by default).

**Server:**  
- Default listens on `0.0.0.0:8080`.
