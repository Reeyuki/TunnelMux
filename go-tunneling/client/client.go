package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

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

func main() {
	clientID := os.Getenv("CLIENT_ID")
	if clientID == "" {
		clientID = "machine1"
	}
	cloudURL := os.Getenv("CLOUD_URL")
	if cloudURL == "" {
		cloudURL = "ws://127.0.0.1:8080"
	}
	localAPI := os.Getenv("LOCAL_API")
	if localAPI == "" {
		localAPI = "http://127.0.0.1:5005"
	}

	wsURL := strings.TrimRight(cloudURL, "/") + "/ws?client_id=" + clientID

	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		log.Fatal("WebSocket dial:", err)
	}
	defer conn.Close()

	for {
		_, msgBytes, err := conn.ReadMessage()
		if err != nil {
			log.Println("Read error:", err)
			break
		}

		var msg Message
		if err := json.Unmarshal(msgBytes, &msg); err != nil {
			log.Println("Invalid message JSON:", err)
			continue
		}

		reqBody := bytes.NewReader([]byte(msg.Body))
		req, err := http.NewRequest(msg.Method, localAPI+msg.Path, reqBody)
		if err != nil {
			log.Println("Failed to create request:", err)
			continue
		}

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			log.Println("Local request error:", err)
			continue
		}

		bodyBytes, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			log.Println("Failed to read local response body:", err)
			continue
		}

		respMsg := Message{
			ID:      msg.ID,
			Status:  resp.StatusCode,
			Headers: map[string]string{},
			Body:    string(bodyBytes),
		}
		for k, v := range resp.Header {
			if len(v) > 0 {
				respMsg.Headers[k] = v[0]
			}
		}

		if err := conn.WriteJSON(respMsg); err != nil {
			log.Println("WebSocket write error:", err)
			break
		}
	}
}
