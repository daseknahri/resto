# Real-time (WebSockets) — setup & operations

Real-time push for the owner workspace, built on **Django Channels**. Today it
powers instant order updates — `order.new` when a customer places an order and
`order.updated` when any device changes an order's status — so the kitchen, the
orders badge, and every open owner screen stay in sync without waiting for the
poll. The same tenant-scoped infrastructure is reusable for **waiter-call**,
**internal chat**, and a **live driver order feed** by adding new event types and
consumers.

## Design guarantees

- **Additive / non-breaking.** WebSockets *augment* the existing polling; they
  never replace it. If Channels isn't installed, Redis isn't set, or the socket
  can't connect, the app keeps working on its 10s/30s polling. Nothing to roll
  back if the WS layer is down.
- **Conditional activation.** `config/settings.py` registers Channels only when
  the package is importable (`HAS_CHANNELS`). With it absent, the app runs exactly
  as before (verified: `manage.py check` passes without channels installed).
- **Strict tenant isolation.** Each socket joins a group named
  `t.<schema>.<channel>` (`realtime/groups.py`); a broadcast can only reach
  sockets that joined the *same tenant's* group.
- **No PII over the wire.** Broadcasts are low-sensitivity "something changed"
  pings (e.g. `{"event": "order.new", "payload": {"order_number": "..."}}`). The
  client refetches details over the authenticated HTTP API — the socket is never
  trusted as a data source.
- **Authorisation mirrors HTTP.** `OwnerConsumer` admits a socket only if the
  session user is platform admin, or belongs to this tenant with role
  `TENANT_OWNER`/`TENANT_STAFF` — identical to `IsTenantEditorOrReadOnly`. A
  logged-in *customer* on the same host cannot join the owner channel.

## What ships in code

| Piece | File |
|---|---|
| Group naming (tenant isolation) | `backend/realtime/groups.py` |
| Guarded broadcast helper | `backend/realtime/broadcast.py` |
| Host → tenant WS middleware | `backend/realtime/middleware.py` |
| `OwnerConsumer` (auth + groups) | `backend/realtime/consumers.py` |
| WS routing (`/ws/owner/`) | `backend/realtime/routing.py` |
| ASGI app (HTTP + WS router) | `backend/config/asgi.py` |
| Channel layer + app registration | `backend/config/settings.py` |
| New-order emit | `backend/menu/views.py` (after the push hook) |
| Frontend client (graceful, reconnect) | `frontend/src/composables/useOwnerRealtime.js` |
| Wired into the owner shell | `frontend/src/layouts/OwnerLayout.vue` |

## Deploy on Coolify

WebSockets require an **ASGI** server and (for multi-worker prod) a **Redis**
channel layer. HTTP can keep running under gunicorn until you cut over.

1. **Install deps** — already in `requirements.txt` (`channels`, `channels-redis`,
   `daphne`, `uvicorn[standard]`). Rebuild the backend image.
2. **Set `REDIS_URL`** in the backend service env (e.g. `redis://default:<pw>@redis:6379/0`).
   - Without it, Channels falls back to an in-memory layer that only works in a
     single process — fine for a quick test, **not** for multi-worker prod (a
     broadcast from one worker won't reach sockets on another).
   - You likely already run Redis for the cache; the same instance is fine
     (the channel layer uses its own `resto:ws` key prefix).
3. **Serve under ASGI.** Change the backend run/start command from gunicorn (WSGI)
   to uvicorn (ASGI):
   ```
   uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers
   ```
   (or `daphne -b 0.0.0.0 -p 8000 config.asgi:application`).
4. **Proxy must allow WS upgrade.** Coolify's Traefik proxies `Upgrade`/`Connection`
   headers by default for the service; just confirm `/ws/` reaches the backend
   (same host/path as the API). The client connects to `wss://<tenant-host>/ws/owner/`.

## Verify after deploy

- Open the owner dashboard; in devtools → Network → WS you should see
  `/ws/owner/` connect (status 101).
- Place a test order from the customer menu → the owner orders badge / kitchen
  should update **immediately** (not on the next poll).
- Sanity-check isolation: a second tenant's dashboard must **not** react to the
  first tenant's order.
- Confirm a logged-out / customer session does **not** get a 101 on `/ws/owner/`
  (expect close code 4403).

## Adding more event types (waiter call, chat, driver feed)

1. Emit from the relevant view: `from realtime.broadcast import broadcast` then
   `broadcast(schema_name, "owner", "waiter.call", {...})` (guarded no-op if WS off).
2. Handle the new `event` string in the frontend `useOwnerRealtime` callback.
3. For a distinct audience (e.g. drivers), add a new channel name + a consumer
   with its own authorisation, and a matching route in `realtime/routing.py`.
