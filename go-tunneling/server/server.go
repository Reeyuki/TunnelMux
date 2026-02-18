package main

import (
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Message struct {
	ID      string            `json:"id"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Headers map[string]string `json:"headers"`
	Body    string            `json:"body"`
	Status  int               `json:"status,omitempty"`
}

var (
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool {
			return true
		},
	}

	clients      = make(map[string]*websocket.Conn)
	clientIDs    []string
	nextIndex    = 0
	lock         sync.Mutex
	pendingResp  = make(map[string]chan Message)
	pendingMutex sync.Mutex
)

func wsHandler(w http.ResponseWriter, r *http.Request) {
	clientID := r.URL.Query().Get("client_id")
	if clientID == "" {
		http.Error(w, "missing client_id", http.StatusBadRequest)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade error:", err)
		return
	}

	lock.Lock()
	clients[clientID] = conn
	clientIDs = append(clientIDs, clientID)
	lock.Unlock()

	log.Println("Client", clientID, "connected")

	defer func() {
		lock.Lock()
		delete(clients, clientID)
		for i, id := range clientIDs {
			if id == clientID {
				clientIDs = append(clientIDs[:i], clientIDs[i+1:]...)
				break
			}
		}
		lock.Unlock()
		log.Println("Client", clientID, "disconnected")
		conn.Close()
	}()

	for {
		var msg Message
		if err := conn.ReadJSON(&msg); err != nil {
			log.Println("Read error:", err)
			break
		}

		if msg.ID != "" {
			pendingMutex.Lock()
			if ch, ok := pendingResp[msg.ID]; ok {
				ch <- msg
			}
			pendingMutex.Unlock()
		}
	}
}

func forwardToNextClient(msg Message) (Message, error) {
	lock.Lock()
	if len(clientIDs) == 0 {
		lock.Unlock()
		return Message{}, fmt.Errorf("no clients connected")
	}
	clientID := clientIDs[nextIndex]
	nextIndex = (nextIndex + 1) % len(clientIDs)
	conn := clients[clientID]
	lock.Unlock()

	msg.ID = fmt.Sprintf("%p", &msg)
	ch := make(chan Message, 1)

	pendingMutex.Lock()
	pendingResp[msg.ID] = ch
	pendingMutex.Unlock()

	if err := conn.WriteJSON(msg); err != nil {
		pendingMutex.Lock()
		delete(pendingResp, msg.ID)
		pendingMutex.Unlock()
		return Message{}, err
	}

	select {
	case resp := <-ch:
		pendingMutex.Lock()
		delete(pendingResp, msg.ID)
		pendingMutex.Unlock()
		return resp, nil

	case <-time.After(5 * time.Second):
		pendingMutex.Lock()
		delete(pendingResp, msg.ID)
		pendingMutex.Unlock()
		return Message{}, fmt.Errorf("client response timeout")
	}
}

func proxyHandler(w http.ResponseWriter, r *http.Request) {
	body := make([]byte, r.ContentLength)
	r.Body.Read(body)

	headers := make(map[string]string)
	for k, v := range r.Header {
		headers[k] = v[0]
	}

	msg := Message{
		Method:  r.Method,
		Path:    r.URL.Path,
		Headers: headers,
		Body:    string(body),
	}

	resp, err := forwardToNextClient(msg)
	if err != nil {
		if err.Error() == "client response timeout" {
			w.WriteHeader(http.StatusGatewayTimeout)
			w.Write([]byte(`{"error":"timeout"}`))
			return
		}
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}

	for k, v := range resp.Headers {
		if k == "Content-Length" || k == "Transfer-Encoding" || k == "Connection" {
			continue
		}
		w.Header().Set(k, v)
	}

	if resp.Status > 0 {
		w.WriteHeader(resp.Status)
	}
	w.Write([]byte(resp.Body))
}

func main() {
	http.HandleFunc("/ws", wsHandler)
	http.HandleFunc("/", proxyHandler)
	log.Println("Server listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
