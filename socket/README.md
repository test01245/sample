# Go Socket Client (VM agent)

A minimal Go client that connects to your Flask Socket.IO server and handles:

- authenticate (using device token from /publickey)
- device_hello (sends hostname)
- encrypt/decrypt signals (no-op placeholders; hook in your logic if needed)
- run_script: executes a shell command and returns basic logs

## Build

Requires Go 1.21+.

```
go mod tidy

go build -o socket-agent
```

## Run

```
./socket-agent --backend https://sample-2ang.onrender.com/py_simple --insecure
```

Flags:
- `--backend` Backend base URL (may include /py_simple). Required.
- `--hostname` Optional override; default is OS hostname.
- `--insecure` Skip TLS verification (lab only).

