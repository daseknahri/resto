# Self-hosting OSRM — real road distances & routes (free, unlimited)

The app's delivery distance, fees, and the live map route line all read from one
seam (`backend/tenancy/routing.py`). With no engine configured it uses a
straight-line × road-factor estimate. Point it at an **OSRM** instance and it
switches to **real driving distances + street routes + real ETAs** — no code
change, just one env var. This is the free, owned path to a full
Uber/inDrive-style routing layer.

## Cost
- Software: **free** (open source, OpenStreetMap data).
- A small VPS handles a country extract: **~$10–40/mo** (≈2–4 GB RAM for Morocco
  with the MLD algorithm; 1–2 vCPU). Unlimited requests — no per-call fees.

## One-time setup (Docker, Morocco extract)
Run on the VPS (needs Docker). Swap the region file for another country later.

```bash
# 1. Download the Morocco extract from Geofabrik (~hundreds of MB)
wget https://download.geofabrik.de/africa/morocco-latest.osm.pbf

# 2. Preprocess with the car profile (one-time; the extract/partition/customize steps)
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract   -p /opt/car.lua /data/morocco-latest.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition           /data/morocco-latest.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize           /data/morocco-latest.osrm

# 3. Serve it (MLD algorithm), auto-restart, on port 5000
docker run -d --restart unless-stopped --name osrm -p 5000:5000 \
  -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/morocco-latest.osrm

# 4. Smoke test (Casablanca → nearby) — expect JSON with a "routes" array
curl "http://localhost:5000/route/v1/driving/-7.62,33.59;-7.55,33.57?overview=false"
```

## Point the app at it
Set in Coolify (api service env), then redeploy `api`:

```
DELIVERY_OSRM_URL=http://<osrm-host-or-ip>:5000
```

That's it. The backend immediately uses real road distances for fees and real
street geometry + ETA for the customer/owner tracking map. Results are cached
(distance 7 days, route geometry 1 day on ~110 m coords) and **fall back to the
straight-line estimate automatically if OSRM is ever down** — it can never block
checkout or tracking.

## Operational notes
- **Keep it private.** Expose OSRM only to the api service (internal Docker
  network or firewall), not the public internet.
- **Refresh monthly.** Re-run the download + preprocess steps to pick up new
  roads, then restart the container.
- **Tune the offer window** with `DELIVERY_ROAD_FACTOR` only matters while OSRM
  is off; once on, real distances are used.
- **Upgrade path:** for turn-by-turn / multi-modal / better ETAs later, Valhalla
  is a drop-in alternative (same idea, richer API). OSRM is the simplest start.

## Map tiles (separate concern)
The route engine draws the *line*; the *map image* comes from tile providers.
The app defaults to OpenStreetMap's public tiles (dev only — not licensed for
heavy production). For production set the frontend **build-time** env vars
(see `frontend/src/lib/mapTiles.js`):

```
VITE_MAP_TILE_URL=https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=YOUR_KEY
VITE_MAP_TILE_ATTRIBUTION=© MapTiler © OpenStreetMap contributors
```

MapTiler / Mapbox / Stadia all have free tiers that cover ~500 orders/day. These
are **build-time** vars (baked into the frontend bundle), so they must be present
when the frontend image is built.
