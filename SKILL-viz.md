# SKILL: sentinel-viz — 3D globe visualisation layer

## Purpose
This skill governs all work in `packages/sentinel-viz/`. It covers CesiumJS
setup, the data layer architecture, the WebSocket event consumer, shader/post-FX
pipeline, and the control panel UI. Read this before adding a new data layer,
writing a shader, or changing how the globe consumes bus events.

---

## What this module does
`sentinel-viz` is Layer 3 — the browser-based 3D geospatial intelligence
dashboard. It is a Vite + vanilla JS single-page application that renders a
CesiumJS globe, consumes the sentinel bus via WebSocket, and visualises live
aircraft, vessels, satellites, OSINT profile overlays, RF detections, and AI
alerts. It also provides shader/post-FX modes (NVG, FLIR, CRT) and a camera
preset system.

---

## Repository layout

```
packages/sentinel-viz/
├── src/
│   ├── main.js                  # Entry point — initialise Cesium, mount layers, open WS
│   ├── globe.js                 # CesiumViewer setup, camera helpers, preset system
│   ├── bus.js                   # WebSocket client, event router
│   ├── layers/
│   │   ├── LayerManager.js      # Registry and toggle controller
│   │   ├── AircraftLayer.js
│   │   ├── VesselLayer.js
│   │   ├── SatelliteLayer.js
│   │   ├── SeismicLayer.js
│   │   ├── TrafficLayer.js
│   │   ├── ProfileLayer.js      # OSINT profile pins
│   │   └── CctvLayer.js
│   ├── shaders/
│   │   ├── PostFxManager.js     # Post-processing pass manager
│   │   ├── nvg.glsl
│   │   ├── flir.glsl
│   │   ├── crt.glsl
│   │   └── bloom.glsl
│   ├── ui/
│   │   ├── ControlPanel.js      # Left sidebar: layer toggles, shader controls
│   │   ├── AlertDrawer.js       # Right sidebar: AI alerts
│   │   ├── InfoPanel.js         # Click-on-entity info popup
│   │   └── CameraPresets.js     # Q-T keyboard shortcuts
│   └── config.js                # Reads import.meta.env (Vite env vars)
├── public/
│   └── index.html
├── vite.config.js
└── package.json
```

---

## CesiumJS setup (globe.js)

```javascript
// src/globe.js
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { config } from './config.js';

export function initGlobe(containerId) {
  Cesium.Ion.defaultAccessToken = config.cesiumToken;

  const viewer = new Cesium.Viewer(containerId, {
    terrainProvider: await Cesium.createWorldTerrainAsync(),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    shadows: false,               // Disable for performance
    requestRenderMode: true,      // Only render on data change — critical for battery life
    maximumRenderTimeChange: 0.5,
  });

  // Google Photorealistic 3D Tiles
  try {
    const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(2275207);
    viewer.scene.primitives.add(tileset);
    // Hide default globe imagery under the 3D tiles
    viewer.scene.globe.show = false;
  } catch (e) {
    console.warn('Google 3D Tiles unavailable, falling back to terrain', e);
    viewer.scene.globe.show = true;
  }

  return viewer;
}
```

**requestRenderMode is critical.** Without it, CesiumJS renders at 60fps even
when nothing is moving, consuming 100% GPU on the client. Always enable it.
Call `viewer.scene.requestRender()` after any data update.

---

## Bus WebSocket client (bus.js)

```javascript
// src/bus.js
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

export class BusClient {
  constructor(url, onEvent) {
    this._url = url;
    this._onEvent = onEvent;
    this._ws = null;
    this._reconnectDelay = RECONNECT_BASE_MS;
    this._filterSpec = null;
  }

  connect(filterSpec = null) {
    this._filterSpec = filterSpec;
    this._open();
  }

  _open() {
    this._ws = new WebSocket(this._url);

    this._ws.onopen = () => {
      console.log('[bus] connected');
      this._reconnectDelay = RECONNECT_BASE_MS;
      // Send filter spec so the server only forwards matching events
      if (this._filterSpec) {
        this._ws.send(JSON.stringify({ type: 'filter', spec: this._filterSpec }));
      }
    };

    this._ws.onmessage = (evt) => {
      try {
        const envelope = JSON.parse(evt.data);
        this._onEvent(envelope);
      } catch (e) {
        console.warn('[bus] bad message', e);
      }
    };

    this._ws.onclose = () => {
      console.log(`[bus] closed, reconnecting in ${this._reconnectDelay}ms`);
      setTimeout(() => this._open(), this._reconnectDelay);
      this._reconnectDelay = Math.min(this._reconnectDelay * 2, RECONNECT_MAX_MS);
    };
  }

  disconnect() { this._ws?.close(); }
}
```

---

## Layer architecture — every layer follows this interface

```javascript
// src/layers/LayerManager.js
export class BaseLayer {
  constructor(viewer) {
    this.viewer = viewer;
    this.enabled = false;
  }

  /** Called with a parsed EventEnvelope when this layer's kind arrives. */
  onEvent(envelope) {}

  /** Show or hide all entities managed by this layer. */
  setVisible(visible) {
    this.enabled = visible;
    this._entities?.forEach(e => { e.show = visible; });
    this.viewer.scene.requestRender();
  }

  /** Remove all entities from the globe. */
  clear() {
    this._entities?.forEach(e => this.viewer.entities.remove(e));
    this._entities = [];
  }
}
```

---

## Aircraft layer (AircraftLayer.js)

```javascript
import * as Cesium from 'cesium';
import { BaseLayer } from './LayerManager.js';

const MAX_AIRCRAFT = 2000;   // Hard cap — more than this kills performance

export class AircraftLayer extends BaseLayer {
  constructor(viewer) {
    super(viewer);
    this._byId = new Map();   // entity_id → { entity, lastSeen }
    this._pruneInterval = setInterval(() => this._prune(), 30_000);
  }

  onEvent(envelope) {
    if (envelope.kind !== 'aircraft') return;
    const { entity_id, lat, lon, alt_m, payload } = envelope;

    const pos = Cesium.Cartesian3.fromDegrees(lon, lat, alt_m ?? 0);

    if (this._byId.has(entity_id)) {
      // Update existing entity position
      const { entity } = this._byId.get(entity_id);
      entity.position = pos;
      entity.label.text = payload.callsign || entity_id;
      this._byId.get(entity_id).lastSeen = Date.now();
    } else {
      if (this._byId.size >= MAX_AIRCRAFT) return;  // Enforce cap
      const entity = this.viewer.entities.add({
        id: entity_id,
        position: pos,
        point: {
          pixelSize: 6,
          color: Cesium.Color.CYAN,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1,
          scaleByDistance: new Cesium.NearFarScalar(1e4, 1.2, 1e6, 0.4),
          show: this.enabled,
        },
        label: {
          text: payload.callsign || '',
          font: '11px monospace',
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cesium.Cartesian2(0, -14),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 1e6),
          show: this.enabled,
        },
      });
      this._byId.set(entity_id, { entity, lastSeen: Date.now() });
    }

    this.viewer.scene.requestRender();
  }

  /** Remove aircraft not seen in the last 60 seconds. */
  _prune() {
    const cutoff = Date.now() - 60_000;
    for (const [id, { entity, lastSeen }] of this._byId) {
      if (lastSeen < cutoff) {
        this.viewer.entities.remove(entity);
        this._byId.delete(id);
      }
    }
  }
}
```

---

## Satellite layer (CelesTrak TLE)

```javascript
// src/layers/SatelliteLayer.js
import * as Cesium from 'cesium';
import * as satellite from 'satellite.js';
import { BaseLayer } from './LayerManager.js';

const TLE_URL = 'https://celestrak.org/SOCRATES/query.php?...';  // or active.txt
const REFRESH_MS = 30_000;

export class SatelliteLayer extends BaseLayer {
  constructor(viewer) {
    super(viewer);
    this._sats = [];
    this._entities = [];
    this._animFrame = null;
  }

  async load() {
    const resp = await fetch('https://celestrak.org/SOCRATES/active.txt');
    const text = await resp.text();
    const lines = text.trim().split('\n');
    this._sats = [];
    for (let i = 0; i < lines.length - 2; i += 3) {
      this._sats.push({
        name: lines[i].trim(),
        satrec: satellite.twoline2satrec(lines[i+1], lines[i+2]),
      });
    }
    this._startAnimation();
  }

  _startAnimation() {
    const tick = () => {
      if (!this.enabled) { this._animFrame = requestAnimationFrame(tick); return; }
      const now = new Date();
      this._sats.forEach((sat, i) => {
        const pv = satellite.propagate(sat.satrec, now);
        if (!pv.position) return;
        const gmst = satellite.gstime(now);
        const geo = satellite.eciToGeodetic(pv.position, gmst);
        const lat = Cesium.Math.toDegrees(geo.latitude);
        const lon = Cesium.Math.toDegrees(geo.longitude);
        const alt = geo.height * 1000;  // km → m
        if (this._entities[i]) {
          this._entities[i].position = Cesium.Cartesian3.fromDegrees(lon, lat, alt);
        }
      });
      this.viewer.scene.requestRender();
      this._animFrame = requestAnimationFrame(tick);
    };
    this._animFrame = requestAnimationFrame(tick);
  }
}
```

**Performance note:** rendering 10,000+ satellites at 60fps is feasible only
with CesiumJS `PointPrimitives` (not `Entity` objects). Switch to a
`Cesium.PointPrimitiveCollection` when satellite count exceeds 500.

---

## Post-FX shader pipeline (PostFxManager.js)

CesiumJS exposes `viewer.scene.postProcessStages` for full-screen GLSL passes.

```javascript
// src/shaders/PostFxManager.js
import * as Cesium from 'cesium';

export class PostFxManager {
  constructor(scene) {
    this._scene = scene;
    this._stages = {};
    this._active = 'none';
  }

  _createStage(name, fragmentShader) {
    return new Cesium.PostProcessStage({
      name,
      fragmentShader,
      uniforms: {},
    });
  }

  loadAll() {
    this._stages.nvg  = this._scene.postProcessStages.add(
      this._createStage('nvg', NVG_GLSL));
    this._stages.flir = this._scene.postProcessStages.add(
      this._createStage('flir', FLIR_GLSL));
    this._stages.crt  = this._scene.postProcessStages.add(
      this._createStage('crt', CRT_GLSL));
    Object.values(this._stages).forEach(s => { s.enabled = false; });
  }

  setMode(mode) {
    Object.entries(this._stages).forEach(([name, stage]) => {
      stage.enabled = (name === mode);
    });
    this._active = mode;
    this._scene.requestRender();
  }
}

// Inline GLSL — import from .glsl files via Vite's ?raw import
const NVG_GLSL = `
uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;
void main() {
  vec4 c = texture(colorTexture, v_textureCoordinates);
  float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
  float noise = fract(sin(dot(v_textureCoordinates, vec2(127.1, 311.7))) * 43758.5);
  float g = lum * 1.4 + (noise - 0.5) * 0.08;
  out_FragColor = vec4(0.0, g, 0.0, 1.0);
}`;

const FLIR_GLSL = `
uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;
vec3 thermalPalette(float t) {
  if (t < 0.25) return mix(vec3(0,0,0.5), vec3(0,0,1), t*4.0);
  if (t < 0.5)  return mix(vec3(0,0,1), vec3(0,1,0), (t-0.25)*4.0);
  if (t < 0.75) return mix(vec3(0,1,0), vec3(1,1,0), (t-0.5)*4.0);
  return mix(vec3(1,1,0), vec3(1,0,0), (t-0.75)*4.0);
}
void main() {
  vec4 c = texture(colorTexture, v_textureCoordinates);
  float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
  out_FragColor = vec4(thermalPalette(lum), 1.0);
}`;
```

---

## Camera preset system (CameraPresets.js)

```javascript
// src/ui/CameraPresets.js
import * as Cesium from 'cesium';

export class CameraPresets {
  constructor(viewer) {
    this._viewer = viewer;
    this._presets = {};   // { key: { name, lat, lon, alt, heading, pitch } }
  }

  register(key, preset) {
    this._presets[key] = preset;
  }

  flyTo(key) {
    const p = this._presets[key];
    if (!p) return;
    this._viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt),
      orientation: {
        heading: Cesium.Math.toRadians(p.heading ?? 0),
        pitch: Cesium.Math.toRadians(p.pitch ?? -45),
        roll: 0,
      },
      duration: 2.0,
    });
  }

  bindKeys(keyMap) {
    // keyMap = { "q": "london_tower", "w": "heathrow", ... }
    document.addEventListener('keydown', e => {
      const presetKey = keyMap[e.key.toLowerCase()];
      if (presetKey) this.flyTo(presetKey);
    });
  }
}
```

Landmark coordinates come from the OpenStreetMap Nominatim API at build time
(not runtime). Store them in `src/config/landmarks.json` and commit — do not
fetch them live, as Nominatim has strict rate limits.

---

## LayerManager — toggles and registration

```javascript
// src/layers/LayerManager.js
export class LayerManager {
  constructor() {
    this._layers = new Map();   // kind → BaseLayer instance
  }

  register(kind, layer) {
    this._layers.set(kind, layer);
  }

  route(envelope) {
    const layer = this._layers.get(envelope.kind);
    if (layer?.enabled) layer.onEvent(envelope);
  }

  toggle(kind, visible) {
    this._layers.get(kind)?.setVisible(visible);
  }
}
```

In `main.js`:
```javascript
const lm = new LayerManager();
lm.register('aircraft', new AircraftLayer(viewer));
lm.register('vessel',   new VesselLayer(viewer));
lm.register('alert',    new AlertLayer(viewer));

const bus = new BusClient(config.wsUrl, envelope => lm.route(envelope));
bus.connect({ kinds: ['aircraft', 'vessel', 'alert'] });
```

---

## Performance rules — non-negotiable

- Always set `requestRenderMode: true` on the Viewer — never allow continuous rendering
- Always call `viewer.scene.requestRender()` after any entity mutation
- Hard cap entities per layer (aircraft: 2000, satellites: 500 with PointPrimitives, profiles: 5000)
- Use `DistanceDisplayCondition` on all labels — never show labels when zoomed out
- Use `NearFarScalar` on point sizes — entities should shrink when the camera is far away
- Traffic particles: load major roads first, then arterials, then minor roads — never load all at once
- Never import all of CesiumJS — use named imports to enable tree-shaking

---

## Environment variables (Vite)

```
# .env.local
VITE_CESIUM_TOKEN=your_cesium_ion_token
VITE_WS_URL=ws://localhost:8080/ws/stream
VITE_OSINT_API=http://localhost:5001/api/v1
```

Access via:
```javascript
// src/config.js
export const config = {
  cesiumToken: import.meta.env.VITE_CESIUM_TOKEN,
  wsUrl:       import.meta.env.VITE_WS_URL,
  osintApi:    import.meta.env.VITE_OSINT_API,
};
```

---

## Adding a new data layer — checklist

1. Create `src/layers/{Name}Layer.js` extending `BaseLayer`
2. Implement `onEvent(envelope)` — handle entity creation, update, and pruning
3. Register in `main.js` with the appropriate `EventKind` string
4. Add a toggle button in `ControlPanel.js`
5. Add to the WebSocket filter spec in `main.js` so the server forwards the new kind
6. Document the expected `payload` fields for this layer's event kind
7. Test with mock events by adding a fixture to `src/dev/mockEvents.js`
