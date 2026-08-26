# Chrome QUIC Issue

Symptoms

- Waiting for connection from debug service...
- CanvasKit wasm failed
- ERR_QUIC_PROTOCOL_ERROR

Cause

Chrome attempted to download canvaskit.wasm using QUIC.

Network blocked UDP/443.

Solution

flutter run -d chrome --web-browser-flag="--disable-quic"

or

Disable QUIC in chrome://flags.
