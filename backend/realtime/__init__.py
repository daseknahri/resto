# Real-time (WebSocket) support. Intentionally empty so that
# `from realtime.broadcast import broadcast` never transitively imports Channels —
# the HTTP request path must stay importable even when channels isn't installed.
