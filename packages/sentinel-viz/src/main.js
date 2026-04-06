

import { initGlobe } from './globe.js';
import { config } from './config.js';
import { BusClient } from './bus.js';
import { LayerManager } from './layers/LayerManager.js';
import { AircraftLayer } from './layers/AircraftLayer.js';
import { VesselLayer } from './layers/VesselLayer.js';
import { SatelliteLayer } from './layers/SatelliteLayer.js';
import { AlertLayer } from './layers/AlertLayer.js';
import { PostFxManager } from './shaders/PostFxManager.js';
import { ControlPanel } from './ui/ControlPanel.js';
import { CameraPresets } from './ui/CameraPresets.js';
import { InfoPanel } from './ui/InfoPanel.js';
import { startMockFeed } from './dev/mockEvents.js';
import landmarks from './config/landmarks.json';

async function main() {
  // Initialise the CesiumJS globe
  const viewer = await initGlobe('cesiumContainer');

  // Layer manager — routes bus events to the right layer
  const lm = new LayerManager();

  const aircraftLayer = new AircraftLayer(viewer);
  const vesselLayer = new VesselLayer(viewer);
  const satelliteLayer = new SatelliteLayer(viewer);
  const alertLayer = new AlertLayer(viewer);

  lm.register('aircraft', aircraftLayer);
  lm.register('vessel', vesselLayer);
  lm.register('satellite', satelliteLayer);
  lm.register('alert', alertLayer);

  // Enable aircraft by default
  lm.toggle('aircraft', true);

  // Post-processing shaders
  const postFx = new PostFxManager(viewer.scene);
  postFx.loadAll();

  // Control panel UI
  const cp = new ControlPanel(lm, postFx);
  cp.mount();

  // Info panel (click-on-entity)
  const infoPanel = new InfoPanel(viewer);
  infoPanel.mount();

  // Camera presets — Q/W/E
  const cam = new CameraPresets(viewer);
  for (const [key, preset] of Object.entries(landmarks)) {
    cam.register(key, preset);
  }
  cam.bindKeys({ q: 'london', w: 'heathrow', e: 'channel' });

  // Load satellite TLEs (async, non-blocking)
  satelliteLayer.load().catch((e) => console.warn('[main] satellite load failed', e));

  // Connect to the event bus via WebSocket
  const bus = new BusClient(config.wsUrl, (envelope) => lm.route(envelope));
  bus.connect({ kinds: ['aircraft', 'vessel', 'alert'] });

  // In dev mode without a backend, start mock event feed
  if (import.meta.env.DEV && !import.meta.env.VITE_NO_MOCK) {
    console.log('[main] starting mock event feed (set VITE_NO_MOCK=1 to disable)');
    startMockFeed((envelope) => lm.route(envelope), 1000);
  }

  // Expose for debugging
  window.viewer = viewer;
  window.layerManager = lm;
  window.postFx = postFx;
}

main().catch((e) => console.error('[main] fatal', e));
