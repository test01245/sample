package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

type DeviceRegisterResp struct {
	DeviceToken string `json:"device_token"`
	WsURL       string `json:"ws_url"`
}

type SocketMessage struct {
	Type string          `json:"type"`
	Data json.RawMessage `json:"data"`
}

func backendOrigin(base string) string {
	u, err := url.Parse(base)
	if err != nil {
		return base
	}
	return (&url.URL{Scheme: u.Scheme, Host: u.Host}).String()
}

func joinURL(base, path string) string {
	return strings.TrimRight(base, "/") + "/" + strings.TrimLeft(path, "/")
}

func registerDevice(base, hostname string) (DeviceRegisterResp, error) {
	body := map[string]string{"hostname": hostname}
	buf, _ := json.Marshal(body)
	resp, err := http.Post(joinURL(base, "/publickey"), "application/json", bytes.NewReader(buf))
	if err != nil {
		return DeviceRegisterResp{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		return DeviceRegisterResp{}, fmt.Errorf("register failed: %s", string(b))
	}
	var out DeviceRegisterResp
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return out, err
	}
	return out, nil
}

func main() {
	backend := flag.String("backend", os.Getenv("BACKEND_URL"), "Backend base URL (e.g. https://sample-2ang.onrender.com/py_simple)")
	hostname := flag.String("hostname", "go-client", "Hostname to report")
	insecure := flag.Bool("insecure", false, "Skip TLS verification (not recommended)")
	flag.Parse()

	if *backend == "" {
		log.Fatal("--backend is required or set BACKEND_URL")
	}

	reg, err := registerDevice(*backend, *hostname)
	if err != nil {
		log.Fatalf("register error: %v", err)
	}
	log.Printf("Device token: %s", reg.DeviceToken)

	origin := backendOrigin(*backend)
	// Engine.IO path is usually /socket.io/ with query transport=websocket&EIO=4
	wsURL := fmt.Sprintf("%s/socket.io/?transport=websocket&EIO=4", strings.TrimRight(origin, "/"))
	if *insecure {
		log.Printf("[warn] insecure TLS is not implemented in this simple client; relying on system trust store")
	}

	dialer := websocket.Dialer{HandshakeTimeout: 20 * time.Second}
	conn, _, err := dialer.Dial(wsURL, http.Header{"Origin": {origin}})
	if err != nil {
		log.Fatalf("websocket dial error: %v", err)
	}
	defer conn.Close()
	log.Printf("Connected to %s", wsURL)

	// Authenticate: emit 42["authenticate",{"device_token":"..."}]
	authPayload := map[string]any{"device_token": reg.DeviceToken}
	authEvent := []any{"authenticate", authPayload}
	authFrame, _ := json.Marshal(authEvent)
	if err := conn.WriteMessage(websocket.TextMessage, append([]byte("42"), authFrame...)); err != nil {
		log.Fatalf("auth write failed: %v", err)
	}

	// Listen loop
	done := make(chan struct{})
	go func() {
		for {
			_, msg, err := conn.ReadMessage()
			if err != nil {
				log.Printf("read error: %v", err)
				close(done)
				return
			}
			// Minimal Socket.IO frame parsing
			if len(msg) < 2 {
				continue
			}
			// 42 -> event packet; strip prefix and parse [eventName, data]
			if msg[0] == '4' && msg[1] == '2' {
				payload := msg[2:]
				var event []any
				if err := json.Unmarshal(payload, &event); err != nil {
					log.Printf("bad event: %s", string(payload))
					continue
				}
				if len(event) < 1 {
					continue
				}
				name, _ := event[0].(string)
				var data json.RawMessage
				if len(event) > 1 {
					sw, _ := json.Marshal(event[1])
					data = json.RawMessage(sw)
				}
				switch name {
				case "encrypt":
					log.Println("[go-client] encrypt requested (simulation placeholder)")
				case "decrypt":
					log.Println("[go-client] decrypt requested (simulation placeholder)")
				case "run_script":
					var obj struct{ Command string `json:"command"` }
					_ = json.Unmarshal(data, &obj)
					log.Printf("[go-client] run_script: %s (not executed in Go client)", obj.Command)
				case "hello":
					log.Println("hello from server")
				case "auth_ok":
					log.Println("authenticated")
				default:
					log.Printf("event %s: %s", name, string(data))
				}
			}
		}
	}()

	// Clean shutdown
	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt, syscall.SIGTERM)
	select {
	case <-done:
		log.Println("socket closed")
	case <-interrupt:
		log.Println("interrupt, closing…")
		_ = conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
		select {
		case <-done:
		case <-time.After(time.Second):
		}
	}
}
